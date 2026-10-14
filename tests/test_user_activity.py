"""One owner-scoped search per user replaces three searches per (user, repo)."""
import generate_report as g

API = "https://api.github.com"


def issue(number, repo, state="closed", pr=True):
    item = {"number": number, "state": state, "title": f"item {number}", "repository_url": f"{API}/repos/{repo}"}
    if pr:
        item["pull_request"] = {"url": f"{API}/repos/{repo}/pulls/{number}"}
    return item


class FakeSearch:
    """Stands in for get_all_pages: answers search queries from a table and records them."""

    def __init__(self, responses, total_counts=None, incomplete=False):
        self.responses = responses  # {predicate-substring: [items]}
        self.total_counts = total_counts or {}
        self.incomplete = incomplete
        self.queries = []

    def __call__(self, url, params, *args, meta=None, **kwargs):
        q = params["q"]
        self.queries.append(q)
        items = []
        for needle, found in self.responses.items():
            if needle in q:
                items = found
                break
        if meta is not None:
            meta["total_count"] = self.total_counts.get(q, len(items))
            meta["incomplete_results"] = self.incomplete
        return items


def run(monkeypatch, fake, repos, **kwargs):
    monkeypatch.setattr(g, "get_all_pages", fake)
    return g.get_user_search_activity("ada", repos, "2024-01-01", "2024-12-31", **kwargs)


def test_splits_prs_and_issues_by_repo_and_state(monkeypatch):
    fake = FakeSearch({"author:ada": [
        issue(1, "apache/hbase", "open"), issue(2, "apache/hbase", "closed"),
        issue(3, "apache/hbase", "open", pr=False), issue(4, "apache/hbase", "closed", pr=False),
        issue(5, "apache/phoenix", "closed"),
    ]})
    a = run(monkeypatch, fake, ["apache/hbase", "apache/phoenix"], want_items=True, want_reviews=False)

    assert [p["number"] for p in a["prs"]["apache/hbase"]["open"]] == [1]
    assert [p["number"] for p in a["prs"]["apache/hbase"]["closed"]] == [2]
    assert [i["number"] for i in a["issues"]["apache/hbase"]["open"]] == [3]
    assert [i["number"] for i in a["issues"]["apache/hbase"]["closed"]] == [4]
    assert [p["number"] for p in a["prs"]["apache/phoenix"]["closed"]] == [5]
    assert a["items_complete"] is True


def test_matches_configured_repos_case_insensitively_and_ignores_others(monkeypatch):
    fake = FakeSearch({"author:ada": [issue(1, "Apache/HBase"), issue(2, "someone/else")]})
    a = run(monkeypatch, fake, ["apache/hbase"], want_items=True, want_reviews=False)
    assert list(a["prs"]) == ["apache/hbase"]
    assert "someone/else" not in a["prs"]


def test_counts_unique_reviewed_prs_per_repo(monkeypatch):
    fake = FakeSearch({"reviewed-by:ada": [issue(7, "apache/hbase"), issue(7, "apache/hbase"), issue(8, "apache/hbase"), issue(9, "apache/phoenix")]})
    a = run(monkeypatch, fake, ["apache/hbase", "apache/phoenix"], want_items=False, want_reviews=True)
    assert a["reviews"] == {"apache/hbase": 2, "apache/phoenix": 1}
    assert a["reviews_complete"] is True


def test_scopes_the_query_to_the_owners_of_the_configured_repos(monkeypatch):
    fake = FakeSearch({})
    run(monkeypatch, fake, ["apache/hbase", "apache/phoenix", "pinot-contrib/docs"], want_items=True, want_reviews=True)
    assert len(fake.queries) == 2  # one for PRs and issues, one for reviews
    for q in fake.queries:
        assert "user:apache" in q and "user:pinot-contrib" in q
        assert "created:2024-01-01..2024-12-31" in q
    assert any(q.startswith("author:ada ") for q in fake.queries)
    assert any("type:pr" in q and "reviewed-by:ada" in q for q in fake.queries)


def test_many_owners_are_split_into_several_queries(monkeypatch):
    repos = [f"org{i}/repo" for i in range(9)]
    fake = FakeSearch({})
    run(monkeypatch, fake, repos, want_items=True, want_reviews=False)
    assert len(fake.queries) == 3  # ceil(9 owners / 4 per query)
    seen = {o for q in fake.queries for o in (w[5:] for w in q.split() if w.startswith("user:"))}
    assert seen == {f"org{i}" for i in range(9)}


def test_truncated_results_are_reported_incomplete(monkeypatch):
    q_items = None  # the exact query string is whatever the implementation builds
    fake = FakeSearch({"author:ada": [issue(1, "apache/hbase")]})
    original = fake.__call__

    def capped(url, params, *a, meta=None, **k):
        items = original(url, params, *a, meta=meta, **k)
        if meta is not None:
            meta["total_count"] = 5000  # more matches than the Search API will return
        return items

    monkeypatch.setattr(g, "get_all_pages", capped)
    a = g.get_user_search_activity("ada", ["apache/hbase"], "2024-01-01", "2024-12-31", want_items=True, want_reviews=False)
    assert a["items_complete"] is False


def test_incomplete_results_flag_is_reported_incomplete(monkeypatch):
    fake = FakeSearch({"author:ada": [issue(1, "apache/hbase")]}, incomplete=True)
    a = run(monkeypatch, fake, ["apache/hbase"], want_items=True, want_reviews=False)
    assert a["items_complete"] is False


def test_asks_for_nothing_that_is_not_needed(monkeypatch):
    fake = FakeSearch({})
    run(monkeypatch, fake, ["apache/hbase"], want_items=False, want_reviews=False)
    assert fake.queries == []


def test_no_repos_means_no_queries(monkeypatch):
    fake = FakeSearch({})
    a = run(monkeypatch, fake, [], want_items=True, want_reviews=True)
    assert fake.queries == []
    assert a["prs"] == {} and a["reviews"] == {}
