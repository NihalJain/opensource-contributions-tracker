"""process_github_data must use the per-user index, and fall back to per-repo queries when truncated."""
import generate_report as g

API = "https://api.github.com"


def item(number, repo, state="closed", pr=True):
    d = {"number": number, "state": state, "title": f"t{number}", "html_url": f"https://github.com/{repo}/{number}",
         "created_at": "2024-02-01T00:00:00Z", "updated_at": "2024-02-02T00:00:00Z", "labels": [],
         "repository_url": f"{API}/repos/{repo}"}
    if pr:
        d["pull_request"] = {"merged_at": None}
    return d


class Calls:
    def __init__(self):
        self.per_repo = {"prs": 0, "issues": 0, "reviews": 0}
        self.broad = []


def install(monkeypatch, search_items, total_count=None):
    calls = Calls()

    def fake_pages(url, params, *a, meta=None, **k):
        q = params.get("q", "")
        if "/search/issues" in url:
            calls.broad.append(q)
            if meta is not None:
                meta["total_count"] = total_count if total_count is not None else len(search_items)
                meta["incomplete_results"] = False
            return list(search_items)
        return []

    monkeypatch.setattr(g, "get_all_pages", fake_pages)
    monkeypatch.setattr(g, "get_user_info", lambda u: {"name": u, "avatar_url": "a", "html_url": "u"})
    monkeypatch.setattr(g, "get_repo_info", lambda r: {"full_name": r, "description": "", "html_url": "h", "owner": {"avatar_url": "x"}})
    monkeypatch.setattr(g, "get_top_contributors", lambda r: [])
    monkeypatch.setattr(g, "get_commits", lambda *a, **k: [])

    def per_repo_prs(user, repo, *a, **k):
        calls.per_repo["prs"] += 1
        return {"open": [], "closed": []}

    def per_repo_issues(user, repo, *a, **k):
        calls.per_repo["issues"] += 1
        return {"open": [], "closed": []}

    def per_repo_reviews(user, repo, *a, **k):
        calls.per_repo["reviews"] += 1
        return 0

    monkeypatch.setattr(g, "get_user_prs_via_search", per_repo_prs)
    monkeypatch.setattr(g, "get_user_issues_via_search", per_repo_issues)
    monkeypatch.setattr(g, "get_pr_count_reviewed_by_user", per_repo_reviews)
    return calls


CFG = {"line_stats": {"enabled": False}}
PROJECTS = {"P": ["apache/hbase", "apache/phoenix"]}


def run():
    return g.process_github_data("2024-01-01", "2024-12-31", ["ada", "bob"], PROJECTS, CFG)


def test_complete_results_avoid_every_per_repo_search(monkeypatch):
    calls = install(monkeypatch, [item(1, "apache/hbase"), item(2, "apache/phoenix", pr=False)])
    data, activity = run()
    assert calls.per_repo == {"prs": 0, "issues": 0, "reviews": 0}
    assert len(data) == 4  # 2 users x 2 repos


def test_values_come_from_the_index(monkeypatch):
    install(monkeypatch, [item(1, "apache/hbase", "open"), item(2, "apache/hbase", "closed"), item(3, "apache/phoenix", pr=False)])
    data, activity = run()
    hb = [r for r in data if r["User"] == "ada" and r["Repository"] == "apache/hbase"][0]
    assert hb["Pull Requests (Open)"] == 1 and hb["Pull Requests (Closed)"] == 1
    ph = [r for r in data if r["User"] == "ada" and r["Repository"] == "apache/phoenix"][0]
    assert ph["Issues (Closed)"] == 1 and ph["Pull Requests (Open)"] == 0


def test_truncated_search_falls_back_to_per_repo_queries(monkeypatch):
    calls = install(monkeypatch, [item(1, "apache/hbase")], total_count=5000)
    data, activity = run()
    # 2 users x 2 repos, each needing PRs, issues and reviews individually
    assert calls.per_repo == {"prs": 4, "issues": 4, "reviews": 4}


def test_query_count_depends_on_users_not_pairs(monkeypatch):
    calls = install(monkeypatch, [item(1, "apache/hbase")])
    run()
    # per user: one for PRs and issues, one for reviews (a single owner, so a single chunk each)
    assert len(calls.broad) == 4
