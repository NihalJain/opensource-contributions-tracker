import json
import logging
import os
import time
import traceback
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import urllib3
from matplotlib.patches import Patch

MAX_SEARCH_RESULT_SIZE = 1000

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

def get_all_pages(url, params, max_retries=10, backoff_factor=0.3, with_pagination=True):
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
    params = dict(params)  # avoid mutating the caller's dict
    results = []
    page = 1
    while True:
        if with_pagination:
            params['page'] = page
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=HEADERS, params=params, proxies=proxies, verify=False)

                # Handle rate-limit responses before raise_for_status so we can inspect headers.
                # 429 = secondary rate limit; 403 with X-RateLimit-Remaining=0 = primary rate limit.
                if response.status_code in (429, 403):
                    rl_remaining = response.headers.get('X-RateLimit-Remaining')
                    is_rate_limited = response.status_code == 429 or rl_remaining == '0'
                    if is_rate_limited:
                        retry_after = response.headers.get('Retry-After')
                        reset_ts = response.headers.get('X-RateLimit-Reset')
                        if retry_after:
                            wait = int(retry_after) + 1
                        elif reset_ts:
                            wait = max(int(reset_ts) - int(time.time()) + 1, 1)
                        else:
                            wait = backoff_factor * (2 ** attempt)
                        logger.warning(f"Rate limited (HTTP {response.status_code}). "
                                       f"Sleeping {wait}s (attempt {attempt + 1}/{max_retries}).")
                        time.sleep(wait)
                        continue  # retry this attempt
                    # Real 403 (auth/forbidden) — fall through to raise_for_status
                response.raise_for_status()
                data = response.json()

                # Proactively back off when the rate-limit window is exhausted so the
                # next request doesn't immediately get a 429/403.
                rl_remaining = response.headers.get('X-RateLimit-Remaining')
                reset_ts = response.headers.get('X-RateLimit-Reset')
                if rl_remaining is not None and int(rl_remaining) == 0 and reset_ts:
                    wait = max(int(reset_ts) - int(time.time()) + 1, 1)
                    logger.warning(f"Rate limit exhausted after this request. Sleeping {wait}s until reset.")
                    time.sleep(wait)

                if not data:
                    return results

                if with_pagination:
                    if url == f"{GITHUB_API_URL}/search/issues":
                        # For search API, check if there are more pages
                        total_count = data.get('total_count', 0)
                        items = data.get('items', [])
                        results.extend(items)
                        # Check if there are more pages based on the total_count and current page
                        # NOTE: In search "Only the first 1000 search results are available"
                        total_until_now = page * params.get('per_page', 100)
                        if len(items) > 0 and total_count > total_until_now and total_until_now < MAX_SEARCH_RESULT_SIZE:
                            page += 1
                            break  # exit retry loop; outer while fetches next page
                        else:
                            return results
                    else:
                        results.extend(data)
                    page += 1
                else:
                    return data
                # Exit retry loop on success
                break
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {e}, attempt {attempt + 1} of {max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(backoff_factor * (2 ** attempt))  # Exponential backoff
                else:
                    logger.critical(f"Max retries exceeded for URL: {url}")
                    raise
    return results


def get_repositories_contributed_to(username: str, per_page: int = 100) -> list[str]:
    """
    Retrieve all repositories a user has contributed to via pull requests.

    Args:
        username: The GitHub username.
        per_page: The number of results per page.

    Returns:
        A sorted list of repository names the user has contributed to.
    """
    params = {
        "q": f"type:pr author:{username}",
        "per_page": per_page
    }
    url = f"{GITHUB_API_URL}/search/issues"
    response_data = get_all_pages(url, params)

    repositories = set()
    for pr in response_data:
        parts = pr['repository_url'].split('/')
        repo_full_name = f'{parts[-2]}/{parts[-1]}'
        repositories.add(repo_full_name)

    return sorted(repositories, key=str.lower)


def get_top_contributors(repo, per_page=100):
    """
    Retrieve top 500 contributors for a repository.

    Args:
        repo (str): The repository name.
        per_page (int): The number of results per page.

    Returns:
        list: A list of contributors.
    """
    params = {
        "per_page": per_page
    }
    contributors_url = f"{GITHUB_API_URL}/repos/{repo}/contributors"
    return get_all_pages(contributors_url, params)


def get_commits(user, repo, since_date, until_date=None, per_page=100):
    """
    Retrieve commits for a specific user in a repository within a date range.

    Args:
        user (str): The GitHub username.
        repo (str): The repository name.
        since_date (str): The start date for retrieving commits in ISO 8601 format.
        until_date (str): The end date for retrieving commits in ISO 8601 format. Optional.
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
    if until_date:
        params["until"] = until_date
    return get_all_pages(commits_url, params)


def get_commit_detailed_stats(repo, commit_sha, refactor_threshold=None):
    """
    Retrieve detailed statistics for a specific commit including lines added/removed.
    Optionally filter out commits that appear to be major refactors based on net change ratio.

    Args:
        repo (str): The repository name.
        commit_sha (str): The commit SHA hash.
        refactor_threshold (float): Minimum ratio of net change to total change to consider meaningful.
                                   If provided, commits below this threshold will be filtered out.

    Returns:
        dict: A dictionary containing commit statistics with 'additions', 'deletions', and 'total'.
    """
    commit_url = f"{GITHUB_API_URL}/repos/{repo}/commits/{commit_sha}"
    params = {}

    try:
        commit_data = get_all_pages(commit_url, params, with_pagination=False)
        stats = commit_data.get('stats', {})
        additions = stats.get('additions', 0)
        deletions = stats.get('deletions', 0)

        # Apply refactor filter if threshold is provided
        if refactor_threshold is not None and additions > 10000 and deletions > 10000:
            net_change = abs(additions - deletions)
            net_change_ratio = max(abs(net_change / additions), abs(net_change / deletions))

            if net_change_ratio < refactor_threshold:
                logger.debug(f"Filtering commit {commit_sha[:8]} in {repo}: "
                             f"net_ratio={net_change_ratio:.3f} < threshold={refactor_threshold} "
                             f"(+{additions}/-{deletions})")
                return {'additions': 0, 'deletions': 0, 'total': 0, 'filtered': True}

        return {
            'additions': additions,
            'deletions': deletions,
            'total': additions + deletions,
            'filtered': False
        }
    except Exception as e:
        logger.warning(f"Failed to get detailed stats for commit {commit_sha} in {repo}: {e}")
        return {'additions': 0, 'deletions': 0, 'total': 0, 'filtered': False}


def get_user_line_changes(user, repo, commits, refactor_threshold=None):
    """
    Calculate total lines added and removed for a user's commits in a repository.
    Only processes master/main branch commits.

    Args:
        user (str): The GitHub username.
        repo (str): The repository name.
        commits (list): List of commits from the user.
        refactor_threshold (float): Minimum ratio of net change to change to consider meaningful.

    Returns:
        dict: A dictionary with 'lines_added', 'lines_removed', and 'filtered_commits'.
    """
    total_additions = 0
    total_deletions = 0
    filtered_commits = 0

    logger.info(f"Processing {len(commits)} commits for line change statistics for user {user} in {repo}")

    for commit in commits:
        commit_sha = commit.get('sha')
        if commit_sha:
            stats = get_commit_detailed_stats(repo, commit_sha, refactor_threshold)
            total_additions += stats['additions']
            total_deletions += stats['deletions']
            if stats.get('filtered', False):
                filtered_commits += 1

    if filtered_commits > 0:
        logger.info(f"Filtered {filtered_commits} refactor commits for user {user} in {repo}")

    return {
        'lines_added': total_additions,
        'lines_removed': total_deletions,
        'filtered_commits': filtered_commits
    }


def get_pr_detailed_stats(repo, pr_number, refactor_threshold=None):
    """
    Retrieve detailed statistics for a specific pull request including lines added/removed.
    Optionally filter out PRs that appear to be major refactors based on net change ratio.

    Args:
        repo (str): The repository name.
        pr_number (int): The pull request number.
        refactor_threshold (float): Minimum ratio of net change to total change to consider meaningful.

    Returns:
        dict: A dictionary containing PR statistics with 'additions', 'deletions', and 'total'.
    """
    pr_url = f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}"
    params = {}

    try:
        pr_data = get_all_pages(pr_url, params, with_pagination=False)
        additions = pr_data.get('additions', 0)
        deletions = pr_data.get('deletions', 0)
        total = additions + deletions

        # Apply refactor filter if threshold is provided
        if refactor_threshold is not None and total > 0:
            net_change = abs(additions - deletions)
            net_change_ratio = net_change / total

            if net_change_ratio < refactor_threshold:
                logger.debug(f"Filtering PR #{pr_number} in {repo}: "
                             f"net_ratio={net_change_ratio:.3f} < threshold={refactor_threshold} "
                             f"(+{additions}/-{deletions})")
                return {'additions': 0, 'deletions': 0, 'total': 0, 'filtered': True}

        return {
            'additions': additions,
            'deletions': deletions,
            'total': total,
            'filtered': False
        }
    except Exception as e:
        logger.warning(f"Failed to get detailed stats for PR #{pr_number} in {repo}: {e}")
        return {'additions': 0, 'deletions': 0, 'total': 0, 'filtered': False}


def get_user_pr_line_changes(user, repo, open_prs, refactor_threshold=None):
    """
    Calculate total lines added and removed for a user's open PRs in a repository.

    Args:
        user (str): The GitHub username.
        repo (str): The repository name.
        open_prs (list): List of open PRs from the user.
        refactor_threshold (float): Minimum ratio of net change to total change to consider meaningful.

    Returns:
        dict: A dictionary with 'lines_added', 'lines_removed', and 'filtered_prs'.
    """
    total_additions = 0
    total_deletions = 0
    filtered_prs = 0

    logger.info(f"Processing {len(open_prs)} open PRs for line change statistics for user {user} in {repo}")

    for pr in open_prs:
        pr_number = pr.get('number')
        if pr_number:
            stats = get_pr_detailed_stats(repo, pr_number, refactor_threshold)
            total_additions += stats['additions']
            total_deletions += stats['deletions']
            if stats.get('filtered', False):
                filtered_prs += 1

    if filtered_prs > 0:
        logger.info(f"Filtered {filtered_prs} refactor PRs for user {user} in {repo}")

    return {
        'lines_added': total_additions,
        'lines_removed': total_deletions,
        'filtered_prs': filtered_prs
    }

def get_user_prs_via_search(user, repo, start_date, end_date=None, per_page=100):
    """
    Retrieve pull requests for a specific user in a repository using GitHub Search API.
    This is more efficient than fetching all PRs and filtering.

    Args:
        user (str): The GitHub username.
        repo (str): The repository name.
        start_date (str): The start date for retrieving PRs in "YYYY-MM-DD" format.
        end_date (str): The end date for retrieving PRs in "YYYY-MM-DD" format. Optional.
        per_page (int): The number of results per page.

    Returns:
        dict: A dictionary with 'open' and 'closed' lists of pull requests.
    """
    # Build date range query
    if end_date:
        date_query = f"created:{start_date}..{end_date}"
    else:
        date_query = f"created:>={start_date}"

    # Search for all PRs by the user in the repository within the date range
    params = {
        "q": f"type:pr repo:{repo} author:{user} {date_query}",
        "per_page": per_page
    }
    url = f"{GITHUB_API_URL}/search/issues"
    all_prs = get_all_pages(url, params)

    # Separate open and closed PRs
    open_prs = []
    closed_prs = []

    for pr in all_prs:
        if pr.get('state') == 'open':
            open_prs.append(pr)
        else:  # closed or merged
            closed_prs.append(pr)

    return {
        'open': open_prs,
        'closed': closed_prs
    }

def get_user_issues_via_search(user, repo, start_date, end_date=None, per_page=100):
    """
    Retrieve issues for a specific user in a repository using GitHub Search API.
    This is more efficient than fetching all issues and filtering.

    Args:
        user (str): The GitHub username.
        repo (str): The repository name.
        start_date (str): The start date for retrieving issues in "YYYY-MM-DD" format.
        end_date (str): The end date for retrieving issues in "YYYY-MM-DD" format. Optional.
        per_page (int): The number of results per page.

    Returns:
        dict: A dictionary with 'open' and 'closed' lists of issues.
    """
    # Build date range query
    if end_date:
        date_query = f"created:{start_date}..{end_date}"
    else:
        date_query = f"created:>={start_date}"

    # Search for all issues by the user in the repository within the date range
    params = {
        "q": f"type:issue repo:{repo} author:{user} {date_query}",
        "per_page": per_page
    }
    url = f"{GITHUB_API_URL}/search/issues"
    all_issues = get_all_pages(url, params)

    # Separate open and closed issues
    open_issues = []
    closed_issues = []

    for issue in all_issues:
        if issue.get('state') == 'open':
            open_issues.append(issue)
        else:  # closed
            closed_issues.append(issue)

    return {
        'open': open_issues,
        'closed': closed_issues
    }

def get_pr_count_reviewed_by_user(user, repo, start_date, end_date=None, per_page=100):
    """
    Retrieve code review comments for a specific user in a repository using GitHub Search API.
    This is more efficient than fetching all PR comments and filtering.

    Args:
        user (str): The GitHub username.
        repo (str): The repository name.
        start_date (str): The start date for retrieving code reviews in "YYYY-MM-DD" format.
        end_date (str): The end date for retrieving code reviews in "YYYY-MM-DD" format. Optional.
        per_page (int): The number of results per page.

    Returns:
        int: The count of code review comments by the user.
    """
    # Build date range query
    if end_date:
        date_query = f"created:{start_date}..{end_date}"
    else:
        date_query = f"created:>={start_date}"

    # Search for PRs reviewed by the user.
    # Note: the GitHub search API filters by PR creation date, not review submission date,
    # so this counts reviews on PRs created within the period as a best-effort approximation.
    params = {
        "q": f"type:pr repo:{repo} reviewed-by:{user} {date_query}",
        "per_page": per_page
    }
    url = f"{GITHUB_API_URL}/search/issues"
    prs_with_comments = get_all_pages(url, params)

    # Count unique PRs reviewed by the user
    unique_prs_reviewed = len(set(pr.get('number') for pr in prs_with_comments if pr.get('number')))

    return unique_prs_reviewed


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


def _metric_cfg(contribution_config, key):
    """Return resolved {enabled, count_towards_score} for a metric key. Defaults to all-on."""
    cfg = (contribution_config or {}).get(key, {})
    return {
        'enabled': cfg.get('enabled', True),
        'count_towards_score': cfg.get('count_towards_score', True),
    }


def _line_stats_cfg(contribution_config):
    """Return resolved {enabled, refactor_threshold} for the line_stats metric."""
    cfg = (contribution_config or {}).get('line_stats', {})
    return {
        'enabled': cfg.get('enabled', True),
        'refactor_threshold': cfg.get('refactor_threshold', None),
    }


def _slim_pr(pr):
    """Return only the fields used by _write_activity_details for a PR item."""
    return {
        'number': pr.get('number'),
        'title': pr.get('title', ''),
        'html_url': pr.get('html_url', ''),
        'state': pr.get('state', ''),
        'created_at': pr.get('created_at', ''),
        'updated_at': pr.get('updated_at', ''),
        'labels': [{'name': lbl['name']} for lbl in pr.get('labels', [])],
        'pull_request': {'merged_at': (pr.get('pull_request') or {}).get('merged_at')},
    }


def _slim_issue(issue):
    """Return only the fields used by _write_activity_details for an issue item."""
    return {
        'number': issue.get('number'),
        'title': issue.get('title', ''),
        'html_url': issue.get('html_url', ''),
        'state': issue.get('state', ''),
        'created_at': issue.get('created_at', ''),
        'updated_at': issue.get('updated_at', ''),
        'labels': [{'name': lbl['name']} for lbl in issue.get('labels', [])],
    }


def process_github_data(start_date, end_date, users, project_to_repo_dict, contribution_config=None):
    """
    Process GitHub data to retrieve commits and pull requests for users and projects.

    Args:
        start_date (str): The start date for retrieving data in "YYYY-MM-DD" format.
        end_date (str): The end date for retrieving data in "YYYY-MM-DD" format.
        users (list): A list of GitHub usernames.
        project_to_repo_dict (dict): A dictionary mapping project keys to repository lists.
        refactor_threshold (float): Minimum ratio of net change to total change to consider meaningful.

    Returns:
        list: A list of dictionaries containing GitHub data.
    """
    # Resolve per-metric configuration once (contribution_config is constant across all users/repos)
    commits_cfg = _metric_cfg(contribution_config, 'commits')
    open_prs_cfg = _metric_cfg(contribution_config, 'open_prs')
    closed_prs_cfg = _metric_cfg(contribution_config, 'closed_prs')
    open_issues_cfg = _metric_cfg(contribution_config, 'open_issues')
    closed_issues_cfg = _metric_cfg(contribution_config, 'closed_issues')
    code_reviews_cfg = _metric_cfg(contribution_config, 'code_reviews')
    line_stats_cfg = _line_stats_cfg(contribution_config)
    refactor_threshold = line_stats_cfg['refactor_threshold']

    # Validate date range
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    if start_dt >= end_dt:
        raise ValueError(f"Start date ({start_date}) must be before end date ({end_date})")

    # Format the dates
    formatted_start_date = start_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    # Use end-of-day so commits made anywhere on end_date are included
    formatted_end_date = end_dt.strftime("%Y-%m-%dT23:59:59Z")

    # Create a list to hold the data
    github_data = []
    activity_data = []  # full PR/issue objects per user+repo for the detail section

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

                logger.info(f"Fetching top 500 contributors for: {repo}")
                top_contributors = get_top_contributors(repo)
                top_contributors_rank = {str(c["login"]).lower(): rank
                                         for rank, c in enumerate(top_contributors, start=1)}

                for user in users:
                    logger.info(f"Processing user: {user}")

                    # Commits — always fetch when line_stats needs the SHA list too
                    need_commits = commits_cfg['enabled'] or line_stats_cfg['enabled']
                    if need_commits:
                        commits = get_commits(user, repo, formatted_start_date, formatted_end_date)
                        commit_count = len(commits) if commits_cfg['enabled'] else 0
                    else:
                        commits = []
                        commit_count = 0

                    # Pull requests
                    need_prs = open_prs_cfg['enabled'] or closed_prs_cfg['enabled'] or line_stats_cfg['enabled']
                    if need_prs:
                        logger.info(f"Fetching pull requests for user: {user} in repository: {repo}")
                        user_prs = get_user_prs_via_search(user, repo, start_date, end_date)
                        open_pr_count = len(user_prs['open']) if open_prs_cfg['enabled'] else 0
                        closed_pr_count = len(user_prs['closed']) if closed_prs_cfg['enabled'] else 0
                    else:
                        user_prs = {'open': [], 'closed': []}
                        open_pr_count = closed_pr_count = 0

                    # Issues
                    need_issues = open_issues_cfg['enabled'] or closed_issues_cfg['enabled']
                    if need_issues:
                        logger.info(f"Fetching issues for user: {user} in repository: {repo}")
                        user_issues = get_user_issues_via_search(user, repo, start_date, end_date)
                        open_issue_count = len(user_issues['open']) if open_issues_cfg['enabled'] else 0
                        closed_issue_count = len(user_issues['closed']) if closed_issues_cfg['enabled'] else 0
                    else:
                        user_issues = {'open': [], 'closed': []}
                        open_issue_count = closed_issue_count = 0

                    # Code reviews
                    if code_reviews_cfg['enabled']:
                        logger.info(f"Fetching count of pull requests reviewed by user: {user} in repository: {repo}")
                        code_review_count = get_pr_count_reviewed_by_user(user, repo, start_date, end_date)
                    else:
                        code_review_count = 0

                    # Line stats — expensive: one extra API call per commit and per open PR
                    if line_stats_cfg['enabled']:
                        logger.info(f"Calculating line changes for user {user} in repository: {repo}")
                        line_changes = get_user_line_changes(user, repo, commits, refactor_threshold)
                        lines_added_commits = line_changes['lines_added']
                        lines_removed_commits = line_changes['lines_removed']

                        logger.info(f"Calculating line changes in open PRs for user {user} in repository: {repo}")
                        pr_line_changes = get_user_pr_line_changes(user, repo, user_prs['open'], refactor_threshold)
                        lines_added_prs = pr_line_changes['lines_added']
                        lines_removed_prs = pr_line_changes['lines_removed']
                    else:
                        logger.info(f"Skipping line-change stats for user {user} in repository: {repo} (line_stats.enabled=false)")
                        lines_added_commits = lines_removed_commits = 0
                        lines_added_prs = lines_removed_prs = 0

                    # Calculate totals
                    total_lines_added = lines_added_commits + lines_added_prs
                    total_lines_removed = lines_removed_commits + lines_removed_prs

                    user_info = user_info_dict[user]
                    repo_info = repo_info_dict[repo]
                    contributor_rank = top_contributors_rank.get(user, -1)

                    # Overall contribution score — only enabled metrics with count_towards_score=true
                    overall_contribution = 0
                    if commits_cfg['enabled'] and commits_cfg['count_towards_score']:
                        overall_contribution += commit_count
                    if open_prs_cfg['enabled'] and open_prs_cfg['count_towards_score']:
                        overall_contribution += open_pr_count
                    if closed_prs_cfg['enabled'] and closed_prs_cfg['count_towards_score']:
                        overall_contribution += closed_pr_count
                    if open_issues_cfg['enabled'] and open_issues_cfg['count_towards_score']:
                        overall_contribution += open_issue_count
                    if closed_issues_cfg['enabled'] and closed_issues_cfg['count_towards_score']:
                        overall_contribution += closed_issue_count
                    if code_reviews_cfg['enabled'] and code_reviews_cfg['count_towards_score']:
                        overall_contribution += code_review_count

                    github_data.append(
                        {
                            "Project Key": project_key,
                            "Repository": repo,
                            "Repository URL": repo_info['url'],
                            "Repository Description": repo_info['description'],
                            "Repository Avatar": repo_info['avatar_url'],
                            "User": user_info['name'] if user_info['name'] else user,
                            "User Avatar": user_info['avatar_url'],
                            "User URL": user_info['url'],
                            "Commits": commit_count,
                            "Pull Requests (Open)": open_pr_count,
                            "Pull Requests (Closed)": closed_pr_count,
                            "Issues (Open)": open_issue_count,
                            "Issues (Closed)": closed_issue_count,
                            "Code Reviews": code_review_count,
                            "Lines Added (Merged)": lines_added_commits,
                            "Lines Removed (Merged)": lines_removed_commits,
                            "Lines Added (Open PRs)": lines_added_prs,
                            "Lines Removed (Open PRs)": lines_removed_prs,
                            "Lines Added": total_lines_added,
                            "Lines Removed": total_lines_removed,
                            "Rank": contributor_rank,
                            "Overall Contribution": overall_contribution
                        }
                    )
                    activity_data.append(
                        {
                            "user": user_info['name'] if user_info['name'] else user,
                            "user_url": user_info['url'],
                            "user_avatar": user_info['avatar_url'],
                            "project_key": project_key,
                            "repo": repo,
                            "repo_url": repo_info['url'],
                            "open_prs": [_slim_pr(pr) for pr in user_prs['open']],
                            "closed_prs": [_slim_pr(pr) for pr in user_prs['closed']],
                            "open_issues": [_slim_issue(i) for i in user_issues['open']],
                            "closed_issues": [_slim_issue(i) for i in user_issues['closed']],
                        }
                    )
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise

    return github_data, activity_data


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


def print_input_json_format():
    """
    Print the format of the input JSON file for OpenSource contributions tracking.

    Returns:
        None
    """
    input_json = {
        "start_date": "YYYY-MM-DD",
        "end_date": "YYYY-MM-DD",
        "contribution_config": {
            "commits":       {"enabled": True, "count_towards_score": True},
            "open_prs":      {"enabled": True, "count_towards_score": True},
            "closed_prs":    {"enabled": True, "count_towards_score": False},
            "open_issues":   {"enabled": True, "count_towards_score": True},
            "closed_issues": {"enabled": True, "count_towards_score": True},
            "code_reviews":  {"enabled": True, "count_towards_score": True},
            "line_stats":    {"enabled": False, "refactor_threshold": 0.1}
        },
        "users": ["user1", "user2"],
        "project_to_repo_dict": {
            "Project 1": ["owner1/repo1", "owner1/repo2"],
            "Project 2": ["owner2/repo3"]
        }
    }
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
        github_data_df, projects_df, users_df = process_data(github_data_df)
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
        commits_cfg = _metric_cfg(contribution_config, 'commits')
        open_prs_cfg = _metric_cfg(contribution_config, 'open_prs')
        closed_prs_cfg = _metric_cfg(contribution_config, 'closed_prs')
        open_issues_cfg = _metric_cfg(contribution_config, 'open_issues')
        closed_issues_cfg = _metric_cfg(contribution_config, 'closed_issues')
        code_reviews_cfg = _metric_cfg(contribution_config, 'code_reviews')
        include_line_stats = _line_stats_cfg(contribution_config)['enabled']

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
                repo_list = '<br>'.join(
                    [f"<img src='{avatar}' width='12' height='12'> [{repo}]({url})" for repo, url, avatar in
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
                repo_list = '<br>'.join(
                    [f"<img src='{avatar}' width='12' height='12'> [{repo}]({url})" for repo, url, avatar in
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
                repo_avatar = f"<img src='{row['Repository Avatar']}' width='12' height='12'>"
                user_avatar = f"<img src='{row['User Avatar']}' width='12' height='12'>"
                rank_display = row['Rank'] if row['Rank'] != -1 else 'N/A'
                base = (
                    f"| {row['Project Key']} | {repo_avatar} [{row['Repository']}]({row['Repository URL']})"
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
        end_date = github_conf_data.get('end_date')
        contribution_config = github_conf_data.get('contribution_config', {})
        users = github_conf_data.get('users', [])
        project_to_repo_dict = github_conf_data.get('project_to_repo_dict', {})
        
        # Set default end_date to tomorrow if not provided
        if not end_date:
            tomorrow = datetime.now() + timedelta(days=1)
            end_date = tomorrow.strftime('%Y-%m-%d')

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
        if not end_date:
            print_input_json_format()
            raise ValueError("End date is required in the input data.")
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
        logger.info(f"End Date: {end_date}")
        logger.info(f"Users: {users}")
        logger.info(f"Project to Repo Dictionary: {project_to_repo_dict}")

        # Create markdown report
        github_data = process_github_data(start_date, end_date, users, project_to_repo_dict, contribution_config)
        github_data_df = convert_to_dataframe(github_data[0])
        process_data_and_create_report(github_data_df, output_dir, report_fname, percentage, True, start_date, end_date, contribution_config, github_data[1])

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise


def generate_report_with_local_data(github_data_csv_path="output/github_contribution_data.csv",
                                    activity_data_json_path="output/github_activity_data.json",
                                    output_dir="output/",
                                    report_fname="github_contributions_report.md", percentage=-1):
    """
    Generate a GitHub contributions report by reading input data, processing it, and creating a markdown report.

    This function reads the input data from a CSV file, processes the GitHub contributions,
    and generates a markdown report with the contributions summary.

    Args:
        github_data_csv_path (str): The path to the GitHub input CSV file. Defaults to "output/github_contribution_data.csv".
        activity_data_json_path (str): The path to the activity data JSON file produced by a previous live run.
            Defaults to "output/github_activity_data.json". Pass None to skip the Activity Details section.
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

        # Load cached activity data (PR / issue objects) if available
        activity_data = None
        if activity_data_json_path and os.path.exists(activity_data_json_path):
            with open(activity_data_json_path, 'r') as af:
                activity_data = json.load(af)
            logger.info(f"Loaded activity data from '{activity_data_json_path}'")
        else:
            logger.warning("Activity data JSON not found; Activity Details section will be omitted from the report.")

        # Create markdown report
        process_data_and_create_report(github_data_df, output_dir, report_fname, percentage,
                                       shouldDump=False, activity_data=activity_data)

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
