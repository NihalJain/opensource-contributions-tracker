import time

import pytest
import requests

import generate_report as g

URL = f"{g.GITHUB_API_URL}/repos/apache/hbase"
SECONDARY = {"message": "You have exceeded a secondary rate limit. Please wait a few minutes before you try again."}


class Reply:
    def __init__(self, status=200, headers=None, body=None):
        self.status_code, self.headers, self._body = status, headers or {}, body if body is not None else {"ok": 1}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code}", response=self)

    def json(self):
        return self._body


def serve(monkeypatch, *replies):
    """Answer successive requests from `replies`; return (requests made, seconds slept)."""
    queue, made, slept = list(replies), [], []

    def get(url, **kwargs):
        made.append(url)
        return queue.pop(0) if queue else Reply()

    monkeypatch.setattr(g.SESSION, "get", get)
    monkeypatch.setattr(g.time, "sleep", slept.append)
    return made, slept


def fetch():
    return g.get_all_pages(URL, {}, with_pagination=False)


# ---------------------------------------------------------------- what the wait is, and why

def test_retry_after_is_honoured_even_though_the_allowance_is_not_exhausted(monkeypatch):
    made, slept = serve(monkeypatch, Reply(403, {"Retry-After": "17", "X-RateLimit-Remaining": "12"}, SECONDARY))
    assert fetch() == {"ok": 1}
    assert slept == [18] and len(made) == 2


def test_a_secondary_limit_without_retry_after_waits_a_minute_not_a_fraction_of_a_second(monkeypatch):
    # The response GitHub really sent for /search/commits: 403, no Retry-After, 13 of 30 left.
    headers = {"X-RateLimit-Remaining": "13", "X-RateLimit-Limit": "30", "X-RateLimit-Resource": "search"}
    made, slept = serve(monkeypatch, Reply(403, headers, SECONDARY))
    assert fetch() == {"ok": 1}
    assert slept == [60]
    assert len(made) == 2          # one retry, after the wait: nothing was spent hammering


def test_a_secondary_limit_that_continues_is_waited_out_for_longer_each_time(monkeypatch):
    refusal = lambda: Reply(403, {"X-RateLimit-Remaining": "9"}, SECONDARY)
    made, slept = serve(monkeypatch, *[refusal() for _ in range(6)])
    assert fetch() == {"ok": 1}
    assert slept == [60, 120, 240, 300, 300, 300]      # doubles, then is capped


def test_the_primary_limit_still_waits_until_the_window_resets(monkeypatch):
    reset = int(time.time()) + 30
    made, slept = serve(monkeypatch, Reply(403, {"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": str(reset)},
                                           {"message": "API rate limit exceeded"}))
    fetch()
    assert 30 <= slept[0] <= 32


def test_a_429_without_any_detail_is_treated_as_a_secondary_limit(monkeypatch):
    made, slept = serve(monkeypatch, Reply(429, {}, {}))
    fetch()
    assert slept == [60]


def test_retry_after_on_a_429_is_honoured(monkeypatch):
    made, slept = serve(monkeypatch, Reply(429, {"Retry-After": "5"}, {}))
    fetch()
    assert slept == [6]


def test_an_unreadable_retry_after_does_not_crash_and_falls_back_to_the_message(monkeypatch):
    made, slept = serve(monkeypatch, Reply(403, {"Retry-After": "soon"}, SECONDARY))
    assert fetch() == {"ok": 1}
    assert slept == [60]


def test_a_secondary_429_does_not_wait_for_the_primary_reset_time(monkeypatch):
    far = int(time.time()) + 3000       # core limit resets in 50 minutes; remaining is not zero
    made, slept = serve(monkeypatch, Reply(429, {"X-RateLimit-Remaining": "4000", "X-RateLimit-Reset": str(far)}, {}))
    fetch()
    assert slept == [60]


# ---------------------------------------------------------------- what is not a rate limit

def test_an_ordinary_forbidden_keeps_the_ordinary_backoff(monkeypatch):
    forbidden = lambda: Reply(403, {"X-RateLimit-Remaining": "4000"}, {"message": "Resource not accessible by integration"})
    made, slept = serve(monkeypatch, *[forbidden() for _ in range(10)])
    with pytest.raises(requests.exceptions.HTTPError):
        fetch()
    assert len(made) == 10
    assert slept == [0.3 * 2 ** i for i in range(9)]   # the unchanged ordinary backoff, no rate-limit wait


def test_success_is_untouched(monkeypatch):
    made, slept = serve(monkeypatch, Reply(200, {"X-RateLimit-Remaining": "50"}, {"full_name": "apache/hbase"}))
    assert fetch() == {"full_name": "apache/hbase"}
    assert slept == [] and len(made) == 1
