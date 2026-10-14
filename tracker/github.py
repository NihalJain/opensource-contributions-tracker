"""
The GitHub queries the report is built from: commits, pull requests, issues, reviews, line stats,
repository and user details, and contributor ranking.
"""
from . import api
from .log import logger


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
    url = f"{api.GITHUB_API_URL}/search/issues"
    response_data = api.get_all_pages(url, params)

    repositories = set()
    for pr in response_data:
        parts = pr['repository_url'].split('/')
        repo_full_name = f'{parts[-2]}/{parts[-1]}'
        repositories.add(repo_full_name)

    return sorted(repositories, key=str.lower)


def get_top_contributors(repo, per_page=100, wanted=None):
    """
    Retrieve top 500 contributors for a repository, ordered by contribution count.

    Contributors are only needed to read off the rank of the people being tracked, so when `wanted`
    is given paging stops as soon as every one of them has been seen. Ranks of the people found are
    unchanged; the list simply ends sooner.

    Args:
        repo (str): The repository name.
        per_page (int): The number of results per page.
        wanted (iterable): Optional logins to look for, matched case-insensitively. When omitted the
            whole list is fetched, as before.

    Returns:
        list: A list of contributors.
    """
    contributors_url = f"{api.GITHUB_API_URL}/repos/{repo}/contributors"
    if wanted is None:
        return api.get_all_pages(contributors_url, {"per_page": per_page})

    remaining = {str(w).lower() for w in wanted}
    results = []
    for page in range(1, _CONTRIBUTOR_PAGES + 1):
        data = api.get_all_pages(contributors_url, {"per_page": per_page, "page": page}, with_pagination=False)
        if not data:
            break
        results.extend(data)
        remaining -= {str(c.get("login", "")).lower() for c in data}
        if not remaining or len(data) < per_page:
            break
    return results


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
    commits_url = f"{api.GITHUB_API_URL}/repos/{repo}/commits"
    params = {
        "author": user,
        "since": since_date,
        "per_page": per_page
    }
    if until_date:
        params["until"] = until_date
    return api.get_all_pages(commits_url, params)


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
    commit_url = f"{api.GITHUB_API_URL}/repos/{repo}/commits/{commit_sha}"
    params = {}

    try:
        commit_data = api.get_all_pages(commit_url, params, with_pagination=False)
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
    pr_url = f"{api.GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}"
    params = {}

    try:
        pr_data = api.get_all_pages(pr_url, params, with_pagination=False)
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
    url = f"{api.GITHUB_API_URL}/search/issues"
    all_prs = api.get_all_pages(url, params)

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
    url = f"{api.GITHUB_API_URL}/search/issues"
    all_issues = api.get_all_pages(url, params)

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

# GitHub only lists a repository's top 500 contributors: five pages of 100.
_CONTRIBUTOR_PAGES = 5

# Owners per search query: the Search API limits how many operators a query may contain.
_OWNERS_PER_QUERY = 4


def _repo_from_url(repository_url):
    """'https://api.github.com/repos/owner/repo' -> 'owner/repo' (empty string if not a repo URL)."""
    prefix = f"{api.GITHUB_API_URL}/repos/"
    return repository_url[len(prefix):].rstrip('/') if repository_url.startswith(prefix) else ""


def get_user_search_activity(user, repos, start_date, end_date, want_items=True, want_reviews=True):
    """
    Find a user's pull requests, issues and reviewed pull requests across many repositories at once.

    The per-repository searches (`repo:R author:U`) cost three Search API calls for every (user, repo)
    pair, and the Search API is limited to 30 requests a minute. The same results come back from one
    owner-scoped query per user (`author:U user:owner1 user:owner2`), which is then split by repository.

    A result set is only trusted when the API returned all of it. The Search API returns at most 1,000
    results per query without raising an error, so when `total_count` exceeds what came back (or the
    API flags `incomplete_results`) the matching `*_complete` flag is False and the caller must fall
    back to per-repository queries for that user.

    Args:
        user (str): The GitHub username.
        repos (list): Repositories in "owner/repo" form.
        start_date (str): "YYYY-MM-DD".
        end_date (str): "YYYY-MM-DD".
        want_items (bool): Look up pull requests and issues.
        want_reviews (bool): Look up reviewed pull requests.

    Returns:
        dict: `prs` and `issues` ({repo: {'open': [...], 'closed': [...]}}), `reviews` ({repo: count of
        unique pull requests reviewed}), and the booleans `items_complete` and `reviews_complete`.
    """
    by_lower = {r.lower(): r for r in repos}
    result = {
        'prs': {r: {'open': [], 'closed': []} for r in repos},
        'issues': {r: {'open': [], 'closed': []} for r in repos},
        'reviews': {r: 0 for r in repos},
        'items_complete': True,
        'reviews_complete': True,
    }
    if not repos or not (want_items or want_reviews):
        return result

    owners = sorted({r.split('/')[0].lower() for r in repos})
    chunks = [owners[i:i + _OWNERS_PER_QUERY] for i in range(0, len(owners), _OWNERS_PER_QUERY)]
    date_query = f"created:{start_date}..{end_date}"
    url = f"{api.GITHUB_API_URL}/search/issues"

    def search(query):
        meta = {}
        items = api.get_all_pages(url, {"q": query, "per_page": 100}, meta=meta, give_up_over=api.MAX_SEARCH_RESULT_SIZE)
        complete = (not meta.get('incomplete_results', False)
                    and meta.get('total_count', len(items)) <= len(items))
        return items, complete

    if want_items:
        for chunk in chunks:
            scope = ' '.join(f"user:{o}" for o in chunk)
            items, complete = search(f"author:{user} {scope} {date_query}")
            result['items_complete'] = result['items_complete'] and complete
            for item in items:
                repo = by_lower.get(_repo_from_url(item.get('repository_url', '')).lower())
                if repo is None:
                    continue
                group = result['prs'] if item.get('pull_request') else result['issues']
                group[repo]['open' if item.get('state') == 'open' else 'closed'].append(item)

    if want_reviews:
        reviewed = {r: set() for r in repos}
        for chunk in chunks:
            scope = ' '.join(f"user:{o}" for o in chunk)
            items, complete = search(f"type:pr reviewed-by:{user} {scope} {date_query}")
            result['reviews_complete'] = result['reviews_complete'] and complete
            for item in items:
                repo = by_lower.get(_repo_from_url(item.get('repository_url', '')).lower())
                if repo is not None and item.get('number'):
                    reviewed[repo].add(item['number'])
        result['reviews'] = {r: len(numbers) for r, numbers in reviewed.items()}

    return result


# Below this many repositories a commit search costs more than the per-repository listing it saves.
_COMMIT_PRUNING_MIN_REPOS = 4


def get_user_commit_repos(user, repos, start_date, end_date):
    """
    Work out which repositories a user has any commits in, with a single owner-scoped commit search.

    Listing a user's commits is one REST call per (user, repo) pair, so it grows with users times
    repositories while most pairs have no commits at all. This lets the caller skip those pairs. It is
    only a filter: exact counts still come from the list-commits API for the pairs that remain, so
    commits too recent to be indexed by search are still counted in any repository that has older ones.

    Returns None when the answer cannot be trusted (the search was truncated at the API's 1,000-result
    cap, flagged incomplete, or failed) or is not worth a search, meaning "do not prune".

    Args:
        user (str): The GitHub username.
        repos (list): Repositories in "owner/repo" form.
        start_date (str): "YYYY-MM-DD".
        end_date (str): "YYYY-MM-DD".

    Returns:
        set or None: Configured repositories that contain at least one commit by the user.
    """
    if len(repos) < _COMMIT_PRUNING_MIN_REPOS:
        return None

    by_lower = {r.lower(): r for r in repos}
    owners = sorted({r.split('/')[0].lower() for r in repos})
    found = set()
    url = f"{api.GITHUB_API_URL}/search/commits"

    try:
        for i in range(0, len(owners), _OWNERS_PER_QUERY):
            scope = ' '.join(f"user:{o}" for o in owners[i:i + _OWNERS_PER_QUERY])
            query = f"author:{user} {scope} committer-date:{start_date}..{end_date}"
            meta = {}
            items = api.get_all_pages(url, {"q": query, "per_page": 100}, meta=meta, give_up_over=api.MAX_SEARCH_RESULT_SIZE)
            if meta.get('incomplete_results', False) or meta.get('total_count', len(items)) > len(items):
                return None
            for item in items:
                name = (item.get('repository') or {}).get('full_name', '').lower()
                if name in by_lower:
                    found.add(by_lower[name])
    except Exception as e:
        logger.warning(f"Could not search commits for '{user}', listing every repository instead: {e}")
        return None

    return found


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
    url = f"{api.GITHUB_API_URL}/search/issues"
    prs_with_comments = api.get_all_pages(url, params)

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
    user_url = f"{api.GITHUB_API_URL}/users/{user}"
    params = {}
    return api.get_all_pages(user_url, params, with_pagination=False)


def get_repo_info(repo):
    """
    Retrieve repository information for a GitHub repository.

    Args:
        user (str): The GitHub repository of form owner/repo.

    Returns:
        Information about the repository.
    """
    user_url = f"{api.GITHUB_API_URL}/repos/{repo}"
    params = {}
    return api.get_all_pages(user_url, params, with_pagination=False)

