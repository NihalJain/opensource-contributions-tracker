import json
import logging
import pathlib
from urllib.parse import quote

import pytest

import check_output_visibility as check
import generate_report as g

API = "https://api.github.com"
PUBLIC = "apache/hbase"
PRIVATE = "secretorg/top-secret-project"
PRIVATE2 = "ada/side-project-x"
SECRET_TITLES = ["TOP-SECRET-TITLE", "other-secret-title", "bob-secret-title"]
NAMES = [PRIVATE, PRIVATE2, "top-secret", "secretorg", "side-project", "Secret Codename"] + SECRET_TITLES


def info(repo, private=False):
    return {"full_name": repo, "description": f"about {repo}", "html_url": f"https://github.com/{repo}",
            "private": private, "visibility": "private" if private else "public",
            "owner": {"avatar_url": f"https://avatars.example/{repo.split('/')[0]}"}}


ANSWERS = {PUBLIC: info(PUBLIC), PRIVATE: info(PRIVATE, True), PRIVATE2: info(PRIVATE2, True)}


def pull(number, repo, title):
    return {"number": number, "state": "closed", "title": title, "html_url": f"https://github.com/{repo}/pull/{number}",
            "created_at": "2024-02-01T00:00:00Z", "updated_at": "2024-02-02T00:00:00Z", "labels": [{"name": "internal"}],
            "repository_url": f"{API}/repos/{repo}", "pull_request": {"merged_at": "2024-02-02T00:00:00Z"}}


ITEMS = {
    "ada": [pull(1, PUBLIC, "public change"), pull(2, PRIVATE, SECRET_TITLES[0]), pull(3, PRIVATE2, SECRET_TITLES[1])],
    "bob": [pull(4, PRIVATE, SECRET_TITLES[2])],
}


class World:
    def __init__(self):
        self.contributor_calls, self.info_calls = [], []


def build(monkeypatch):
    world = World()

    def pages(url, params, *a, meta=None, **k):
        if "/search/issues" in url:
            q = params["q"]
            who = next((u for u in ITEMS if f"author:{u} " in q + " "), None)
            hits = [] if (who is None or "reviewed-by" in q) else ITEMS[who]
            if meta is not None:
                meta.update(total_count=len(hits), incomplete_results=False)
            return hits
        if "/search/commits" in url and meta is not None:
            meta["total_count"] = 0
        return []

    monkeypatch.setattr(g, "get_all_pages", pages)
    monkeypatch.setattr(g, "get_user_info", lambda u: {"name": u, "avatar_url": f"https://a/{u}", "html_url": f"https://github.com/{u}"})
    monkeypatch.setattr(g, "get_repo_info_if_visible", lambda repo: ANSWERS.get(repo.lower()) if repo.lower() in ANSWERS else ANSWERS.get(repo))

    def repo_info(repo):
        world.info_calls.append(repo)
        return ANSWERS[repo]

    def contributors(repo, per_page=100, wanted=None):
        world.contributor_calls.append(repo)
        return [{"login": "ada"}, {"login": "bob"}]

    monkeypatch.setattr(g, "get_repo_info", repo_info)
    monkeypatch.setattr(g, "get_top_contributors", contributors)
    monkeypatch.setattr(g, "get_commits", lambda *a, **k: [])
    return world


def run(tmp_path, config=None):
    conf = tmp_path / "github.json"
    conf.write_text(json.dumps({
        "start_date": "2024-01-01", "users": ["ada", "bob"], "private_repos": "redact",
        "contribution_config": {"line_stats": {"enabled": False}},
        "project_to_repo_dict": {"HBase": [PUBLIC], "Secret Codename": [PRIVATE, PRIVATE2]},
        **(config or {})}))
    out = tmp_path / "out"
    g.generate_report(github_conf_path=str(conf), output_dir=f"{out}/")
    return out


def rows_of(out):
    import csv
    return list(csv.DictReader(open(out / "github_contribution_data.csv")))


def everything(out, caplog):
    text = "\n".join(p.read_bytes().decode("utf-8", "ignore") for p in pathlib.Path(out).iterdir() if p.suffix != ".png")
    return text + "\n" + caplog.text


# ---------------------------------------------------------------- the whole report

def test_private_work_becomes_one_unnamed_row_per_user_and_still_counts(monkeypatch, tmp_path, caplog):
    build(monkeypatch)
    with caplog.at_level(logging.DEBUG):
        out = run(tmp_path)
    rows = {(r["User"], r["Repository"]): r for r in rows_of(out)}

    assert set(rows) == {("ada", PUBLIC), ("ada", g.REDACTED_REPOSITORY), ("bob", g.REDACTED_REPOSITORY)}
    ada_private, bob_private = rows[("ada", g.REDACTED_REPOSITORY)], rows[("bob", g.REDACTED_REPOSITORY)]
    assert ada_private["Project Key"] == bob_private["Project Key"] == g.REDACTED_PROJECT
    assert int(ada_private["Pull Requests (Closed)"]) == 2           # two private repos, summed
    assert int(bob_private["Pull Requests (Closed)"]) == 1
    assert int(ada_private["Overall Contribution"]) == 2             # it counts towards the score
    assert int(rows[("ada", PUBLIC)]["Pull Requests (Closed)"]) == 1
    assert sum(int(r["Overall Contribution"]) for r in rows.values()) == 4


def test_nothing_identifying_is_written_to_any_file_or_log(monkeypatch, tmp_path, caplog):
    build(monkeypatch)
    with caplog.at_level(logging.DEBUG):
        out = run(tmp_path)
    text = everything(out, caplog)
    assert PUBLIC in text
    for needle in NAMES:
        assert needle.lower() not in text.lower(), needle


def test_the_redacted_row_has_no_url_description_avatar_or_rank(monkeypatch, tmp_path):
    build(monkeypatch)
    row = next(r for r in rows_of(run(tmp_path)) if r["Repository"] == g.REDACTED_REPOSITORY)
    assert row["Repository URL"] == row["Repository Description"] == row["Repository Avatar"] == ""
    assert row["Rank"] == "-1"


def test_activity_for_private_work_is_not_written_at_all(monkeypatch, tmp_path):
    build(monkeypatch)
    activity = json.loads((run(tmp_path) / "github_activity_data.json").read_text())
    assert {a["repo"] for a in activity} == {PUBLIC}
    assert sum(len(a["closed_prs"]) for a in activity) == 1           # only the public pull request


def test_private_repositories_are_not_looked_up_for_details_or_contributors(monkeypatch, tmp_path):
    world = build(monkeypatch)
    run(tmp_path)
    assert set(world.contributor_calls) == {PUBLIC}
    assert world.info_calls == []                                      # all of it came from the visibility lookup


def test_the_markdown_report_has_no_empty_link_or_image_for_redacted_work(monkeypatch, tmp_path):
    build(monkeypatch)
    md = (run(tmp_path) / "github_contributions_report.md").read_text()
    assert g.REDACTED_REPOSITORY in md and g.REDACTED_PROJECT in md
    assert "[Private repositories](" not in md
    assert "src='None'" not in md and "src=''" not in md.replace("<img src='' ", "")  # no broken avatar for it


def test_the_public_repositories_checker_accepts_a_redacted_report(monkeypatch, tmp_path, capsys):
    build(monkeypatch)
    out = run(tmp_path)
    assert check.main([str(out)]) == 0
    assert "Checked 1 repositories" in capsys.readouterr().out


def test_the_default_is_still_exclude_and_include_still_names_everything(monkeypatch, tmp_path, caplog):
    build(monkeypatch)
    with caplog.at_level(logging.DEBUG):
        out = run(tmp_path, {"private_repos": "exclude"})
    assert PRIVATE not in everything(out, caplog) and g.REDACTED_REPOSITORY not in everything(out, caplog)
    caplog.clear()
    with caplog.at_level(logging.DEBUG):
        out = run(tmp_path / "again" if (tmp_path / "again").mkdir() is None else tmp_path, {"private_repos": "include"})
    assert PRIVATE in everything(out, caplog)


def test_a_failure_while_redacting_does_not_put_a_private_name_in_the_log(monkeypatch, tmp_path, caplog):
    build(monkeypatch)

    def boom(*a, **k):
        raise RuntimeError(f"cannot list commits for {PRIVATE} (https://api.github.com/repos/{PRIVATE}/commits)")

    monkeypatch.setattr(g, "get_user_search_activity", boom)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(RuntimeError):
            run(tmp_path)
    assert PRIVATE not in caplog.text and "top-secret" not in caplog.text.lower()
    assert "<private>" in caplog.text


# ---------------------------------------------------------------- merging rows

def row(repo, user, **counts):
    base = {"Project Key": "P", "Repository": repo, "Repository URL": f"https://github.com/{repo}",
            "Repository Description": "d", "Repository Avatar": "a", "User": user, "User Avatar": "ua",
            "User URL": f"https://github.com/{user}", "Rank": 3}
    base.update({c: 0 for c in g._COUNT_COLUMNS})
    base.update(counts)
    return base


def test_rows_of_one_user_are_summed_and_other_users_are_kept_apart():
    data = [row("a/one", "ada", Commits=2, **{"Overall Contribution": 2}),
            row("a/two", "ada", Commits=3, **{"Pull Requests (Open)": 1, "Overall Contribution": 4}),
            row("a/one", "bob", Commits=7, **{"Overall Contribution": 7}),
            row("a/public", "ada", Commits=1, **{"Overall Contribution": 1})]
    rows, _ = g.redact_private_rows(data, [], ["a/one", "a/two"])
    redacted = {r["User"]: r for r in rows if r["Repository"] == g.REDACTED_REPOSITORY}
    assert redacted["ada"]["Commits"] == 5 and redacted["ada"]["Pull Requests (Open)"] == 1
    assert redacted["ada"]["Overall Contribution"] == 6 and redacted["bob"]["Commits"] == 7
    assert [r["Repository"] for r in rows].count("a/public") == 1
    assert all(r["Repository"] != "a/one" for r in rows)


def test_matching_private_names_ignores_case_and_leaves_activity_of_public_repos():
    data = [row("Acme/Secret", "ada", Commits=1)]
    activity = [{"repo": "ACME/secret", "user": "ada"}, {"repo": "apache/hbase", "user": "ada"}]
    rows, kept = g.redact_private_rows(data, activity, ["acme/secret"])
    assert [r["Repository"] for r in rows] == [g.REDACTED_REPOSITORY]
    assert kept == [{"repo": "apache/hbase", "user": "ada"}]


# ---------------------------------------------------------------- the log scrubber

def emit(caplog, message):
    with caplog.at_level(logging.DEBUG):
        g.logger.error(message)
    return caplog.records[-1].getMessage()


def test_scrubber_hides_names_in_urls_and_encoded_queries_case_insensitively(caplog):
    g._scrubber.hide([PRIVATE, "secretorg"])
    shown = emit(caplog, f"Request failed: 404 for url: {API}/repos/{PRIVATE.upper()}/commits?q=repo%3A{quote(PRIVATE, safe='')}"
                         f"+user%3Asecretorg")
    assert "secret" not in shown.lower() and shown.count("<private>") == 3


def test_scrubber_leaves_public_names_users_and_short_names_alone(caplog):
    g._scrubber.hide([PRIVATE, "ab"])
    shown = emit(caplog, f"user ada has {PUBLIC} and an ab")
    assert shown == f"user ada has {PUBLIC} and an ab"


def test_each_run_starts_with_nothing_hidden(monkeypatch, tmp_path):
    build(monkeypatch)
    g._scrubber.hide(["apache/hbase"])
    run(tmp_path, {"private_repos": "exclude"})
    assert g._scrubber._pattern is None


def test_the_redacted_row_carries_none_of_the_private_repository_details_it_was_built_from():
    data = [row("secret/one", "ada", Commits=1)]
    data[0].update({"Repository Description": "launch plans", "Repository Avatar": "https://a/secret", "Rank": 4})
    rows, _ = g.redact_private_rows(data, [], ["secret/one"])
    assert len(rows) == 1
    assert rows[0]["Repository URL"] == rows[0]["Repository Description"] == rows[0]["Repository Avatar"] == ""
    assert rows[0]["Rank"] == -1
    assert "secret" not in json.dumps(rows[0]).lower()


# ---------------------------------------------------------------- which names are hidden

def found(public, private):
    return {"public": public, "private": private, "visible": {}, "infos": {}, "unavailable": 0}


def test_an_owner_that_appears_only_through_private_repositories_is_hidden():
    names = g.names_to_hide(found({"P": ["apache/hbase"]}, ["secretorg/x"]), {"P": ["apache/hbase"], "Q": ["secretorg/x"]}, ["ada"])
    assert "secretorg" in names and "secretorg/x" in names


def test_an_owner_that_also_owns_a_public_repository_is_not_hidden():
    names = g.names_to_hide(found({"P": ["apache/hbase"]}, ["apache/secret"]), {"P": ["apache/hbase", "apache/secret"]}, ["ada"])
    assert "apache/secret" in names and "apache" not in names


def test_a_tracked_user_is_not_hidden_even_when_all_their_own_repositories_are_private():
    names = g.names_to_hide(found({}, ["ada/side-project"]), {"ada/side-project": ["ada/side-project"]}, ["ada"])
    assert "ada/side-project" in names and "ada" not in names


def test_a_project_made_only_of_private_repositories_is_hidden_but_a_mixed_one_is_not():
    config = {"Secret Codename": ["acme/a", "acme/b"], "Mixed": ["apache/hbase", "acme/c"]}
    names = g.names_to_hide(found({"Mixed": ["apache/hbase"]}, ["acme/a", "acme/b", "acme/c"]), config, ["ada"])
    assert "Secret Codename" in names and "Mixed" not in names
