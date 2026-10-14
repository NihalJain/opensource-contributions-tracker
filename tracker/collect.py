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


METRICS = ('commits', 'open_prs', 'closed_prs', 'open_issues', 'closed_issues', 'code_reviews')


class _Settings:
    """The contribution_config, resolved once: it is the same for every user and repository."""

    def __init__(self, contribution_config):
        self.metric = {m: config._metric_cfg(contribution_config, m) for m in METRICS}
        line_stats = config._line_stats_cfg(contribution_config)
        self.line_stats = line_stats['enabled']
        self.refactor_threshold = line_stats['refactor_threshold']

    def enabled(self, *metrics):
        return any(self.metric[m]['enabled'] for m in metrics)

    @property
    def need_commits(self):
        # Line stats need the commit list even when commits are not counted
        return self.enabled('commits') or self.line_stats

    @property
    def need_prs(self):
        return self.enabled('open_prs', 'closed_prs') or self.line_stats

    @property
    def need_issues(self):
        return self.enabled('open_issues', 'closed_issues')

    def count(self, metric, items):
        return len(items) if self.metric[metric]['enabled'] else 0

    def score(self, counts):
        """Overall contribution: only enabled metrics with count_towards_score=true."""
        return sum(counts[m] for m in METRICS
                   if self.metric[m]['enabled'] and self.metric[m]['count_towards_score'])


def _date_window(start_date, end_date):
    """The commit listing's `since` and `until` for a `YYYY-MM-DD` range; end_date is included."""
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    if start_dt >= end_dt:
        raise ValueError(f"Start date ({start_date}) must be before end date ({end_date})")
    # Use end-of-day so commits made anywhere on end_date are included
    return start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), end_dt.strftime("%Y-%m-%dT23:59:59Z")


def _user_infos(users):
    infos = {}
    for user in users:
        logger.info(f"Processing user: {user}")
        user_info = github.get_user_info(user)
        infos[user] = {"name": user_info.get('name', user), "avatar_url": user_info.get('avatar_url'),
                       "url": user_info.get('html_url')}
    return infos


def _search_activity(users, all_repos, start_date, end_date, settings):
    """
    One owner-scoped search per user replaces three searches per (user, repo) pair. A user whose
    results were truncated by the Search API falls back to the per-repository queries.
    """
    need_items = settings.need_prs or settings.need_issues
    need_reviews = settings.enabled('code_reviews')
    user_activity = {}
    if need_items or need_reviews:
        logger.info("Searching each user's pull requests, issues and reviews...")
        for user in users:
            user_activity[user] = github.get_user_search_activity(
                user, all_repos, start_date, end_date, want_items=need_items, want_reviews=need_reviews)
            logger.info(f"User '{user}': items {'complete' if user_activity[user]['items_complete'] else 'TRUNCATED, using per-repository queries'}, "
                        f"reviews {'complete' if user_activity[user]['reviews_complete'] else 'TRUNCATED, using per-repository queries'}")
    return user_activity


def _commit_repos(users, all_repos, start_date, end_date, settings):
    """Which repos does each user have commits in? Lets the loop skip the listing for the rest."""
    user_commit_repos = {}
    if settings.need_commits:
        for user in users:
            user_commit_repos[user] = github.get_user_commit_repos(user, all_repos, start_date, end_date)
            known = user_commit_repos[user]
            if known is not None:
                logger.info(f"User '{user}' has commits in {len(known)}/{len(all_repos)} repositories")
    return user_commit_repos


class _RepoDetails:
    """
    Repository details, looked up on first use: they are only needed for repositories someone was
    active in. Details already fetched by the caller are not requested a second time.
    """

    def __init__(self, fetched):
        self._fetched = fetched or {}
        self._details = {}

    def get(self, repo):
        if repo not in self._details:
            info = self._fetched.get(repo)
            if info is None:
                logger.info(f"Fetching details for repository: {repo}")
                info = github.get_repo_info(repo)
            self._details[repo] = {"name": info.get('full_name', repo),
                                   "description": info.get('description'), "url": info.get('html_url'),
                                   "avatar_url": info.get('owner', {}).get('avatar_url')}
        return self._details[repo]


class _Window:
    """The period being reported on, in the two forms the API needs."""

    def __init__(self, start_date, end_date):
        self.start_date, self.end_date = start_date, end_date
        self.since, self.until = _date_window(start_date, end_date)


def _commits(user, repo, window, settings, commit_repos):
    has_commits = commit_repos.get(user)
    if not settings.need_commits or (has_commits is not None and repo not in has_commits):
        return []
    return github.get_commits(user, repo, window.since, window.until)


def _prs(user, repo, window, settings, activity):
    if not settings.need_prs:
        return {'open': [], 'closed': []}
    if activity is not None and activity['items_complete']:
        return activity['prs'][repo]
    logger.info(f"Fetching pull requests for user: {user} in repository: {repo}")
    return github.get_user_prs_via_search(user, repo, window.start_date, window.end_date)


def _issues(user, repo, window, settings, activity):
    if not settings.need_issues:
        return {'open': [], 'closed': []}
    if activity is not None and activity['items_complete']:
        return activity['issues'][repo]
    logger.info(f"Fetching issues for user: {user} in repository: {repo}")
    return github.get_user_issues_via_search(user, repo, window.start_date, window.end_date)


def _reviews(user, repo, window, settings, activity):
    if not settings.enabled('code_reviews'):
        return 0
    if activity is not None and activity['reviews_complete']:
        return activity['reviews'][repo]
    logger.info(f"Fetching count of pull requests reviewed by user: {user} in repository: {repo}")
    return github.get_pr_count_reviewed_by_user(user, repo, window.start_date, window.end_date)


def _line_changes(user, repo, commits, open_prs, settings):
    """
    Lines added and removed in (commits, open PRs). Expensive: one extra API call per commit and
    per open PR.
    """
    if not settings.line_stats:
        logger.info(f"Skipping line-change stats for user {user} in repository: {repo} (line_stats.enabled=false)")
        return {'lines_added': 0, 'lines_removed': 0}, {'lines_added': 0, 'lines_removed': 0}
    logger.info(f"Calculating line changes for user {user} in repository: {repo}")
    in_commits = github.get_user_line_changes(user, repo, commits, settings.refactor_threshold)
    logger.info(f"Calculating line changes in open PRs for user {user} in repository: {repo}")
    in_prs = github.get_user_pr_line_changes(user, repo, open_prs, settings.refactor_threshold)
    return in_commits, in_prs


def _user_in_repo(user, user_info, project_key, repo, window, settings, activity, commit_repos):
    """
    One user's work in one repository: (report row, activity record, was the user active here).
    The repository's URL, description, avatar and the user's rank are filled in later.
    """
    commits = _commits(user, repo, window, settings, commit_repos)
    prs = _prs(user, repo, window, settings, activity)
    issues = _issues(user, repo, window, settings, activity)
    counts = {
        'commits': settings.count('commits', commits),
        'open_prs': settings.count('open_prs', prs['open']),
        'closed_prs': settings.count('closed_prs', prs['closed']),
        'open_issues': settings.count('open_issues', issues['open']),
        'closed_issues': settings.count('closed_issues', issues['closed']),
        'code_reviews': _reviews(user, repo, window, settings, activity),
    }
    in_commits, in_prs = _line_changes(user, repo, commits, prs['open'], settings)

    name = user_info['name'] if user_info['name'] else user
    row = {
        "Project Key": project_key,
        "Repository": repo,
        "Repository URL": None,
        "Repository Description": None,
        "Repository Avatar": None,
        "User": name,
        "User Avatar": user_info['avatar_url'],
        "User URL": user_info['url'],
        "Commits": counts['commits'],
        "Pull Requests (Open)": counts['open_prs'],
        "Pull Requests (Closed)": counts['closed_prs'],
        "Issues (Open)": counts['open_issues'],
        "Issues (Closed)": counts['closed_issues'],
        "Code Reviews": counts['code_reviews'],
        "Lines Added (Merged)": in_commits['lines_added'],
        "Lines Removed (Merged)": in_commits['lines_removed'],
        "Lines Added (Open PRs)": in_prs['lines_added'],
        "Lines Removed (Open PRs)": in_prs['lines_removed'],
        "Lines Added": in_commits['lines_added'] + in_prs['lines_added'],
        "Lines Removed": in_commits['lines_removed'] + in_prs['lines_removed'],
        "Rank": -1,
        "Overall Contribution": settings.score(counts),
    }
    record = {
        "user": name,
        "user_url": user_info['url'],
        "user_avatar": user_info['avatar_url'],
        "project_key": project_key,
        "repo": repo,
        "repo_url": None,
        "open_prs": [_slim_pr(pr) for pr in prs['open']],
        "closed_prs": [_slim_pr(pr) for pr in prs['closed']],
        "open_issues": [_slim_issue(i) for i in issues['open']],
        "closed_issues": [_slim_issue(i) for i in issues['closed']],
    }
    return row, record, sum(counts.values()) > 0


def _repo_lookups(repo, active_users, no_details, repo_details):
    """
    The repository's details and each active user's contributor rank. The repository is looked up
    only if someone was active in it: an idle repository keeps its zero rows (the report filters
    them) with a URL that needs no API call.
    """
    if repo.lower() in no_details:
        return {"description": None, "avatar_url": None, "url": None}, {}
    if active_users:
        details = repo_details.get(repo)
        logger.info(f"Fetching top 500 contributors for: {repo}")
        ranks = {str(c["login"]).lower(): rank for rank, c in
                 enumerate(github.get_top_contributors(repo, wanted=active_users), start=1)}
        return details, ranks
    logger.info(f"No tracked activity in {repo}; skipping repository and contributor lookups")
    return {"description": None, "avatar_url": None, "url": f"https://github.com/{repo}"}, {}


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
        contribution_config (dict): Optional. Which metrics are collected and which count towards the score.
        repo_infos (dict): Optional. Repository information already fetched, keyed by `owner/repo`, so
            it is not requested a second time.
        skip_ranking (set): Optional. Lower-case `owner/repo` names whose details and contributor ranking
            are not looked up, because nothing about those repositories will be written (redacted work).

    Returns:
        tuple: (report rows, activity records), one of each per (project, repository, user).
    """
    settings = _Settings(contribution_config)
    window = _Window(start_date, end_date)

    github_data = []
    activity_data = []  # full PR/issue objects per user+repo for the detail section

    try:
        logger.info("Processing user data...")
        user_info_dict = _user_infos(users)
        repo_details = _RepoDetails(repo_infos)
        no_details = skip_ranking or set()

        all_repos = [repo for repo_list in project_to_repo_dict.values() for repo in repo_list]
        user_activity = _search_activity(users, all_repos, start_date, end_date, settings)
        user_commit_repos = _commit_repos(users, all_repos, start_date, end_date, settings)

        logger.info("Fetching contribution data...")
        for project_key, repo_list in project_to_repo_dict.items():
            logger.info(f"Processing project: {project_key}")
            for repo in repo_list:
                logger.info(f"Processing repository: {repo}")

                # Rows are completed after the users loop, once we know whether anyone was active here
                repo_rows = []
                for user in users:
                    logger.info(f"Processing user: {user}")
                    repo_rows.append(_user_in_repo(user, user_info_dict[user], project_key, repo, window,
                                                   settings, user_activity.get(user), user_commit_repos))

                active_users = {user for (row, _, active), user in zip(repo_rows, users) if active}
                details, ranks = _repo_lookups(repo, active_users, no_details, repo_details)

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
