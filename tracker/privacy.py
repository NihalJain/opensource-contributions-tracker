"""
Keeping private repositories out of a report that is normally public.

The generated report is normally committed to a public repository and published as a public site,
so private repositories are left out unless the configuration says `"private_repos": "include"`, or
`"redact"`, which counts their work without naming anything.
"""
import requests

from . import api


PRIVATE_REPOS_MODES = ('exclude', 'include', 'redact')

# Answers that mean "this token cannot see that repository"; retrying them cannot change the result.
REPO_NOT_VISIBLE_STATUSES = (403, 404, 451)


def resolve_private_repos_mode(value):
    """Validate the `private_repos` setting. Missing means 'exclude'; anything unrecognised is an error."""
    if value is None:
        return 'exclude'
    mode = value.strip().lower() if isinstance(value, str) else value
    if mode not in PRIVATE_REPOS_MODES:
        raise ValueError(f"'private_repos' must be one of {', '.join(repr(m) for m in PRIVATE_REPOS_MODES)}, "
                         f"got {value!r}")
    return mode


def is_public_repo(info):
    """True only when GitHub explicitly says the repository is public; anything else is not trusted."""
    return isinstance(info, dict) and info.get('private') is False and info.get('visibility', 'public') == 'public'


def get_repo_info_if_visible(repo):
    """
    Retrieve repository information, or None when GitHub says this token cannot see the repository.

    Any other failure (network, rate limit, server error) is raised, so a run stops instead of
    quietly dropping repositories. This runs before visibility is known, so neither the log nor the
    raised error carries the repository name or URL.
    """
    try:
        return api.get_all_pages(f"{api.GITHUB_API_URL}/repos/{repo}", {}, with_pagination=False,
                             no_retry_on=REPO_NOT_VISIBLE_STATUSES, redact_url=True)
    except requests.exceptions.RequestException as e:
        status = getattr(getattr(e, 'response', None), 'status_code', None)
        if status in REPO_NOT_VISIBLE_STATUSES:
            return None
        what = f"HTTP {status}" if status else type(e).__name__
        raise RuntimeError(f"Could not check whether a repository is public ({what})") from None


def classify_repositories(project_to_repo_dict):
    """
    Look every repository up once and sort it as public, private or unavailable (not visible to the token).

    A repository the token cannot see, or whose visibility is missing from the answer, is treated as
    private rather than public: nothing is assumed public without GitHub saying so. Names are never
    logged here: CI logs of a public repository are public too.

    Returns a dict:
        public:      {project: [repos]} the public repositories, projects left empty dropped
        visible:     {project: [repos]} public and private ones, for work that counts private repos
        infos:       {repo: API info} for every repository the token can see
        private:     [repos] visible to the token but not public, once each
        unavailable: number of repositories the token cannot see
    """
    verdicts = {}  # repo name (lower case) -> (info or None, 'public' | 'private' | 'unavailable')
    for repos in project_to_repo_dict.values():
        for repo in repos:
            key = repo.lower()
            if key in verdicts:
                continue
            info = get_repo_info_if_visible(repo)
            if info is None:
                verdicts[key] = (None, 'unavailable')
            elif is_public_repo(info):
                verdicts[key] = (info, 'public')
            else:
                verdicts[key] = (info, 'private')

    public, visible, infos, private = {}, {}, {}, []
    seen_private = set()
    for project_key, repos in project_to_repo_dict.items():
        keep_public, keep_visible = [], []
        for repo in repos:
            info, kind = verdicts[repo.lower()]
            if kind == 'unavailable':
                continue
            infos[repo] = info
            keep_visible.append(repo)
            if kind == 'public':
                keep_public.append(repo)
            elif repo.lower() not in seen_private:
                seen_private.add(repo.lower())
                private.append(repo)
        if keep_public:
            public[project_key] = keep_public
        if keep_visible:
            visible[project_key] = keep_visible
    unavailable = sum(1 for _, kind in verdicts.values() if kind == 'unavailable')
    return {"public": public, "visible": visible, "infos": infos, "private": private, "unavailable": unavailable}


def exclude_non_public_repositories(project_to_repo_dict):
    """
    Remove every repository that is not known to be public, before anything is searched or logged.

    Projects left without repositories are dropped.

    Returns:
        tuple: (the filtered dictionary, {repo: API info} for the repositories kept,
                number of private repositories removed, number removed because they were not visible).
    """
    found = classify_repositories(project_to_repo_dict)
    kept = {repo for repos in found["public"].values() for repo in repos}
    infos = {repo: info for repo, info in found["infos"].items() if repo in kept}
    return found["public"], infos, len(found["private"]), found["unavailable"]


def names_to_hide(found, project_to_repo_dict, users):
    """
    Every name a log line must not carry once private work is being redacted: the private repositories,
    the owners that appear only through them (an owner shows up in search queries), and projects made
    only of private repositories. The tracked users and anything that is also public are not hidden.
    """
    private = found["private"]
    public_repos = {r.lower() for repos in found["public"].values() for r in repos}
    public_owners = {r.split('/')[0].lower() for r in public_repos}
    private_keys = {r.lower() for r in private}

    hide = set(private)
    hide |= {r.split('/')[0] for r in private
             if r.split('/')[0].lower() not in public_owners and r.split('/')[0].lower() not in users}
    for project_key, repos in project_to_repo_dict.items():
        lowered = {r.lower() for r in repos}
        if lowered & private_keys and not lowered & public_repos:
            hide.add(project_key)
    return hide


# What private work becomes under "private_repos": "redact". Nothing in these names identifies a
# repository, and "Private repositories" has no owner/repo shape, so check_output_visibility.py does
# not read it as one.
REDACTED_PROJECT = "Private work"
REDACTED_REPOSITORY = "Private repositories"
_COUNT_COLUMNS = ["Commits", "Pull Requests (Open)", "Pull Requests (Closed)", "Issues (Open)",
                  "Issues (Closed)", "Code Reviews", "Lines Added (Merged)", "Lines Removed (Merged)",
                  "Lines Added (Open PRs)", "Lines Removed (Open PRs)", "Lines Added", "Lines Removed",
                  "Overall Contribution"]


def redact_private_rows(github_data, activity_data, private_repos):
    """
    Replace each user's rows in private repositories with one row that identifies nothing.

    The counts are summed per user, so they still count towards that user's totals and score. The rows
    carry no repository name, URL, description, avatar or rank, and the activity records of private
    repositories (titles, links, labels) are dropped altogether: private work is counts only.

    Returns:
        tuple: (rows, activity records), with the private repositories' own removed.
    """
    private = {repo.lower() for repo in private_repos}
    rows = [row for row in github_data if row["Repository"].lower() not in private]
    merged = {}
    for row in github_data:
        if row["Repository"].lower() not in private:
            continue
        key = (row["User"], row["User URL"])
        if key not in merged:
            merged[key] = {"Project Key": REDACTED_PROJECT, "Repository": REDACTED_REPOSITORY,
                           "Repository URL": "", "Repository Description": "", "Repository Avatar": "",
                           "User": row["User"], "User Avatar": row["User Avatar"], "User URL": row["User URL"],
                           **{column: 0 for column in _COUNT_COLUMNS}, "Rank": -1}
        for column in _COUNT_COLUMNS:
            merged[key][column] += row.get(column) or 0
    activity = [record for record in activity_data if record["repo"].lower() not in private]
    return rows + list(merged.values()), activity
