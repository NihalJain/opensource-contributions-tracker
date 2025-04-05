import json
import logging
import os
import time
import traceback
from collections import defaultdict
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import urllib3
from matplotlib.patches import Patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress the insecure warning from urllib3.
urllib3.disable_warnings(category=urllib3.exceptions.InsecureRequestWarning)

# GitHub API base URL
GITHUB_API_URL = "https://api.github.com"

# Proxies configuration
proxies = {"http": os.getenv("HTTP_PROXY"), "https": os.getenv("HTTPS_PROXY")}

# GitHub token for authentication
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Headers for authentication
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}


def get_all_pages(url, params, max_retries=3, backoff_factor=0.3, with_pagination=True):
    """
    Retrieve all pages of results from a paginated GitHub API endpoint.

    Args:
        url (str): The API endpoint URL.
        params (dict): The query parameters for the request.
        max_retries (int): The maximum number of retries for failed requests.
        backoff_factor (float): The factor for exponential backoff between retries.
        with_pagination (bool): Whether to handle pagination. Defaults to True.

    Returns:
        list: A list of results from all pages.
    """
    results = []
    page = 1
    while True:
        if with_pagination:
            params['page'] = page
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=HEADERS, params=params, proxies=proxies, verify=False)
                response.raise_for_status()
                data = response.json()
                if not data:
                    return results

                if with_pagination:
                    if url == f"{GITHUB_API_URL}/search/issues":
                        # For search API, check if there are more pages
                        total_count = data.get('total_count', 0)
                        items = data.get('items', [])
                        results.extend(items)
                        # Check if there are more pages based on the total_count and current page
                        if len(items) > 0 and total_count > page * params.get('per_page', params['per_page']):
                            page += 1
                            continue
                        else:
                            return results
                    else:
                        results.extend(data)
                    page += 1
                else:
                    return data
                # Exit retry loop if request is successful, in this attempt
                break
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}, attempt {attempt + 1} of {max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(backoff_factor * (2 ** attempt))  # Exponential backoff
                else:
                    logger.critical(f"Max retries exceeded for URL: {url}")
                    raise e  # Raise the exception if max retries are exceeded
            # rate limit to max 60 requests per minute
            time.sleep(1)
    return results


def get_repositories_contributed_to(username, per_page=100):
    """
    Retrieve all repositories a user has contributed to via pull requests.

    Args:
        username (str): The GitHub username.
        per_page (int): The number of results per page.

    Returns:
        list: A list of repository names the user has contributed to.
    """
    params = {"q": f"type:pr author:{username}", "per_page": per_page}
    url = f"{GITHUB_API_URL}/search/issues"
    response_data = get_all_pages(url, params)

    repositories = set()
    for pr in response_data:
        repo_full_name = pr['repository_url'].split('/')[-2] + '/' + pr['repository_url'].split('/')[-1]
        repositories.add(repo_full_name)

    return list(repositories)


def get_top_contributors(repo, per_page=100):
    """
    Retrieve top 500 contributors for a repository.

    Args:
        repo (str): The repository name.
        per_page (int): The number of results per page.

    Returns:
        list: A list of contributors.
    """
    params = {"per_page": per_page}
    contributors_url = f"{GITHUB_API_URL}/repos/{repo}/contributors"
    return get_all_pages(contributors_url, params)


def get_commits(user, repo, since_date, per_page=100):
    """
    Retrieve commits for a specific user in a repository since a given date.

    Args:
        user (str): The GitHub username.
        repo (str): The repository name.
        since_date (str): The start date for retrieving commits in ISO 8601 format.
        per_page (int): The number of results per page.

    Returns:
        list: A list of commits.
    """
    commits_url = f"{GITHUB_API_URL}/repos/{repo}/commits"
    params = {"author": user, "since": since_date, "per_page": per_page}
    return get_all_pages(commits_url, params)


def get_pull_requests(repo, state="open", per_page=100):
    """
    Retrieve pull requests for a repository.

    Args:
        repo (str): The repository name.
        state (str): The state of the pull requests (e.g., "open", "closed").
        per_page (int): The number of results per page.

    Returns:
        list: A list of pull requests.
    """
    pr_url = f"{GITHUB_API_URL}/repos/{repo}/pulls"
    params = {"state": state, "per_page": per_page}
    return get_all_pages(pr_url, params)


def get_user_info(user):
    """
    Retrieve user information for a GitHub user.

    Args:
        user (str): The GitHub username.

    Returns:
        Information about the user.
    """
    user_url = f"{GITHUB_API_URL}/users/{user}"
    params = {}
    return get_all_pages(user_url, params, with_pagination=False)


def get_repo_info(repo):
    """
    Retrieve repository information for a GitHub repository.

    Args:
        user (str): The GitHub repository of form owner/repo.

    Returns:
        Information about the repository.
    """
    user_url = f"{GITHUB_API_URL}/repos/{repo}"
    params = {}
    return get_all_pages(user_url, params, with_pagination=False)


def read_github_input_file(file_path):
    """
    Read GitHub input data from a JSON file.

    Args:
        file_path (str): The path to the JSON file.

    Returns:
        dict: The data read from the JSON file.
    """
    try:
        with open(file_path, 'r') as json_file:
            data = json.load(json_file)
            logger.info(f"Successfully read data from {file_path}")
            return data
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        raise
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from file: {file_path}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")
        raise


def process_github_data(start_date, users, project_to_repo_dict):
    """
    Process GitHub data to retrieve commits and pull requests for users and projects.

    Args:
        start_date (str): The start date for retrieving data in "YYYY-MM-DD" format.
        users (list): A list of GitHub usernames.
        project_to_repo_dict (dict): A dictionary mapping project keys to repository lists.

    Returns:
        list: A list of dictionaries containing GitHub data.
    """
    # Format the start date
    formatted_start_date = datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y-%m-%dT%H:%M:%SZ")

    # Create a list to hold the data
    github_data = []

    try:
        logger.info("Processing user data...")
        user_info_dict = {}
        for user in users:
            logger.info(f"Processing user: {user}")
            user_info = get_user_info(user)
            user_info_dict[user] = {"name": user_info.get('name', user), "avatar_url": user_info.get('avatar_url'),
                                    "url": user_info.get('html_url')}

        logger.info("Processing project data...")
        repo_info_dict = {}
        for project_key, repo_list in project_to_repo_dict.items():
            logger.info(f"Processing project: {project_key}")
            for repo in repo_list:
                logger.info(f"Processing repository: {repo}")
                repo_info = get_repo_info(repo)
                repo_info_dict[repo] = {"name": repo_info.get('full_name', user),
                                        "description": repo_info.get('description'), "url": repo_info.get('html_url'),
                                        "avatar_url": repo_info.get('owner', {}).get('avatar_url')}

        # Populate the data list with dictionaries
        logger.info("Fetching contribution data...")
        for project_key, repo_list in project_to_repo_dict.items():
            logger.info(f"Processing project: {project_key}")
            for repo in repo_list:
                logger.info(f"Processing repository: {repo}")

                logger.info(f"Fetching top 500 contributors: {repo}")
                top_contributors = get_top_contributors(repo)
                top_contributors_rank = {str(contributor["login"]).lower(): rank for rank, contributor in
                                         enumerate(top_contributors, start=1)}
                top_contributors_in_users = {}

                # Check if any of the user is in the top contributor list and if present notedown their rank
                for user in users:
                    if user in top_contributors_rank:
                        top_contributors_in_users[user] = top_contributors_rank[user]

                logger.info(
                    f"Users: {top_contributors_in_users} are in top 500 contributor list of the repository: {repo}")
                logger.info(f"Fetching pull requests (open) for repository: {repo}")
                prs = get_pull_requests(repo, state="open")

                # Create a dictionary to map users to their pull requests
                user_prs_dict = defaultdict(list)
                for pr in prs:
                    user_login = str(pr["user"]["login"]).lower().strip()
                    if pr["created_at"] >= start_date:
                        user_prs_dict[user_login].append(pr)

                for user in users:
                    logger.info(f"Processing user: {user}")
                    commits = get_commits(user, repo, formatted_start_date)
                    commit_count = len(commits)
                    pr_count = len(user_prs_dict[user])

                    user_info = user_info_dict[user]
                    repo_info = repo_info_dict[repo]

                    github_data.append(
                        {"Project Key": project_key, "Repository": repo, "Repository URL": repo_info['url'],
                            "Repository Description": repo_info['description'],
                            "Repository Avatar": repo_info['avatar_url'],
                            "User": user_info['name'] if user_info['name'] else user,
                            "User Avatar": user_info['avatar_url'], "User URL": user_info['url'],
                            "Commits": commit_count, "Pull Requests (Open)": pr_count,
                            "Rank": top_contributors_in_users.get(user, -1),
                            "Overall Contribution": commit_count + pr_count})
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise

    return github_data


def convert_to_dataframe(github_data):
    """
    Convert the list of dictionaries to a DataFrame.

    Args:
        github_data (list): A list of dictionaries containing GitHub data.

    Returns:
        DataFrame: A pandas DataFrame containing the GitHub data.
    """
    github_data_df = pd.DataFrame(github_data)
    logger.info("Converted github_data to DataFrame")
    return github_data_df


def filter_contributions(github_data_df):
    """
    Filter out all entries with contributions equal to 0.

    Args:
        github_data_df (DataFrame): The DataFrame containing GitHub data.

    Returns:
        DataFrame: A filtered DataFrame with non-zero contributions.
    """
    filtered_df = github_data_df[(github_data_df['Commits'] > 0) | (github_data_df['Pull Requests (Open)'] > 0)]
    logger.info("Filtered out entries with zero contributions")
    return filtered_df


def group_contributions(filtered_df):
    """
    Group contributions by 'User' and 'Project Key'.

    Args:
        filtered_df (DataFrame): The filtered DataFrame with non-zero contributions.

    Returns:
        tuple: Two DataFrames, one grouped by 'User' and the other by 'Project Key'.
    """
    project_df = filtered_df.groupby('Project Key')[['Commits', 'Pull Requests (Open)']].sum().reset_index()
    project_df['Repositories'] = filtered_df.groupby('Project Key').apply(
        lambda x: list(zip(x['Repository'], x['Repository URL'], x['Repository Avatar']))).reset_index(drop=True).apply(
        lambda x: list(set(x)))
    project_df['Repositories'] = project_df['Repositories'].apply(lambda x: sorted(x, key=lambda y: y[0]))
    project_df['Repository Count'] = filtered_df.groupby('Project Key')['Repository'].nunique().reset_index()[
        'Repository']
    project_df['Users'] = filtered_df.groupby('Project Key').apply(
        lambda x: list(zip(x['User'], x['User URL'], x['User Avatar']))).reset_index(drop=True).apply(
        lambda x: list(set(x)))
    project_df['Users'] = project_df['Users'].apply(lambda x: sorted(x, key=lambda y: y[0]))
    project_df['Overall Contribution'] = project_df['Commits'] + project_df['Pull Requests (Open)']
    project_df = project_df[project_df['Overall Contribution'] > 0]
    logger.info("Grouped by 'Project Key' and calculated overall contributions")

    users_df = filtered_df.groupby('User')[['Commits', 'Pull Requests (Open)']].sum().reset_index()
    users_df['Repositories'] = filtered_df.groupby('User').apply(
        lambda x: list(zip(x['Repository'], x['Repository URL'], x['Repository Avatar']))).reset_index(drop=True).apply(
        lambda x: list(set(x)))
    users_df['Repositories'] = users_df['Repositories'].apply(lambda x: sorted(x, key=lambda y: y[0]))
    users_df['Repository Count'] = filtered_df.groupby('User')['Repository'].nunique().reset_index()['Repository']
    users_df['User URL'] = users_df['User'].apply(lambda x: filtered_df[filtered_df['User'] == x]['User URL'].iloc[0])
    users_df['User Avatar'] = users_df['User'].apply(
        lambda x: filtered_df[filtered_df['User'] == x]['User Avatar'].iloc[0])
    users_df['Overall Contribution'] = users_df['Commits'] + users_df['Pull Requests (Open)']
    users_df = users_df[users_df['Overall Contribution'] > 0]
    logger.info("Grouped by 'User' and calculated overall contributions")

    return project_df, users_df


def create_pie_chart(title, df, field, filename, percentage=-1):
    """
    Create a pie chart for the given DataFrame and save it as an image file.

    Args:
        title (str): The title of the pie chart.
        df (DataFrame): The DataFrame containing the data.
        field (str): The field to group by for the pie chart.
        filename (str): The filename to save the pie chart image.
        percentage (int): The percentage threshold for grouping smaller values into 'Other'. Defaults to -1 (no grouping).

    Raises:
        Exception: If an error occurs while creating the pie chart.
    """
    try:
        # Group by the field and sum the 'Commits' and 'Pull Requests (Open)'
        df_copy = df.groupby(field)[['Commits', 'Pull Requests (Open)']].sum().reset_index()
        logger.info(f"Grouped data by {field}")

        # Add a new field 'Overall Contribution' which is the sum of 'Commits' and 'Pull Requests (Open)'
        df_copy['Overall Contribution'] = df_copy['Commits'] + df_copy['Pull Requests (Open)']
        logger.info("Calculated 'Overall Contribution'")

        # Find values with count less than a given percentage of the maximum count
        threshold = df_copy['Overall Contribution'].max() * percentage / 100
        less_than_threshold = df_copy[df_copy['Overall Contribution'] < threshold][field]

        if percentage != -1:
            # Replace these values with 'Other' in the DataFrame copy
            df_copy.loc[df_copy[field].isin(less_than_threshold), field] = 'Other'
            logger.info(f"Replaced values less than {percentage}% of max with 'Other'")

        # Get value counts again and sort
        value_counts = df_copy.groupby(field)['Overall Contribution'].sum().sort_values(ascending=False)
        total = value_counts.sum()

        # Prepare labels for the legend with percentage
        labels = [f"{index} - {value} ({value * 100 / total:.2f}%)" for index, value in value_counts.items()]

        # Plot donut chart
        plt.figure(figsize=(10, 10))
        colors = plt.cm.coolwarm(np.linspace(0, 1, len(labels)))
        patches, texts, autotexts = plt.pie(value_counts, colors=colors, shadow=True,
                                            wedgeprops=dict(width=0.6, edgecolor='w'), autopct='%1.2f%%')

        # Draw circle for the center of the plot to make the pie look like a donut
        centre_circle = plt.Circle((0, 0), 0.1, fc='white')
        fig = plt.gcf()
        fig.gca().add_artist(centre_circle)

        # Create a legend for the total sum
        total_patch = Patch(color='none', label=f'Total Contributions: {total}')

        # Add the total_patch to the existing patches
        patches = [total_patch] + list(patches)

        plt.title(title, fontsize=24)
        plt.legend(handles=patches, labels=[total_patch.get_label()] + labels, loc="upper center",
            bbox_to_anchor=(1, 1.1), fontsize=10, title=field)
        plt.margins(0, 0)
        plt.axis('equal')
        plt.savefig(filename, bbox_inches='tight', pad_inches=0.5)
        logger.info(f"Saved pie chart as {filename}")
        plt.close()
    except Exception as e:
        logger.error(f"An error occurred while creating the pie chart: {e}")
        raise


def print_input_json_format():
    """
    Print the format of the input JSON file for OpenSource contributions tracking.

    Returns:
        None
    """
    input_json = {"start_date": "YYYY-MM-DD", "users": ["user1", "user2"],
        "project_to_repo_dict": {"Project 1": ["owner1/repo1", "owner1/repo2"], "Project 2": ["owner2/repo3"]}}
    logger.info("Format of the input JSON file for OpenSource contributions tracking:")
    logger.info(json.dumps(input_json, indent=4))
    logger.info("NOTE: The 'project_to_repo_dict' key is optional."
                "If not provided, the script will use the 'users' key to get the repositories.")


def process_data(github_data_df):
    """
    Process the data for contributions.

    Args:
        github_data_df (DataFrame): The DataFrame containing GitHub data.

    Returns:
        github_data_df (DataFrame): The processed DataFrame containing GitHub data.
        projects_df (DataFrame): The DataFrame containing project-wise contributions.
        users_df (DataFrame): The DataFrame containing user-wise contributions.
    """
    github_data_df = filter_contributions(github_data_df)
    projects_df, users_df = group_contributions(github_data_df)
    return github_data_df, projects_df, users_df


def process_data_and_create_report(github_data_df, output_dir, report_filename, percentage, shouldDump=True):
    """
    Process data and create a markdown report of GitHub contributions and save it as a file.

    Args:
        github_data_df (DataFrame): The DataFrame containing GitHub data.
        output_dir (str): The directory to save the output markdown report.
        report_filename (str): The filename for the output markdown report.
        shouldDump (bool): Whether to dump the contribution data to a file. Defaults to True.
        percentage (int): The percentage threshold for grouping smaller values into 'Other'. This value represents the
            percentage of the maximum contribution. Defaults to -1 (no grouping).

    Raises:
        Exception: If an error occurs while creating the markdown report.
    """
    try:
        github_data_df, projects_df, users_df = process_data(github_data_df)
        create_markdown_report(github_data_df, users_df, projects_df, output_dir, report_filename, percentage)

        # Dump contribution data to an output file for offline processing
        # NOTE: To reload run `github_data_df = pd.read_csv(output_dir + 'github_contribution_data.csv')`
        if shouldDump:
            github_data_df.to_csv(output_dir + 'github_contribution_data.csv', index=False)
            logger.info(f"Dumped contribution data to {output_dir}'github_contribution_data.csv'")
    except Exception as e:
        logger.error(f"An error occurred while creating the markdown report: {e}")
        raise


def create_markdown_report(github_data_df, users_df, projects_df, output_dir, report_filename, percentage):
    """
    Create a markdown report of GitHub contributions and save it as a file.

    Args:
        github_data_df (DataFrame): The DataFrame containing GitHub data.
        users_df (DataFrame): The DataFrame containing user-wise contributions.
        projects_df (DataFrame): The DataFrame containing project-wise contributions.
        output_dir (str): The folder to save the markdown report.
        report_filename (str): The filename for the output markdown report.
        percentage (int): The percentage threshold for grouping smaller values into 'Other'. This value represents the
            percentage of the maximum contribution. Defaults to -1 (no grouping).
    """
    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logger.info(f"Created output directory: {output_dir}")

    with open(os.path.join(output_dir, report_filename), 'w') as f:
        # Add title of the report
        f.write("# OpenSource Contributions Report\n\n")

        # Add current time
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"Report auto-generated on: {current_time}\n\n")

        # Add Summary
        number_of_users = len(users_df)
        number_of_projects = len(projects_df)
        number_of_repos = len(github_data_df['Repository'].unique())
        total_overall_contributions = github_data_df['Overall Contribution'].sum()
        total_number_of_commits = github_data_df['Commits'].sum()
        total_number_of_open_prs = github_data_df['Pull Requests (Open)'].sum()

        # Add summary table
        f.write("## Overall Summary\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Total number of projects | {number_of_projects} |\n")
        if number_of_users > 1:
            f.write(f"| Total number of contributors | {number_of_users} |\n")
        f.write(f"| Total number of repositories | {number_of_repos} |\n")
        f.write(f"| Total number of contributions | {total_overall_contributions} |\n")
        f.write(f"| Number of commits | {total_number_of_commits} |\n")
        f.write(f"| Number of pull requests (Open) | {total_number_of_open_prs} |\n")

        # Add a pie chart image for project wise contributions
        project_wise_contribution_fname = "project_wise_contribution.png"
        create_pie_chart("Project wise Contributions", projects_df, 'Project Key',
                         os.path.join(output_dir, project_wise_contribution_fname))

        # Add pie chart image for user wise contributions
        user_wise_contribution_fname = "user_wise_contribution.png"
        create_pie_chart("User wise Contributions", users_df, 'User',
                         os.path.join(output_dir, user_wise_contribution_fname), percentage)

        f.write(f'\n<div style="display: flex; justify-content: space-around;">\n'
                f'  <img src="{project_wise_contribution_fname}" alt="Project wise Contributions" style="width:45%;">\n'
                f'  <img src="{user_wise_contribution_fname}" alt="User wise Contributions" style="width:45%;">\n'
                f'</div>\n')

        if users_df.empty:
            f.write("No contributions found for the given users.\n")
        else:
            # Sort the project counts by 'Overall Contribution' in descending order and write to the markdown file
            f.write("\n## Summary of Contributions by each project\n\n")
            f.write("| Project Key | Repositories | Users | Commits | Pull Requests (Open) | Overall Contribution |\n")
            f.write("|--------------|--------------|-------|---------|----------------------|----------------------|\n")
            for _, row in projects_df.sort_values(by=['Overall Contribution'], ascending=False).iterrows():
                repo_list = '<br>'.join(
                    [f"<img src='{avatar}' width='12' height='12'> [{repo}]({url})" for repo, url, avatar in
                     row['Repositories']])
                user_list = '<br>'.join(
                    [f"<img src='{avatar}' width='12' height='12'> [{user}]({url})" for user, url, avatar in
                     row['Users']])
                f.write(
                    f"| {row['Project Key']} | {repo_list} | {user_list} | {row['Commits']} " + f"| {row['Pull Requests (Open)']} | {row['Overall Contribution']} |\n")

            # Sort the user counts by 'Overall Contribution' in descending order and write to the markdown file
            f.write("\n## Summary of Contributions by each user\n\n")
            f.write("| User | Repositories | Commits | Pull Requests (Open) | Overall Contribution |\n")
            f.write("|------|--------------|---------|----------------------|----------------------|\n")
            for _, row in users_df.sort_values(by=['Overall Contribution'], ascending=False).iterrows():
                user_avatar = f"<img src='{row['User Avatar']}' width='12' height='12'>"
                repo_list = '<br>'.join(
                    [f"<img src='{avatar}' width='12' height='12'> [{repo}]({url})" for repo, url, avatar in
                     row['Repositories']])
                f.write(
                    f"| {user_avatar} [{row['User']}]({row['User URL']}) | {repo_list} | {row['Commits']} " + f"| {row['Pull Requests (Open)']} | {row['Overall Contribution']} |\n")

            # Sort the detailed contributions by 'Overall Contribution' in descending order and 'User' in ascending order
            # and write to the markdown file
            f.write("\n## Detailed Contributions\n\n")
            f.write("| Project Key | Repository | User | Commits | Pull Requests (Open) | Overall Contribution |\n")
            f.write("|--------------|------------|------|---------|----------------------|----------------------|\n")
            for _, row in github_data_df.sort_values(by=['User'], ascending=[True]).iterrows():
                repo_avatar = f"<img src='{row['Repository Avatar']}' width='12' height='12'>"
                user_avatar = f"<img src='{row['User Avatar']}' width='12' height='12'>"
                f.write(
                    f"| {row['Project Key']} | {repo_avatar} [{row['Repository']}]({row['Repository URL']})" + f" | {user_avatar} [{row['User']}]({row['User URL']}) | {row['Commits']} |" + f" {row['Pull Requests (Open)']} | {row['Overall Contribution']} |\n")
    logger.info(f"Markdown report created successfully: {report_filename}")


def generate_report(github_conf_path="input/github.json", output_dir="output/",
                    report_fname="github_contributions_report.md", percentage=-1):
    """
    Generate a GitHub contributions report by reading input data, processing it, and creating a markdown report.

    This function reads the input data from a JSON file, processes the GitHub contributions,
    and generates a markdown report with the contributions summary.

    Args:
        github_conf_path (str): The path to the GitHub input JSON file. Defaults to "input/github.json".
        output_dir (str): The directory to save the output markdown report. Defaults to "output/".
        report_fname (str): The filename for the output markdown report. Defaults to "github_contributions_report.md".
        percentage (int): The percentage threshold for grouping smaller values into 'Other'. This value represents the
            percentage of the maximum contribution. Defaults to -1 (no grouping).

    Returns:
        None

    Raises:
        Exception: If an error occurs during the process.
    """
    try:
        # Read input for GitHub from JSON file
        github_conf_data = read_github_input_file(github_conf_path)

        # Extract variables from the loaded data
        start_date = github_conf_data.get('start_date')
        users = github_conf_data.get('users', [])
        project_to_repo_dict = github_conf_data.get('project_to_repo_dict', {})

        # if project to repo dict is empty, use get_repositories_contributed_to to get the repositories
        if not project_to_repo_dict:
            project_to_repo_dict = {}
            for user in users:
                # for each project create one entry
                repo_list = get_repositories_contributed_to(user)
                for repo in repo_list:
                    project_to_repo_dict[repo] = [repo]

        # Ensure input is valid
        if not start_date:
            print_input_json_format()
            raise ValueError("Start date is required in the input data.")
        if not users:
            print_input_json_format()
            raise ValueError("At least one user is required in the input data.")
        if not project_to_repo_dict:
            print_input_json_format()
            raise ValueError("At least one project with repositories is required in the input data.")

        # Lower case all the users
        users = [str(user).lower().strip() for user in users]

        # Log the variables to verify
        logger.info(f"Start Date: {start_date}")
        logger.info(f"Users: {users}")
        logger.info(f"Project to Repo Dictionary: {project_to_repo_dict}")

        # Create markdown report
        github_data = process_github_data(start_date, users, project_to_repo_dict)
        github_data_df = convert_to_dataframe(github_data)
        process_data_and_create_report(github_data_df, output_dir, report_fname, percentage)

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise


def generate_report_with_local_data(github_data_csv_path="output/github_contribution_data.csv", output_dir="output/",
                                    report_fname="github_contributions_report.md", percentage=-1):
    """
    Generate a GitHub contributions report by reading input data, processing it, and creating a markdown report.

    This function reads the input data from a CSV file, processes the GitHub contributions,
    and generates a markdown report with the contributions summary.

    Args:
        github_data_csv_path (str): The path to the GitHub input CSV file. Defaults to "output/github_contribution_data.csv".
        output_dir (str): The directory to save the output markdown report. Defaults to "output/".
        report_fname (str): The filename for the output markdown report. Defaults to "github_contributions_report.md".
        percentage (int): The percentage threshold for grouping smaller values into 'Other'. This value represents the
            percentage of the maximum contribution. Defaults to -1 (no grouping).

    Returns:
        None

    Raises:
        Exception: If an error occurs during the process.
    """
    try:
        # Read input for GitHub from CSV file
        github_data_df = pd.read_csv(github_data_csv_path)

        # Create markdown report
        process_data_and_create_report(github_data_df, output_dir, report_fname, percentage, shouldDump=False)

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise


if __name__ == "__main__":
    try:
        logger.info("Script started.")
        # You can customize the input JSON file path, output directory, and report filename as follows:
        # generate_report(github_conf_path="input/github.json", output_dir="output/", report_fname="github_contributions_report.md")
        generate_report()
        # In order to generate the report with local data, in case you have the data
        # Comment the above code line i.e. generate_report()
        # Next, uncomment the below code line
        # generate_report_with_local_data()
        logger.info("Script completed successfully.")
        # Ensure an exit code of 0 upon successful completion, required by test workflow
        exit(0)
    except Exception as e:
        logger.error(f"Failed to complete job: {e}")
        traceback.print_exc()
        exit(-1)
