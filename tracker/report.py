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


_ITEM_TABLE_HEAD = ("| # | Title | Status | Created | Updated | Labels |\n"
                    "|---|-------|--------|---------|---------|--------|\n")


def _pr_status(pr):
    if pr.get('state') == 'open':
        return '🔄 Open'
    if (pr.get('pull_request') or {}).get('merged_at'):
        return '✅ Merged'
    return '❌ Closed'


def _issue_status(issue):
    return '🔓 Open' if issue.get('state') == 'open' else '🔒 Closed'


def _write_items(f, heading, items, status):
    """A table of pull requests or issues, in number order."""
    f.write(f"\n**{heading}**\n\n")
    f.write(_ITEM_TABLE_HEAD)
    for item in sorted(items, key=lambda x: x.get('number', 0)):
        number = item.get('number', '')
        title = item.get('title', '').replace('|', '\\|').replace('\r', '').replace('\n', ' ')
        url = item.get('html_url', '')
        created = item.get('created_at', '')[:10]
        updated = item.get('updated_at', '')[:10]
        labels = ', '.join(lbl['name'] for lbl in item.get('labels', []))
        f.write(f"| [#{number}]({url}) | {title} | {status(item)} | {created} | {updated} | {labels} |\n")


def _group(entries, key):
    """{key value: [entries]} in first-seen order."""
    groups = {}
    for entry in entries:
        groups.setdefault(entry[key], []).append(entry)
    return groups


def _write_project_activity(f, project_key, entries):
    """One project's repositories with their pull requests and issues; nothing if there are none."""
    repo_entries = [
        (entry, entry['open_prs'] + entry['closed_prs'], entry['open_issues'] + entry['closed_issues'])
        for entry in sorted(entries, key=lambda x: x['repo'])
    ]
    if not any(prs or issues for _, prs, issues in repo_entries):
        return

    f.write(f"\n#### {project_key}\n")
    for entry, all_prs, all_issues in repo_entries:
        if not all_prs and not all_issues:
            continue
        f.write(f"\n##### [{entry['repo']}]({entry['repo_url']})\n")
        if all_prs:
            _write_items(f, "Pull Requests", all_prs, _pr_status)
        if all_issues:
            _write_items(f, "Issues", all_issues, _issue_status)


def _write_activity_details(f, activity_data):
    """
    Write the '## Activity Details' section listing every PR and issue per user / project / repo.

    Args:
        f: Open file handle to write into.
        activity_data (list): List of dicts produced by process_github_data, each containing full
                              PR and issue objects for one (user, project, repo) combination.
    """
    f.write("\n## Activity Details\n")
    for user, entries in sorted(_group(activity_data, 'user').items()):
        meta = entries[0]
        f.write(f"\n### <img src='{meta['user_avatar']}' width='20' height='20'>"
                f" [{user}]({meta['user_url']})\n")
        for project_key, project_entries in sorted(_group(entries, 'project_key').items()):
            _write_project_activity(f, project_key, project_entries)


def _repo_markdown(repo, url, avatar):
    """A repository as an avatar and a link; plain text when it has no URL, as for redacted private work."""
    if not isinstance(url, str) or not url:
        return str(repo)
    return f"<img src='{avatar}' width='12' height='12'> [{repo}]({url})"


def _user_markdown(user, url, avatar):
    return f"<img src='{avatar}' width='12' height='12'> [{user}]({url})"


# (metric, summary label, data column) for the counted metrics, in report order
_SUMMARY_METRICS = [
    ('commits', "Number of commits to master", 'Commits'),
    ('open_prs', "Number of pull requests (Open)", 'Pull Requests (Open)'),
    ('closed_prs', "Number of pull requests (Closed)", 'Pull Requests (Closed)'),
    ('open_issues', "Number of issues (Open)", 'Issues (Open)'),
    ('closed_issues', "Number of issues (Closed)", 'Issues (Closed)'),
    ('code_reviews', "Total unique PRs reviewed", 'Code Reviews'),
]
_SUMMARY_LINE_STATS = [
    ("Lines added (commits)", 'Lines Added (Merged)'),
    ("Lines removed (commits)", 'Lines Removed (Merged)'),
    ("Lines added (open PRs)", 'Lines Added (Open PRs)'),
    ("Lines removed (open PRs)", 'Lines Removed (Open PRs)'),
    ("Overall lines added", 'Lines Added'),
    ("Overall lines removed", 'Lines Removed'),
]
# The count columns every summary table shows, in order
_COUNT_CELLS = ['Commits', 'Pull Requests (Open)', 'Pull Requests (Closed)', 'Issues (Open)', 'Issues (Closed)',
                'Code Reviews']
_LINE_CELLS = ['Lines Added (Merged)', 'Lines Removed (Merged)', 'Lines Added (Open PRs)', 'Lines Removed (Open PRs)',
               'Lines Added', 'Lines Removed']


def _write_header(f, start_date, end_date):
    f.write("# OpenSource Contributions Report\n\n")
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    f.write(f"*Report auto-generated on: {current_time} for period {start_date or 'N/A'} to {end_date or 'N/A'}*\n\n")


def _write_summary(f, github_data_df, users_df, projects_df, contribution_config):
    """The overall totals; a * marks the metrics that count towards the contribution total."""
    metrics = {m: config._metric_cfg(contribution_config, m) for m in config.METRICS}
    include_line_stats = config._line_stats_cfg(contribution_config)['enabled']

    f.write("## Overall Summary\n\n")
    f.write("| Metric | Value |\n")
    f.write("|--------|-------|\n")
    f.write(f"| Total number of projects | {len(projects_df)} |\n")
    if len(users_df) > 1:
        f.write(f"| Total number of contributors | {len(users_df)} |\n")
    f.write(f"| Total number of repositories | {len(github_data_df['Repository'].unique())} |\n")
    f.write(f"| Total number of contributions | {github_data_df['Overall Contribution'].sum()} |\n")
    for metric, label, column in _SUMMARY_METRICS:
        cfg = metrics[metric]
        if cfg['enabled']:
            marker = "*" if cfg['count_towards_score'] else ""
            f.write(f"| {label}{marker} | {github_data_df[column].sum()} |\n")
    if include_line_stats:
        for label, column in _SUMMARY_LINE_STATS:
            f.write(f"| {label} | {github_data_df[column].sum():,} |\n")

    f.write("\n**Note:** Fields marked with * contribute to the total contribution count.\n")


def _write_charts(f, output_dir, users_df, projects_df, percentage):
    """Draw the project and user pie charts and show them side by side."""
    project_wise_contribution_fname = "project_wise_contribution.png"
    create_pie_chart("Project wise Contributions", projects_df, 'Project Key',
                     os.path.join(output_dir, project_wise_contribution_fname))

    user_wise_contribution_fname = "user_wise_contribution.png"
    create_pie_chart("User wise Contributions", users_df, 'User',
                     os.path.join(output_dir, user_wise_contribution_fname), percentage)

    f.write(f'\n<div style="display: flex; justify-content: space-around;">\n'
            f'  <img src="{project_wise_contribution_fname}" alt="Project wise Contributions" style="width:45%;">\n'
            f'  <img src="{user_wise_contribution_fname}" alt="User wise Contributions" style="width:45%;">\n'
            f'</div>\n')


def _counts(row, columns):
    return " | ".join(str(row[c]) for c in columns)


def _write_project_table(f, projects_df):
    """Projects, highest overall contribution first."""
    f.write("\n## Summary of Contributions by each project\n\n")
    f.write("| Project Key | Repositories | Users | Commits | Pull Requests (Open) | Pull Requests (Closed) | Issues (Open) | Issues (Closed) | Code Reviews | Overall Contribution |\n")
    f.write("|--------------|--------------|-------|---------|----------------------|----------------------|----------------|----------------|--------------|----------------------|\n")
    for _, row in projects_df.sort_values(by=['Overall Contribution'], ascending=False).iterrows():
        repo_list = '<br>'.join(_repo_markdown(*repo) for repo in row['Repositories'])
        user_list = '<br>'.join(_user_markdown(*user) for user in row['Users'])
        f.write(f"| {row['Project Key']} | {repo_list} | {user_list} | {_counts(row, _COUNT_CELLS)} | {row['Overall Contribution']} |\n")


def _write_user_table(f, users_df):
    """Users, highest overall contribution first."""
    f.write("\n## Summary of Contributions by each user\n\n")
    f.write("| User | Repositories | Commits | Pull Requests (Open) | Pull Requests (Closed) | Issues (Open) | Issues (Closed) | Code Reviews | Overall Contribution |\n")
    f.write("|------|--------------|---------|----------------------|----------------------|----------------|----------------|--------------|----------------------|\n")
    for _, row in users_df.sort_values(by=['Overall Contribution'], ascending=False).iterrows():
        user = _user_markdown(row['User'], row['User URL'], row['User Avatar'])
        repo_list = '<br>'.join(_repo_markdown(*repo) for repo in row['Repositories'])
        f.write(f"| {user} | {repo_list} | {_counts(row, _COUNT_CELLS)} | {row['Overall Contribution']} |\n")


def _write_detailed_table(f, github_data_df, include_line_stats):
    """One row per (project, repository, user), by user; line counts only when line stats are on."""
    f.write("\n## Detailed Contributions\n\n")
    if include_line_stats:
        f.write("| Project Key | Repository | User | Rank | Commits | Pull Requests (Open) | Pull Requests (Closed) | Issues (Open) | Issues (Closed) | Code Reviews | Lines Added (Merged) | Lines Removed (Merged) | Lines Added (Open PRs) | Lines Removed (Open PRs) | Lines Added | Lines Removed | Overall Contribution |\n")
        f.write("|--------------|------------|------|------|---------|----------------------|----------------------|----------------|----------------|--------------|---------------------|----------------------|----------------------|-------------------------|-------------|---------------|----------------------|\n")
    else:
        f.write("| Project Key | Repository | User | Rank | Commits | Pull Requests (Open) | Pull Requests (Closed) | Issues (Open) | Issues (Closed) | Code Reviews | Overall Contribution |\n")
        f.write("|--------------|------------|------|------|---------|----------------------|----------------------|----------------|----------------|--------------|----------------------|\n")
    for _, row in github_data_df.sort_values(by=['User'], ascending=[True]).iterrows():
        rank_display = row['Rank'] if row['Rank'] != -1 else 'N/A'
        cells = [row['Project Key'], _repo_markdown(row['Repository'], row['Repository URL'], row['Repository Avatar']),
                 _user_markdown(row['User'], row['User URL'], row['User Avatar']), rank_display]
        cells += [row[c] for c in _COUNT_CELLS]
        if include_line_stats:
            cells += [f"{row[c]:,}" for c in _LINE_CELLS]
        cells.append(row['Overall Contribution'])
        f.write("| " + " | ".join(str(c) for c in cells) + " |\n")


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
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        logger.info(f"Created output directory: {output_dir}")

    with open(os.path.join(output_dir, report_filename), 'w') as f:
        _write_header(f, start_date, end_date)
        _write_summary(f, github_data_df, users_df, projects_df, contribution_config)
        _write_charts(f, output_dir, users_df, projects_df, percentage)
        if users_df.empty:
            f.write("No contributions found for the given users.\n")
        else:
            _write_project_table(f, projects_df)
            _write_user_table(f, users_df)
            _write_detailed_table(f, github_data_df, config._line_stats_cfg(contribution_config)['enabled'])
        if activity_data:
            _write_activity_details(f, activity_data)
    logger.info(f"Markdown report created successfully: {report_filename}")
