from tracker import api, github


class Reply:
    status_code, headers = 200, {}

    def raise_for_status(self):
        pass

    def json(self):
        return {"full_name": "apache/hbase"}


def test_every_request_goes_through_the_one_shared_session(monkeypatch):
    """A new connection per request costs a TLS handshake each time; the session keeps one open."""
    through_session = []

    def session_get(url, **kwargs):
        through_session.append(url)
        return Reply()

    def module_level_get(*args, **kwargs):
        raise AssertionError("requests.get opens a new connection for every call")

    monkeypatch.setattr(api.SESSION, "get", session_get)
    monkeypatch.setattr(api.requests, "get", module_level_get)

    github.get_repo_info("apache/hbase")
    github.get_repo_info("apache/hadoop")

    assert len(through_session) == 2
    assert isinstance(api.SESSION, api.requests.Session)
