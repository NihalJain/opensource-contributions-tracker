"""
Turning the collected rows into a DataFrame and the per-project and per-user totals.
"""
import pandas as pd

from .log import logger


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
    filtered_df = github_data_df[(github_data_df['Commits'] > 0) | (github_data_df['Pull Requests (Open)'] > 0) | (
                github_data_df['Pull Requests (Closed)'] > 0) | (github_data_df['Issues (Open)'] > 0) | (
                                             github_data_df['Issues (Closed)'] > 0) | (
                                             github_data_df['Code Reviews'] > 0)]
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
    project_df = filtered_df.groupby('Project Key')[
        ['Commits', 'Pull Requests (Open)', 'Pull Requests (Closed)', 'Issues (Open)', 'Issues (Closed)',
         'Code Reviews', 'Lines Added (Merged)', 'Lines Removed (Merged)',
         'Lines Added (Open PRs)', 'Lines Removed (Open PRs)', 'Lines Added', 'Lines Removed']].sum().reset_index()
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
    # Sum the per-row Overall Contribution so the contribution_config flags are respected
    overall_by_project = filtered_df.groupby('Project Key')['Overall Contribution'].sum()
    project_df['Overall Contribution'] = project_df['Project Key'].map(overall_by_project)
    project_df = project_df[project_df['Overall Contribution'] > 0]
    logger.info("Grouped by 'Project Key' and calculated overall contributions")

    users_df = filtered_df.groupby('User')[
        ['Commits', 'Pull Requests (Open)', 'Pull Requests (Closed)', 'Issues (Open)', 'Issues (Closed)',
         'Code Reviews', 'Lines Added (Merged)', 'Lines Removed (Merged)',
         'Lines Added (Open PRs)', 'Lines Removed (Open PRs)', 'Lines Added', 'Lines Removed']].sum().reset_index()
    users_df['Repositories'] = filtered_df.groupby('User').apply(
        lambda x: list(zip(x['Repository'], x['Repository URL'], x['Repository Avatar']))).reset_index(drop=True).apply(
        lambda x: list(set(x)))
    users_df['Repositories'] = users_df['Repositories'].apply(lambda x: sorted(x, key=lambda y: y[0]))
    users_df['Repository Count'] = filtered_df.groupby('User')['Repository'].nunique().reset_index()['Repository']
    user_meta = filtered_df.drop_duplicates('User').set_index('User')[['User URL', 'User Avatar']]
    users_df['User URL'] = users_df['User'].map(user_meta['User URL'])
    users_df['User Avatar'] = users_df['User'].map(user_meta['User Avatar'])
    # Sum the per-row Overall Contribution so the contribution_config flags are respected
    overall_by_user = filtered_df.groupby('User')['Overall Contribution'].sum()
    users_df['Overall Contribution'] = users_df['User'].map(overall_by_user)
    users_df = users_df[users_df['Overall Contribution'] > 0]
    logger.info("Grouped by 'User' and calculated overall contributions")

    return project_df, users_df

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
