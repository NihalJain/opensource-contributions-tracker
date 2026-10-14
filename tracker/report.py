"""
Writing the report: the markdown file, its pie charts, and the CSV and JSON data files.
"""
import json
import os
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

from . import aggregate, config
from .log import logger


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
        # Use the pre-computed Overall Contribution column so contribution_config flags are respected
        df_copy = df.groupby(field)['Overall Contribution'].sum().reset_index()
        logger.info(f"Grouped data by {field}")

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

def process_data_and_create_report(github_data_df, output_dir, report_filename, percentage, shouldDump=True, start_date=None, end_date=None, contribution_config=None, activity_data=None):
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
        github_data_df, projects_df, users_df = aggregate.process_data(github_data_df)
        create_markdown_report(github_data_df, users_df, projects_df, output_dir, report_filename, percentage, start_date, end_date, contribution_config, activity_data)

        # Dump contribution data to an output file for offline processing
        # NOTE: To reload run `github_data_df = pd.read_csv(output_dir + 'github_contribution_data.csv')`
        if shouldDump:
            github_data_df.to_csv(output_dir + 'github_contribution_data.csv', index=False)
            logger.info(f"Dumped contribution data to '{output_dir}github_contribution_data.csv'")
            if activity_data is not None:
                activity_json_path = output_dir + 'github_activity_data.json'
                with open(activity_json_path, 'w') as af:
                    json.dump(activity_data, af)
                logger.info(f"Dumped activity data to '{activity_json_path}'")
    except Exception as e:
        logger.error(f"An error occurred while creating the markdown report: {e}")
        raise


def _write_activity_details(f, activity_data):
    """
    Write the '## Activity Details' section listing every PR and issue per user / project / repo.

    Args:
        f: Open file handle to write into.
        activity_data (list): List of dicts produced by process_github_data, each containing full
                              PR and issue objects for one (user, project, repo) combination.
    """
    f.write("\n## Activity Details\n")

    # Group entries by user display name, preserving first-seen metadata
    users_map = {}
    for entry in activity_data:
        user = entry['user']
        if user not in users_map:
            users_map[user] = {'meta': entry, 'entries': []}
        users_map[user]['entries'].append(entry)

    for user, user_data in sorted(users_map.items()):
        meta = user_data['meta']
        f.write(f"\n### <img src='{meta['user_avatar']}' width='20' height='20'>"
                f" [{user}]({meta['user_url']})\n")

        # Group by project key
        projects_map = {}
        for entry in user_data['entries']:
            pk = entry['project_key']
            if pk not in projects_map:
                projects_map[pk] = []
            projects_map[pk].append(entry)

        for project_key, proj_entries in sorted(projects_map.items()):
            repo_entries = [
                (entry, entry['open_prs'] + entry['closed_prs'], entry['open_issues'] + entry['closed_issues'])
                for entry in sorted(proj_entries, key=lambda x: x['repo'])
            ]
            # Skip project entirely if no repo has any PRs or issues
            if not any(prs or issues for _, prs, issues in repo_entries):
                continue

            f.write(f"\n#### {project_key}\n")

            for entry, all_prs, all_issues in repo_entries:
                if not all_prs and not all_issues:
                    continue

                f.write(f"\n##### [{entry['repo']}]({entry['repo_url']})\n")

                if all_prs:
                    f.write("\n**Pull Requests**\n\n")
                    f.write("| # | Title | Status | Created | Updated | Labels |\n")
                    f.write("|---|-------|--------|---------|---------|--------|\n")
                    for pr in sorted(all_prs, key=lambda x: x.get('number', 0)):
                        number = pr.get('number', '')
                        title = pr.get('title', '').replace('|', '\\|').replace('\r', '').replace('\n', ' ')
                        url = pr.get('html_url', '')
                        created = pr.get('created_at', '')[:10]
                        updated = pr.get('updated_at', '')[:10]
                        labels = ', '.join(lbl['name'] for lbl in pr.get('labels', []))
                        merged_at = (pr.get('pull_request') or {}).get('merged_at')
                        if pr.get('state') == 'open':
                            status = '🔄 Open'
                        elif merged_at:
                            status = '✅ Merged'
                        else:
                            status = '❌ Closed'
                        f.write(f"| [#{number}]({url}) | {title} | {status} | {created} | {updated} | {labels} |\n")

                if all_issues:
                    f.write("\n**Issues**\n\n")
                    f.write("| # | Title | Status | Created | Updated | Labels |\n")
                    f.write("|---|-------|--------|---------|---------|--------|\n")
                    for issue in sorted(all_issues, key=lambda x: x.get('number', 0)):
                        number = issue.get('number', '')
                        title = issue.get('title', '').replace('|', '\\|').replace('\r', '').replace('\n', ' ')
                        url = issue.get('html_url', '')
                        created = issue.get('created_at', '')[:10]
                        updated = issue.get('updated_at', '')[:10]
                        labels = ', '.join(lbl['name'] for lbl in issue.get('labels', []))
                        status = '🔓 Open' if issue.get('state') == 'open' else '🔒 Closed'
                        f.write(f"| [#{number}]({url}) | {title} | {status} | {created} | {updated} | {labels} |\n")


def _repo_markdown(repo, url, avatar):
    """A repository as an avatar and a link; plain text when it has no URL, as for redacted private work."""
    if not isinstance(url, str) or not url:
        return str(repo)
    return f"<img src='{avatar}' width='12' height='12'> [{repo}]({url})"


def create_markdown_report(github_data_df, users_df, projects_df, output_dir, report_filename, percentage, start_date=None, end_date=None, contribution_config=None, activity_data=None):
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

        # Add current time and date range
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"*Report auto-generated on: {current_time} for period {start_date or 'N/A'} to {end_date or 'N/A'}*\n\n")

        # Add Summary
        number_of_users = len(users_df)
        number_of_projects = len(projects_df)
        number_of_repos = len(github_data_df['Repository'].unique())
        total_overall_contributions = github_data_df['Overall Contribution'].sum()
        total_number_of_commits = github_data_df['Commits'].sum()
        total_number_of_open_prs = github_data_df['Pull Requests (Open)'].sum()
        total_number_of_closed_prs = github_data_df['Pull Requests (Closed)'].sum()
        total_number_of_open_issues = github_data_df['Issues (Open)'].sum()
        total_number_of_closed_issues = github_data_df['Issues (Closed)'].sum()
        total_number_of_code_reviews = github_data_df['Code Reviews'].sum()
        total_lines_added = github_data_df['Lines Added'].sum()
        total_lines_removed = github_data_df['Lines Removed'].sum()
        total_lines_added_merged = github_data_df['Lines Added (Merged)'].sum()
        total_lines_removed_merged = github_data_df['Lines Removed (Merged)'].sum()
        total_lines_added_open_prs = github_data_df['Lines Added (Open PRs)'].sum()
        total_lines_removed_open_prs = github_data_df['Lines Removed (Open PRs)'].sum()

        # Resolve per-metric config for report rendering
        commits_cfg = config._metric_cfg(contribution_config, 'commits')
        open_prs_cfg = config._metric_cfg(contribution_config, 'open_prs')
        closed_prs_cfg = config._metric_cfg(contribution_config, 'closed_prs')
        open_issues_cfg = config._metric_cfg(contribution_config, 'open_issues')
        closed_issues_cfg = config._metric_cfg(contribution_config, 'closed_issues')
        code_reviews_cfg = config._metric_cfg(contribution_config, 'code_reviews')
        include_line_stats = config._line_stats_cfg(contribution_config)['enabled']

        def _marker(cfg):
            return "*" if cfg['enabled'] and cfg['count_towards_score'] else ""

        # Add summary table
        f.write("## Overall Summary\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Total number of projects | {number_of_projects} |\n")
        if number_of_users > 1:
            f.write(f"| Total number of contributors | {number_of_users} |\n")
        f.write(f"| Total number of repositories | {number_of_repos} |\n")
        f.write(f"| Total number of contributions | {total_overall_contributions} |\n")
        if commits_cfg['enabled']:
            f.write(f"| Number of commits to master{_marker(commits_cfg)} | {total_number_of_commits} |\n")
        if open_prs_cfg['enabled']:
            f.write(f"| Number of pull requests (Open){_marker(open_prs_cfg)} | {total_number_of_open_prs} |\n")
        if closed_prs_cfg['enabled']:
            f.write(f"| Number of pull requests (Closed){_marker(closed_prs_cfg)} | {total_number_of_closed_prs} |\n")
        if open_issues_cfg['enabled']:
            f.write(f"| Number of issues (Open){_marker(open_issues_cfg)} | {total_number_of_open_issues} |\n")
        if closed_issues_cfg['enabled']:
            f.write(f"| Number of issues (Closed){_marker(closed_issues_cfg)} | {total_number_of_closed_issues} |\n")
        if code_reviews_cfg['enabled']:
            f.write(f"| Total unique PRs reviewed{_marker(code_reviews_cfg)} | {total_number_of_code_reviews} |\n")
        if include_line_stats:
            f.write(f"| Lines added (commits) | {total_lines_added_merged:,} |\n")
            f.write(f"| Lines removed (commits) | {total_lines_removed_merged:,} |\n")
            f.write(f"| Lines added (open PRs) | {total_lines_added_open_prs:,} |\n")
            f.write(f"| Lines removed (open PRs) | {total_lines_removed_open_prs:,} |\n")
            f.write(f"| Overall lines added | {total_lines_added:,} |\n")
            f.write(f"| Overall lines removed | {total_lines_removed:,} |\n")

        # Add note about asterisks
        f.write(f"\n**Note:** Fields marked with * contribute to the total contribution count.\n")

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
            f.write(
                "| Project Key | Repositories | Users | Commits | Pull Requests (Open) | Pull Requests (Closed) | Issues (Open) | Issues (Closed) | Code Reviews | Overall Contribution |\n")
            f.write(
                "|--------------|--------------|-------|---------|----------------------|----------------------|----------------|----------------|--------------|----------------------|\n")
            for _, row in projects_df.sort_values(by=['Overall Contribution'], ascending=False).iterrows():
                repo_list = '<br>'.join([_repo_markdown(repo, url, avatar) for repo, url, avatar in
                                         row['Repositories']])
                user_list = '<br>'.join(
                    [f"<img src='{avatar}' width='12' height='12'> [{user}]({url})" for user, url, avatar in
                     row['Users']])
                f.write(
                    f"| {row['Project Key']} | {repo_list} | {user_list} | {row['Commits']} " + f"| {row['Pull Requests (Open)']} | {row['Pull Requests (Closed)']} | {row['Issues (Open)']} | {row['Issues (Closed)']} | {row['Code Reviews']} | {row['Overall Contribution']} |\n")

            # Sort the user counts by 'Overall Contribution' in descending order and write to the markdown file
            f.write("\n## Summary of Contributions by each user\n\n")
            f.write(
                "| User | Repositories | Commits | Pull Requests (Open) | Pull Requests (Closed) | Issues (Open) | Issues (Closed) | Code Reviews | Overall Contribution |\n")
            f.write(
                "|------|--------------|---------|----------------------|----------------------|----------------|----------------|--------------|----------------------|\n")
            for _, row in users_df.sort_values(by=['Overall Contribution'], ascending=False).iterrows():
                user_avatar = f"<img src='{row['User Avatar']}' width='12' height='12'>"
                repo_list = '<br>'.join([_repo_markdown(repo, url, avatar) for repo, url, avatar in
                                         row['Repositories']])
                f.write(
                    f"| {user_avatar} [{row['User']}]({row['User URL']}) | {repo_list} | {row['Commits']} " + f"| {row['Pull Requests (Open)']} | {row['Pull Requests (Closed)']} | {row['Issues (Open)']} | {row['Issues (Closed)']} | {row['Code Reviews']} | {row['Overall Contribution']} |\n")

            # Sort the detailed contributions by 'Overall Contribution' in descending order and 'User' in ascending order
            # and write to the markdown file
            f.write("\n## Detailed Contributions\n\n")
            if include_line_stats:
                f.write(
                    "| Project Key | Repository | User | Rank | Commits | Pull Requests (Open) | Pull Requests (Closed) | Issues (Open) | Issues (Closed) | Code Reviews | Lines Added (Merged) | Lines Removed (Merged) | Lines Added (Open PRs) | Lines Removed (Open PRs) | Lines Added | Lines Removed | Overall Contribution |\n")
                f.write(
                    "|--------------|------------|------|------|---------|----------------------|----------------------|----------------|----------------|--------------|---------------------|----------------------|----------------------|-------------------------|-------------|---------------|----------------------|\n")
            else:
                f.write(
                    "| Project Key | Repository | User | Rank | Commits | Pull Requests (Open) | Pull Requests (Closed) | Issues (Open) | Issues (Closed) | Code Reviews | Overall Contribution |\n")
                f.write(
                    "|--------------|------------|------|------|---------|----------------------|----------------------|----------------|----------------|--------------|----------------------|\n")
            for _, row in github_data_df.sort_values(by=['User'], ascending=[True]).iterrows():
                user_avatar = f"<img src='{row['User Avatar']}' width='12' height='12'>"
                rank_display = row['Rank'] if row['Rank'] != -1 else 'N/A'
                base = (
                    f"| {row['Project Key']} | {_repo_markdown(row['Repository'], row['Repository URL'], row['Repository Avatar'])}"
                    f" | {user_avatar} [{row['User']}]({row['User URL']}) | {rank_display} | {row['Commits']} |"
                    f" {row['Pull Requests (Open)']} | {row['Pull Requests (Closed)']} | {row['Issues (Open)']} | {row['Issues (Closed)']} | {row['Code Reviews']} |"
                )
                if include_line_stats:
                    base += (
                        f" {row['Lines Added (Merged)']:,} | {row['Lines Removed (Merged)']:,} | {row['Lines Added (Open PRs)']:,} | {row['Lines Removed (Open PRs)']:,} |"
                        f" {row['Lines Added']:,} | {row['Lines Removed']:,} |"
                    )
                base += f" {row['Overall Contribution']} |\n"
                f.write(base)
        if activity_data:
            _write_activity_details(f, activity_data)
    logger.info(f"Markdown report created successfully: {report_filename}")
