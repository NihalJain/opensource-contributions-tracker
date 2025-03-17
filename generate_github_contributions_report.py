import time
import requests
from collections import defaultdict
import logging
import os
import urllib3
import json
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress the insecure warning from urllib3.
urllib3.disable_warnings(category=urllib3.exceptions.InsecureRequestWarning)

# GitHub API base URL
GITHUB_API_URL = "https://api.github.com"

# Proxies configuration
proxies = {
    "http": os.getenv("HTTP_PROXY"),
    "https": os.getenv("HTTPS_PROXY")
}

# GitHub token for authentication
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Headers for authentication
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}


def get_all_pages(url, params, max_retries=3, backoff_factor=0.3):
    """
    Retrieve all pages of results from a paginated GitHub API endpoint.

    Args:
        url (str): The API endpoint URL.
        params (dict): The query parameters for the request.
        max_retries (int): The maximum number of retries for failed requests.
        backoff_factor (float): The factor for exponential backoff between retries.

    Returns:
        list: A list of results from all pages.
    """
    results = []
    page = 1
    while True:
        params['page'] = page
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=HEADERS, params=params, proxies=proxies, verify=False)
                response.raise_for_status()
                data = response.json()
                if not data:
                    return results
                results.extend(data)
                page += 1
                break  # Exit retry loop if request is successful
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
    params = {
        "author": user,
        "since": since_date,
        "per_page": per_page
    }
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
    params = {
        "state": state,
        "per_page": per_page
    }
    return get_all_pages(pr_url, params)


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
        project_to_repo_dict (dict): A dictionary mapping project names to repository lists.

    Returns:
        list: A list of dictionaries containing GitHub data.
    """
    # Format the start date
    formatted_start_date = datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y-%m-%dT%H:%M:%SZ")

    # Create a list to hold the data
    github_data = []

    try:
        # Populate the data list with dictionaries
        for project_name, repo_list in project_to_repo_dict.items():
            logger.info(f"Processing project: {project_name}")
            for repo in repo_list:
                logger.info(f"Processing repository: {repo}")
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

                    github_data.append({
                        "Project Name": project_name,
                        "Repository": repo,
                        "User": user,
                        "Commits": commit_count,
                        "Pull Requests (Open)": pr_count,
                        "Overall Contribution": commit_count + pr_count
                    })
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
    Group contributions by 'User' and 'Project Name'.

    Args:
        filtered_df (DataFrame): The filtered DataFrame with non-zero contributions.

    Returns:
        tuple: Two DataFrames, one grouped by 'User' and the other by 'Project Name'.
    """
    user_counts_df = filtered_df.groupby('User')[['Commits', 'Pull Requests (Open)']].sum().reset_index()
    user_counts_df['Overall Contribution'] = user_counts_df['Commits'] + user_counts_df['Pull Requests (Open)']
    user_counts_df = user_counts_df[user_counts_df['Overall Contribution'] > 0]
    logger.info("Grouped by 'User' and calculated overall contributions")

    project_counts_df = filtered_df.groupby('Project Name')[['Commits', 'Pull Requests (Open)']].sum().reset_index()
    project_counts_df['Overall Contribution'] = project_counts_df['Commits'] + project_counts_df['Pull Requests (Open)']
    project_counts_df = project_counts_df[project_counts_df['Overall Contribution'] > 0]
    logger.info("Grouped by 'Project Name' and calculated overall contributions")

    return user_counts_df, project_counts_df


def create_pie_chart(df, field, filename, percentage=-1):
    """
    Create a pie chart for the given DataFrame and save it as an image file.

    Args:
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
        plt.figure(figsize=(10, 10))  # Adjusted figure size
        colors = plt.cm.Paired(np.linspace(0., 1., len(value_counts)))
        explode = [0.1 if i == 'Other' else 0 for i in value_counts.index]
        patches, _ = plt.pie(value_counts, colors=colors, shadow=False, wedgeprops=dict(width=0.8, edgecolor='w'))

        # Draw circle for the center of the plot to make the pie look like a donut
        centre_circle = plt.Circle((0, 0), 0.20, fc='white')
        fig = plt.gcf()
        fig.gca().add_artist(centre_circle)

        # Create a legend for the total sum
        total_patch = Patch(color='none', label=f'Total Contributions: {total}')

        # Add the total_patch to the existing patches
        patches = [total_patch] + list(patches)

        plt.legend(handles=patches, labels=[total_patch.get_label()] + labels, loc="best", bbox_to_anchor=(1, 0.75),
                   fontsize=10, title=field)
        plt.margins(0, 0)
        plt.axis('equal')
        plt.savefig(filename, bbox_inches='tight', pad_inches=0)
        logger.info(f"Saved pie chart as {filename}")
        plt.close()
    except Exception as e:
        logger.error(f"An error occurred while creating the pie chart: {e}")
        raise


def create_markdown_report(github_data_df, user_counts_df, project_counts_df, output_filename, percentage=-1):
    """
    Create a markdown report of GitHub contributions and save it as a file.

    Args:
        github_data_df (DataFrame): The DataFrame containing GitHub data.
        user_counts_df (DataFrame): The DataFrame containing user contribution data.
        project_counts_df (DataFrame): The DataFrame containing project contribution data.
        output_filename (str): The filename to save the markdown report.
        percentage (int): The percentage threshold for grouping smaller values into 'Other'. Defaults to -1 (no grouping).

    Raises:
        Exception: If an error occurs while creating the markdown report.
    """
    try:
        # Ensure the output directory exists
        output_folder = os.path.dirname(output_filename)
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
            logger.info(f"Created output directory: {output_folder}")

        with open(output_filename, 'w') as f:
            # Add title
            f.write("# GitHub Contributions Report\n\n")

            # Add current time
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"Report auto-generated on: {current_time}\n\n")

            # Add summary table
            f.write("## Summary of Contributions by each user\n\n")
            f.write("| User | Commits | Pull Requests (Open) | Overall Contribution |\n")
            f.write("|------|---------|----------------------|----------------------|\n")
            for _, row in user_counts_df.sort_values(by=['Overall Contribution'], ascending=False).iterrows():
                f.write(
                    f"| {row['User']} | {row['Commits']} | {row['Pull Requests (Open)']} | {row['Overall Contribution']} |\n")

            # Add pie chart image for user wise contributions
            user_wise_contribution_fname = "user_wise_contribution.png"
            create_pie_chart(user_counts_df, 'User', os.path.join(output_folder, user_wise_contribution_fname),
                             percentage)
            f.write(f'\n<img src="{user_wise_contribution_fname}" alt="Contributions: User Wise" style="width:50%;">\n')

            # Add summary table for project wise
            f.write("\n## Summary of Contributions by each project\n\n")
            f.write("| Project Name | Commits | Pull Requests (Open) | Overall Contribution |\n")
            f.write("|--------------|---------|----------------------|----------------------|\n")
            for _, row in project_counts_df.sort_values(by=['Overall Contribution'], ascending=False).iterrows():
                f.write(
                    f"| {row['Project Name']} | {row['Commits']} | {row['Pull Requests (Open)']} | {row['Overall Contribution']} |\n")

            # Add a heatmap image for project wise contributions
            project_wise_contribution_fname = "project_wise_contribution.png"
            create_pie_chart(project_counts_df, 'Project Name',
                             os.path.join(output_folder, project_wise_contribution_fname))
            f.write(
                f'\n<img src="{project_wise_contribution_fname}" alt="Contributions: Project Wise" style="width:50%;">\n')

            # Add detailed contribution data for each user, use non_zero_df
            f.write("\n## Detailed Contributions\n\n")
            f.write("| Project Name | Repository | User | Commits | Pull Requests (Open) | Overall Contribution |\n")
            f.write("|--------------|------------|------|---------|----------------------|----------------------|\n")
            for _, row in github_data_df.sort_values(by=['Overall Contribution', 'User'],
                                                     ascending=[False, True]).iterrows():
                f.write(
                    f"| {row['Project Name']} | {row['Repository']} | {row['User']} | {row['Commits']} | {row['Pull Requests (Open)']} | {row['Overall Contribution']} |\n")

        logger.info(f"Markdown report created successfully: {output_filename}")
    except Exception as e:
        logger.error(f"An error occurred while creating the markdown report: {e}")
        raise


def generate_github_contributions_report(github_conf_path="input/github.json", output_dir="output/",
                                         report_fname="github_contributions_report.md"):
    """
    Generate a GitHub contributions report by reading input data, processing it, and creating a markdown report.

    This function reads the input data from a JSON file, processes the GitHub contributions,
    and generates a markdown report with the contributions summary.

    Args:
        github_conf_path (str): The path to the GitHub input JSON file. Defaults to "input/github.json".
        output_dir (str): The directory to save the output markdown report. Defaults to "output/".
        report_fname (str): The filename for the output markdown report. Defaults to "github_contributions_report.md".

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

        # Log the variables to verify
        logger.info(f"Start Date: {start_date}")
        logger.info(f"Users: {users}")
        logger.info(f"Project to Repo Dictionary: {project_to_repo_dict}")

        # Process the data
        github_data = process_github_data(start_date, users, project_to_repo_dict)
        github_data_df = convert_to_dataframe(github_data)
        github_data_df = filter_contributions(github_data_df)
        user_counts_df, project_counts_df = group_contributions(github_data_df)

        # Ensure the output directory exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"Created output directory: {output_dir}")

        # Create markdown report
        create_markdown_report(github_data_df, user_counts_df, project_counts_df,
                               os.path.join(output_dir, report_fname))

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise


if __name__ == "__main__":
    try:
        logger.info("Script started.")
        generate_github_contributions_report()
        logger.info("Script completed successfully.")
        exit(0)  # Ensure an exit code of 0 upon successful completion
    except Exception as e:
        logger.error(f"Failed to complete job: {e}")
        traceback.print_exc()
        exit(-1)
