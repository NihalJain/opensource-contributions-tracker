"""An owner-scoped commit search tells us which repos a user committed to at all."""
from tracker import api, github

API = "https://api.github.com"


def commit(sha, repo):
    return {"sha": sha, "repository": {"full_name": repo}}


class FakeSearch:
    def __init__(self, items=None, total=None, incomplete=False, boom=False):
        self.items, self.total, self.incomplete, self.boom = items or [], total, incomplete, boom
        self.calls = []

    def __call__(self, url, params, *a, meta=None, **k):
        self.calls.append((url, params["q"]))
        if self.boom:
            raise RuntimeError("search is down")
        if meta is not None:
            meta["total_count"] = self.total if self.total is not None else len(self.items)
            meta["incomplete_results"] = self.incomplete
        return list(self.items)


def repos_for(monkeypatch, fake, repos):
    monkeypatch.setattr(api, "get_all_pages", fake)
    return github.get_user_commit_repos("ada", repos, "2024-01-01", "2024-12-31")


REPOS = ["apache/hbase", "apache/phoenix", "apache/pinot", "apache/kafka"]


def test_returns_the_repos_that_have_commits(monkeypatch):
    fake = FakeSearch([commit("a", "apache/hbase"), commit("b", "apache/hbase"), commit("c", "Apache/Pinot")])
    assert repos_for(monkeypatch, fake, REPOS) == {"apache/hbase", "apache/pinot"}


def test_ignores_commits_in_repos_that_are_not_configured(monkeypatch):
    fake = FakeSearch([commit("a", "someone/else"), commit("b", "apache/hbase")])
    assert repos_for(monkeypatch, fake, REPOS) == {"apache/hbase"}


def test_query_is_scoped_to_owners_and_dated_by_committer_date(monkeypatch):
    fake = FakeSearch()
    repos_for(monkeypatch, fake, ["apache/hbase", "pinot-contrib/docs", "a/x", "b/y"])
    urls = {u for u, _ in fake.calls}
    assert urls == {f"{API}/search/commits"}
    q = fake.calls[0][1]
    assert q.startswith("author:ada ")
    assert "committer-date:2024-01-01..2024-12-31" in q
    for owner in ("apache", "pinot-contrib", "a", "b"):
        assert f"user:{owner}" in q


def test_truncated_results_mean_we_cannot_prune(monkeypatch):
    fake = FakeSearch([commit("a", "apache/hbase")], total=5000)
    assert repos_for(monkeypatch, fake, REPOS) is None


def test_incomplete_results_mean_we_cannot_prune(monkeypatch):
    fake = FakeSearch([commit("a", "apache/hbase")], incomplete=True)
    assert repos_for(monkeypatch, fake, REPOS) is None


def test_a_failing_search_means_we_cannot_prune(monkeypatch):
    assert repos_for(monkeypatch, FakeSearch(boom=True), REPOS) is None


def test_no_commits_at_all_is_a_valid_empty_answer(monkeypatch):
    assert repos_for(monkeypatch, FakeSearch([]), REPOS) == set()


def test_small_repo_lists_are_not_worth_a_search(monkeypatch):
    fake = FakeSearch([commit("a", "apache/hbase")])
    assert repos_for(monkeypatch, fake, ["apache/hbase", "apache/phoenix"]) is None
    assert fake.calls == []
