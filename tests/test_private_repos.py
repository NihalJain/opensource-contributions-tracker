import json
import logging
import pathlib

import pytest
import requests

import generate_report as g

API = "https://api.github.com"
PUBLIC = "apache/hbase"
PRIVATE = "acme/top-secret-project"
HIDDEN = "apache/not-visible"          # the API answers 404, as it does for a repository the token lacks
SECRET_TITLE = "TOP-SECRET-TITLE"


def info(repo, **extra):
    base = {"full_name": repo, "description": f"about {repo}", "html_url": f"https://github.com/{repo}",
            "private": False, "visibility": "public", "owner": {"avatar_url": f"https://a/{repo.split('/')[0]}"}}
    base.update(extra)
    return base


API_ANSWERS = {
    PUBLIC: info(PUBLIC),
    PRIVATE: info(PRIVATE, private=True, visibility="private"),
    HIDDEN: None,
    "acme/internal": info("acme/internal", private=True, visibility="internal"),
    "acme/no-visibility": {"full_name": "acme/no-visibility"},
}


# ---------------------------------------------------------------- the setting

def test_missing_setting_means_exclude():
    assert g.resolve_private_repos_mode(None) == "exclude"


@pytest.mark.parametrize("value", ["exclude", "include", " Include ", "EXCLUDE"])
def test_accepts_both_modes_case_insensitively(value):
    assert g.resolve_private_repos_mode(value) == value.strip().lower()


@pytest.mark.parametrize("value", ["exclufde", "", True, False, 0, ["exclude"]])
def test_anything_else_is_an_error_not_a_silent_default(value):
    with pytest.raises(ValueError, match="private_repos"):
        g.resolve_private_repos_mode(value)


def test_only_an_explicit_public_answer_counts_as_public():
    assert g.is_public_repo(info(PUBLIC))
    assert g.is_public_repo({"private": False})                       # visibility absent, private says public
    assert not g.is_public_repo(info(PRIVATE, private=True, visibility="private"))
    assert not g.is_public_repo(info("x/y", private=False, visibility="internal"))
    assert not g.is_public_repo({})
    assert not g.is_public_repo({"visibility": "public"})              # no `private` flag at all
    assert not g.is_public_repo(None)


# ---------------------------------------------------------------- looking a repository up

class Response:
    def __init__(self, status, body=None, url=""):
        self.status_code, self._body, self.headers, self.url = status, body or {}, {}, url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(f"{self.status_code} Server Error for url: {self.url}", response=self)

    def json(self):
        return self._body


def fake_requests(monkeypatch, status, body=None):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return Response(status, body, url)

    monkeypatch.setattr(g.requests, "get", get)
    monkeypatch.setattr(g.time, "sleep", lambda s: None)
    return calls


@pytest.mark.parametrize("status", [403, 404, 451])
def test_a_repository_the_token_cannot_see_is_none_after_one_request_and_is_not_logged(monkeypatch, caplog, status):
    calls = fake_requests(monkeypatch, status)
    with caplog.at_level(logging.DEBUG):
        assert g.get_repo_info_if_visible(PRIVATE) is None
    assert len(calls) == 1
    assert PRIVATE not in caplog.text and "Request failed" not in caplog.text


def test_a_server_error_is_raised_so_a_run_never_drops_repositories_quietly(monkeypatch):
    calls = fake_requests(monkeypatch, 500)
    with pytest.raises(RuntimeError, match="500"):
        g.get_repo_info_if_visible(PUBLIC)
    assert len(calls) == 10        # ordinary retries still apply


def test_a_failed_lookup_never_logs_or_raises_the_repository_name(monkeypatch, caplog):
    """The lookup runs before visibility is known, so even its error paths must not name the repository."""
    fake_requests(monkeypatch, 502)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(RuntimeError) as error:
            g.get_repo_info_if_visible(PRIVATE)
    assert PRIVATE not in caplog.text and PRIVATE not in str(error.value)
    assert "top-secret" not in caplog.text and "top-secret" not in str(error.value)


def test_a_dropped_connection_never_logs_or_raises_the_repository_name(monkeypatch, caplog):
    def get(url, **kwargs):
        raise requests.exceptions.ConnectionError(f"HTTPSConnectionPool: Max retries exceeded with url: /repos/{PRIVATE}")

    monkeypatch.setattr(g.requests, "get", get)
    monkeypatch.setattr(g.time, "sleep", lambda s: None)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(RuntimeError) as error:
            g.get_repo_info_if_visible(PRIVATE)
    assert "top-secret" not in caplog.text and "top-secret" not in str(error.value)


def test_other_lookups_still_log_their_url_for_diagnosis(monkeypatch, caplog):
    fake_requests(monkeypatch, 500)
    with caplog.at_level(logging.ERROR):
        with pytest.raises(requests.exceptions.HTTPError):
            g.get_all_pages(f"{API}/repos/{PUBLIC}/commits", {}, with_pagination=False)
    assert PUBLIC in caplog.text


def test_a_visible_repository_returns_its_information(monkeypatch):
    fake_requests(monkeypatch, 200, info(PUBLIC))
    assert g.get_repo_info_if_visible(PUBLIC)["full_name"] == PUBLIC


# ---------------------------------------------------------------- filtering a configuration

def stub_visibility(monkeypatch):
    seen = []

    def lookup(repo):
        seen.append(repo)
        return API_ANSWERS[repo]

    monkeypatch.setattr(g, "get_repo_info_if_visible", lookup)
    return seen


def test_filter_keeps_only_public_repositories_and_counts_the_rest(monkeypatch):
    stub_visibility(monkeypatch)
    config = {"Mine": [PUBLIC, PRIVATE], "Hidden": [HIDDEN], "Corp": ["acme/internal", "acme/no-visibility"]}
    kept, infos, private, unavailable = g.exclude_non_public_repositories(config)
    assert kept == {"Mine": [PUBLIC]}               # projects left empty are dropped
    assert list(infos) == [PUBLIC]
    assert (private, unavailable) == (3, 1)         # private + internal + no visibility field; one 404


def test_filter_looks_each_repository_up_once_whatever_the_case(monkeypatch):
    seen = stub_visibility(monkeypatch)
    monkeypatch.setitem(API_ANSWERS, "APACHE/HBASE", info(PUBLIC))
    g.exclude_non_public_repositories({"A": [PUBLIC], "B": [PUBLIC, "APACHE/HBASE"]})
    assert [r.lower() for r in seen] == [PUBLIC]


# ---------------------------------------------------------------- the whole report

def issue(number, repo, title):
    return {"number": number, "state": "closed", "title": title, "html_url": f"https://github.com/{repo}/pull/{number}",
            "created_at": "2024-02-01T00:00:00Z", "updated_at": "2024-02-02T00:00:00Z", "labels": [],
            "repository_url": f"{API}/repos/{repo}", "pull_request": {"merged_at": "2024-02-02T00:00:00Z"}}


def run_report(monkeypatch, tmp_path, config):
    """Run generate_report() against a GitHub that has a public and a private repo with activity in both."""
    items = [issue(1, PUBLIC, "public change"), issue(2, PRIVATE, SECRET_TITLE)]

    def pages(url, params, *a, meta=None, **k):
        if "/search/issues" in url:
            hits = [] if "reviewed-by" in params["q"] else items
            if meta is not None:
                meta.update(total_count=len(hits), incomplete_results=False)
            return hits
        if "/search/commits" in url and meta is not None:
            meta["total_count"] = 0
        return []

    monkeypatch.setattr(g, "get_all_pages", pages)
    monkeypatch.setattr(g, "get_user_info", lambda u: {"name": u, "avatar_url": "a", "html_url": f"https://github.com/{u}"})
    monkeypatch.setattr(g, "get_repo_info_if_visible", lambda repo: API_ANSWERS[repo])
    monkeypatch.setattr(g, "get_repo_info", lambda repo: API_ANSWERS[repo])
    monkeypatch.setattr(g, "get_top_contributors", lambda *a, **k: [{"login": "ada"}])
    monkeypatch.setattr(g, "get_commits", lambda *a, **k: [])

    conf = tmp_path / "github.json"
    conf.write_text(json.dumps({"start_date": "2024-01-01", "users": ["ada"],
                                "contribution_config": {"line_stats": {"enabled": False}}, **config}))
    out = tmp_path / "out"
    g.generate_report(github_conf_path=str(conf), output_dir=f"{out}/")
    return {p.name: p.read_bytes() for p in pathlib.Path(out).iterdir()}


def everything_written(files, caplog):
    text = b"\n".join(files.values()).decode("utf-8", "ignore")
    return text + "\n" + caplog.text


@pytest.mark.parametrize("config", [
    {"project_to_repo_dict": {"HBase": [PUBLIC], "Secret": [PRIVATE]}},          # listed explicitly
    {},                                                                          # discovered from activity
    {"private_repos": "exclude"},
], ids=["listed", "discovered", "explicit-exclude"])
def test_a_private_repository_appears_nowhere_in_the_files_or_the_logs(monkeypatch, tmp_path, caplog, config):
    with caplog.at_level(logging.DEBUG):
        files = run_report(monkeypatch, tmp_path, config)
    text = everything_written(files, caplog)

    assert PUBLIC in text
    for needle in (PRIVATE, "top-secret", SECRET_TITLE, "acme"):
        assert needle not in text
    assert "Excluded 1 private repositories" in caplog.text


def test_totals_leave_out_the_private_repository(monkeypatch, tmp_path, caplog):
    files = run_report(monkeypatch, tmp_path, {"project_to_repo_dict": {"HBase": [PUBLIC], "Secret": [PRIVATE]}})
    rows = files["github_contribution_data.csv"].decode().strip().splitlines()
    assert len(rows) == 2                            # header + the one public repository
    activity = json.loads(files["github_activity_data.json"])
    assert [r["repo"] for r in activity] == [PUBLIC]
    assert sum(len(r["closed_prs"]) for r in activity) == 1


def test_include_keeps_the_private_repository_and_warns(monkeypatch, tmp_path, caplog):
    with caplog.at_level(logging.DEBUG):
        files = run_report(monkeypatch, tmp_path,
                           {"private_repos": "include", "project_to_repo_dict": {"HBase": [PUBLIC], "Secret": [PRIVATE]}})
    text = everything_written(files, caplog)
    assert PRIVATE in text and SECRET_TITLE in text
    assert "private_repos is 'include'" in caplog.text


def test_a_typo_in_the_setting_stops_the_run_before_any_request(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(g, "get_all_pages", lambda *a, **k: calls.append(a) or [])
    conf = tmp_path / "github.json"
    conf.write_text(json.dumps({"start_date": "2024-01-01", "users": ["ada"], "private_repos": "exclufde",
                                "project_to_repo_dict": {"P": [PUBLIC]}}))
    with pytest.raises(ValueError, match="private_repos"):
        g.generate_report(github_conf_path=str(conf), output_dir=f"{tmp_path}/out/")
    assert calls == []


def test_a_configuration_with_nothing_public_left_fails_with_counts_only(monkeypatch, tmp_path, caplog):
    with pytest.raises(ValueError) as error:
        with caplog.at_level(logging.DEBUG):
            run_report(monkeypatch, tmp_path, {"project_to_repo_dict": {"Secret": [PRIVATE]}})
    assert "1 private" in str(error.value)
    assert PRIVATE not in str(error.value) and PRIVATE not in caplog.text
