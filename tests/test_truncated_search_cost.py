"""A search that is over the Search API's cap must cost one request, not ten."""
from tracker import api, github


class FakeResponse:
    status_code = 200
    headers = {}

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class SearchServer:
    """A /search endpoint with `total` results, 100 to a page, that records the pages requested."""

    def __init__(self, total):
        self.total = total
        self.pages = []

    def __call__(self, url, headers=None, params=None, **k):
        page = params["page"]
        self.pages.append(page)
        start = (page - 1) * 100
        n = max(0, min(100, self.total - start))
        return FakeResponse({"total_count": self.total, "incomplete_results": False,
                             "items": [{"number": start + i} for i in range(n)]})


def test_without_a_limit_it_pages_up_to_the_cap(monkeypatch):
    server = SearchServer(total=5000)
    monkeypatch.setattr(api.SESSION, "get", server)
    meta = {}
    results = api.get_all_pages("https://api.github.com/search/issues", {"q": "x", "per_page": 100}, meta=meta)
    assert len(results) == 1000 and server.pages == list(range(1, 11))   # today's behaviour, unchanged
    assert meta["total_count"] == 5000


def test_over_the_limit_it_stops_after_the_first_page(monkeypatch):
    server = SearchServer(total=5000)
    monkeypatch.setattr(api.SESSION, "get", server)
    meta = {}
    results = api.get_all_pages("https://api.github.com/search/issues", {"q": "x", "per_page": 100},
                              meta=meta, give_up_over=1000)
    assert server.pages == [1]
    assert meta["total_count"] == 5000          # the caller can still see why it gave up
    assert len(results) == 100


def test_under_the_limit_it_still_fetches_everything(monkeypatch):
    server = SearchServer(total=250)
    monkeypatch.setattr(api.SESSION, "get", server)
    meta = {}
    results = api.get_all_pages("https://api.github.com/search/issues", {"q": "x", "per_page": 100},
                              meta=meta, give_up_over=1000)
    assert len(results) == 250 and server.pages == [1, 2, 3]
    assert meta["total_count"] == 250


def test_exactly_at_the_limit_is_still_complete(monkeypatch):
    server = SearchServer(total=1000)
    monkeypatch.setattr(api.SESSION, "get", server)
    results = api.get_all_pages("https://api.github.com/search/issues", {"q": "x", "per_page": 100}, give_up_over=1000)
    assert len(results) == 1000


def test_the_broad_user_queries_ask_to_give_up_early(monkeypatch):
    seen = []

    def spy(url, params, *a, meta=None, **k):
        seen.append(k.get("give_up_over"))
        if meta is not None:
            meta["total_count"] = 0
        return []

    monkeypatch.setattr(api, "get_all_pages", spy)
    github.get_user_search_activity("ada", ["apache/a", "apache/b"], "2024-01-01", "2024-12-31", True, True)
    github.get_user_commit_repos("ada", [f"apache/r{i}" for i in range(5)], "2024-01-01", "2024-12-31")
    assert seen and all(v == api.MAX_SEARCH_RESULT_SIZE for v in seen)
