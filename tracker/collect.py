"""
Collecting every user's contributions to every configured repository into report rows.
"""
from datetime import datetime

from . import config, github
from .log import logger


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


def process_github_data(start_date, end_date, users, project_to_repo_dict, contribution_config=None,
                        repo_infos=None, skip_ranking=None):
    """
    Process GitHub data to retrieve commits and pull requests for users and projects.

    Every repository in `project_to_repo_dict` ends up in the output, so a caller that must not publish
    private repositories filters them first with `exclude_non_public_repositories`.

    Args:
        start_date (str): The start date for retrieving data in "YYYY-MM-DD" format.
        end_date (str): The end date for retrieving data in "YYYY-MM-DD" format.
        users (list): A list of GitHub usernames.
        project_to_repo_dict (dict): A dictionary mapping project keys to repository lists.
        refactor_threshold (float): Minimum ratio of net change to total change to consider meaningful.
        repo_infos (dict): Optional. Repository information already fetched, keyed by `owner/repo`, so
            it is not requested a second time.
        skip_ranking (set): Optional. Lower-case `owner/repo` names whose details and contributor ranking
            are not looked up, because nothing about those repositories will be written (redacted work).

    Returns:
        list: A list of dictionaries containing GitHub data.
    """
    # Resolve per-metric configuration once (contribution_config is constant across all users/repos)
    commits_cfg = config._metric_cfg(contribution_config, 'commits')
    open_prs_cfg = config._metric_cfg(contribution_config, 'open_prs')
    closed_prs_cfg = config._metric_cfg(contribution_config, 'closed_prs')
    open_issues_cfg = config._metric_cfg(contribution_config, 'open_issues')
    closed_issues_cfg = config._metric_cfg(contribution_config, 'closed_issues')
    code_reviews_cfg = config._metric_cfg(contribution_config, 'code_reviews')
    line_stats_cfg = config._line_stats_cfg(contribution_config)
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
            user_info = github.get_user_info(user)
            user_info_dict[user] = {"name": user_info.get('name', user), "avatar_url": user_info.get('avatar_url'),
                                    "url": user_info.get('html_url')}

        # Repository details are only needed for repositories someone was active in, so they are
        # fetched on first use inside the loop below.
        repo_info_dict = {}
        fetched_repo_infos = repo_infos or {}
        no_details = skip_ranking or set()

        def repo_details(repo):
            if repo not in repo_info_dict:
                info = fetched_repo_infos.get(repo)
                if info is None:
                    logger.info(f"Fetching details for repository: {repo}")
                    info = github.get_repo_info(repo)
                repo_info_dict[repo] = {"name": info.get('full_name', repo),
                                        "description": info.get('description'), "url": info.get('html_url'),
                                        "avatar_url": info.get('owner', {}).get('avatar_url')}
            return repo_info_dict[repo]

        # One owner-scoped search per user replaces three searches per (user, repo) pair. A user whose
        # results were truncated by the Search API falls back to the per-repository queries below.
        need_items = (open_prs_cfg['enabled'] or closed_prs_cfg['enabled'] or line_stats_cfg['enabled']
                      or open_issues_cfg['enabled'] or closed_issues_cfg['enabled'])
        need_reviews = code_reviews_cfg['enabled']
        all_repos = [repo for repo_list in project_to_repo_dict.values() for repo in repo_list]
        user_activity = {}
        if need_items or need_reviews:
            logger.info("Searching each user's pull requests, issues and reviews...")
            for user in users:
                user_activity[user] = github.get_user_search_activity(
                    user, all_repos, start_date, end_date, want_items=need_items, want_reviews=need_reviews)
                logger.info(f"User '{user}': items {'complete' if user_activity[user]['items_complete'] else 'TRUNCATED, using per-repository queries'}, "
                            f"reviews {'complete' if user_activity[user]['reviews_complete'] else 'TRUNCATED, using per-repository queries'}")

        # Which repos does each user have commits in? Lets the loop skip the listing for the rest.
        user_commit_repos = {}
        if commits_cfg['enabled'] or line_stats_cfg['enabled']:
            for user in users:
                user_commit_repos[user] = github.get_user_commit_repos(user, all_repos, start_date, end_date)
                known = user_commit_repos[user]
                if known is not None:
                    logger.info(f"User '{user}' has commits in {len(known)}/{len(all_repos)} repositories")

        # Populate the data list with dictionaries
        logger.info("Fetching contribution data...")
        for project_key, repo_list in project_to_repo_dict.items():
            logger.info(f"Processing project: {project_key}")
            for repo in repo_list:
                logger.info(f"Processing repository: {repo}")

                # Rows are completed after the users loop, once we know whether anyone was active here
                repo_rows = []  # (github row, activity record, user was active in this repo)

                for user in users:
                    logger.info(f"Processing user: {user}")

                    # Commits — always fetch when line_stats needs the SHA list too
                    need_commits = commits_cfg['enabled'] or line_stats_cfg['enabled']
                    has_commits = user_commit_repos.get(user)
                    if need_commits and has_commits is not None and repo not in has_commits:
                        commits = []
                        commit_count = 0
                    elif need_commits:
                        commits = github.get_commits(user, repo, formatted_start_date, formatted_end_date)
                        commit_count = len(commits) if commits_cfg['enabled'] else 0
                    else:
                        commits = []
                        commit_count = 0

                    # Pull requests
                    activity = user_activity.get(user)
                    items_known = activity is not None and activity['items_complete']
                    need_prs = open_prs_cfg['enabled'] or closed_prs_cfg['enabled'] or line_stats_cfg['enabled']
                    if need_prs:
                        if items_known:
                            user_prs = activity['prs'][repo]
                        else:
                            logger.info(f"Fetching pull requests for user: {user} in repository: {repo}")
                            user_prs = github.get_user_prs_via_search(user, repo, start_date, end_date)
                        open_pr_count = len(user_prs['open']) if open_prs_cfg['enabled'] else 0
                        closed_pr_count = len(user_prs['closed']) if closed_prs_cfg['enabled'] else 0
                    else:
                        user_prs = {'open': [], 'closed': []}
                        open_pr_count = closed_pr_count = 0

                    # Issues
                    need_issues = open_issues_cfg['enabled'] or closed_issues_cfg['enabled']
                    if need_issues:
                        if items_known:
                            user_issues = activity['issues'][repo]
                        else:
                            logger.info(f"Fetching issues for user: {user} in repository: {repo}")
                            user_issues = github.get_user_issues_via_search(user, repo, start_date, end_date)
                        open_issue_count = len(user_issues['open']) if open_issues_cfg['enabled'] else 0
                        closed_issue_count = len(user_issues['closed']) if closed_issues_cfg['enabled'] else 0
                    else:
                        user_issues = {'open': [], 'closed': []}
                        open_issue_count = closed_issue_count = 0

                    # Code reviews
                    if code_reviews_cfg['enabled']:
                        if activity is not None and activity['reviews_complete']:
                            code_review_count = activity['reviews'][repo]
                        else:
                            logger.info(f"Fetching count of pull requests reviewed by user: {user} in repository: {repo}")
                            code_review_count = github.get_pr_count_reviewed_by_user(user, repo, start_date, end_date)
                    else:
                        code_review_count = 0

                    # Line stats — expensive: one extra API call per commit and per open PR
                    if line_stats_cfg['enabled']:
                        logger.info(f"Calculating line changes for user {user} in repository: {repo}")
                        line_changes = github.get_user_line_changes(user, repo, commits, refactor_threshold)
                        lines_added_commits = line_changes['lines_added']
                        lines_removed_commits = line_changes['lines_removed']

                        logger.info(f"Calculating line changes in open PRs for user {user} in repository: {repo}")
                        pr_line_changes = github.get_user_pr_line_changes(user, repo, user_prs['open'], refactor_threshold)
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
                    was_active = (commit_count + open_pr_count + closed_pr_count + open_issue_count
                                  + closed_issue_count + code_review_count) > 0

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

                    row = (
                        {
                            "Project Key": project_key,
                            "Repository": repo,
                            "Repository URL": None,
                            "Repository Description": None,
                            "Repository Avatar": None,
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
                            "Rank": -1,
                            "Overall Contribution": overall_contribution
                        }
                    )
                    record = (
                        {
                            "user": user_info['name'] if user_info['name'] else user,
                            "user_url": user_info['url'],
                            "user_avatar": user_info['avatar_url'],
                            "project_key": project_key,
                            "repo": repo,
                            "repo_url": None,
                            "open_prs": [_slim_pr(pr) for pr in user_prs['open']],
                            "closed_prs": [_slim_pr(pr) for pr in user_prs['closed']],
                            "open_issues": [_slim_issue(i) for i in user_issues['open']],
                            "closed_issues": [_slim_issue(i) for i in user_issues['closed']],
                        }
                    )
                    repo_rows.append((row, record, was_active))

                # Look the repository up only if someone was active in it. An idle repository keeps its
                # zero rows (the report filters them) with a URL that needs no API call.
                active_users = {user for (row, _, active), user in zip(repo_rows, users) if active}
                if repo.lower() in no_details:
                    details = {"description": None, "avatar_url": None, "url": None}
                    ranks = {}
                elif active_users:
                    details = repo_details(repo)
                    logger.info(f"Fetching top 500 contributors for: {repo}")
                    ranks = {str(c["login"]).lower(): rank for rank, c in
                             enumerate(github.get_top_contributors(repo, wanted=active_users), start=1)}
                else:
                    details = {"description": None, "avatar_url": None, "url": f"https://github.com/{repo}"}
                    ranks = {}
                    logger.info(f"No tracked activity in {repo}; skipping repository and contributor lookups")

                for (row, record, active), user in zip(repo_rows, users):
                    row["Repository URL"] = details["url"]
                    row["Repository Description"] = details["description"]
                    row["Repository Avatar"] = details["avatar_url"]
                    row["Rank"] = ranks.get(user, -1)
                    record["repo_url"] = details["url"]
                    github_data.append(row)
                    activity_data.append(record)
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise

    return github_data, activity_data
