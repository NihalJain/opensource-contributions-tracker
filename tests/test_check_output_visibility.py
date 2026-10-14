import json

import pytest

import check_output_visibility as check
from tracker import privacy

PUBLIC = "apache/hbase"
PRIVATE = "acme/top-secret-project"

ANSWERS = {
    PUBLIC: {"private": False, "visibility": "public"},
    PRIVATE: {"private": True, "visibility": "private"},
    "gone/deleted": None,                                   # 404
}


@pytest.fixture(autouse=True)
def github(monkeypatch):
    looked_up = []

    def lookup(repo):
        looked_up.append(repo)
        return ANSWERS[repo.lower()] if repo.lower() in ANSWERS else {"private": False, "visibility": "public"}

    monkeypatch.setattr(privacy, "get_repo_info_if_visible", lookup)
    return looked_up


def write_output(tmp_path, *repos):
    """An output directory the way the generator writes it, naming the given repositories."""
    out = tmp_path / "output"
    out.mkdir()
    rows = "\n".join(f"P,{r},ada,1" for r in repos)
    (out / "github_contribution_data.csv").write_text(f"Project,Repository,User,Commits\n{rows}\n")
    (out / "github_activity_data.json").write_text(json.dumps(
        [{"user": "ada", "repo": r, "repo_url": f"https://github.com/{r}",
          "closed_prs": [{"html_url": f"https://github.com/{r}/pull/1", "title": "t"}]} for r in repos]))
    (out / "github_contributions_report.md").write_text(
        "# Report\n" + "\n".join(f"- [{r}](https://github.com/{r}) has [#1](https://github.com/{r}/pull/1)."
                                for r in repos) + "\n")
    (out / "chart.png").write_bytes(b"\x89PNG not text")
    return out


# ---------------------------------------------------------------- what counts as "named"

def test_finds_repositories_in_urls_csv_and_json_fields(tmp_path):
    out = write_output(tmp_path, PUBLIC)
    assert check.repos_in_output(out) == {PUBLIC: {"github_contribution_data.csv", "github_activity_data.json",
                                                   "github_contributions_report.md"}}


def test_ignores_profiles_avatars_and_non_repository_paths(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    (out / "report.md").write_text(
        "[Ada](https://github.com/ada) ![a](https://avatars.githubusercontent.com/u/1?v=4) "
        "[org](https://github.com/orgs/acme/people) [s](https://github.com/sponsors/ada/x) "
        "[r](https://github.com/apache/hbase.git). See https://github.com/apache/hbase-thirdparty.")
    assert set(check.repos_in_output(out)) == {"apache/hbase", "apache/hbase-thirdparty"}


def test_a_name_that_differs_only_by_case_is_one_repository(tmp_path):
    out = tmp_path / "output"
    out.mkdir()
    (out / "a.md").write_text("https://github.com/Apache/HBase and https://github.com/apache/hbase/pull/2")
    assert list(check.repos_in_output(out)) == ["apache/hbase"]


# ---------------------------------------------------------------- the verdict

def test_all_public_passes(tmp_path, capsys):
    out = write_output(tmp_path, PUBLIC)
    assert check.main([str(out)]) == 0
    assert "All of them are public" in capsys.readouterr().out


def test_a_private_repository_fails_and_is_not_named(tmp_path, capsys):
    out = write_output(tmp_path, PUBLIC, PRIVATE)
    assert check.main([str(out)]) == 1
    printed = capsys.readouterr().out
    assert "no longer existing: 1" in printed
    assert PRIVATE not in printed and "top-secret" not in printed
    assert "github_activity_data.json: 1" in printed          # says where, not what


def test_names_are_printed_only_when_asked(tmp_path, capsys):
    out = write_output(tmp_path, PUBLIC, PRIVATE)
    assert check.main([str(out), "--show-names"]) == 1
    assert PRIVATE in capsys.readouterr().out


def test_a_repository_the_token_cannot_see_fails_closed(tmp_path, capsys):
    out = write_output(tmp_path, PUBLIC, "gone/deleted")
    assert check.main([str(out)]) == 1
    assert "deleted" not in capsys.readouterr().out


def test_allow_private_reports_but_passes(tmp_path, capsys):
    out = write_output(tmp_path, PRIVATE)
    assert check.main([str(out), "--allow-private"]) == 0
    printed = capsys.readouterr().out
    assert "no longer existing: 1" in printed and PRIVATE not in printed


def test_a_failed_lookup_is_an_error_not_a_verdict(tmp_path, monkeypatch, capsys):
    def boom(repo):
        raise RuntimeError("Could not check whether a repository is public (HTTP 502)")

    monkeypatch.setattr(privacy, "get_repo_info_if_visible", boom)
    out = write_output(tmp_path, PRIVATE)
    assert check.main([str(out)]) == 2
    printed = capsys.readouterr().out
    assert "HTTP 502" in printed and PRIVATE not in printed


def test_a_name_that_only_a_hand_edit_put_in_the_report_is_still_caught(tmp_path, capsys):
    out = write_output(tmp_path, PUBLIC)
    report = out / "github_contributions_report.md"
    report.write_text(report.read_text() + f"\nAlso worked on https://github.com/{PRIVATE}/issues/9\n")
    assert check.main([str(out)]) == 1
    printed = capsys.readouterr().out
    assert "github_contributions_report.md: 1" in printed and PRIVATE not in printed


def test_a_missing_directory_is_an_error(tmp_path, capsys):
    assert check.main([str(tmp_path / "nope")]) == 2


def test_each_repository_is_looked_up_once(tmp_path, github):
    out = write_output(tmp_path, PUBLIC, PUBLIC.upper())
    check.main([str(out)])
    assert len(github) == 1


def test_an_empty_output_directory_passes(tmp_path, capsys):
    out = tmp_path / "output"
    out.mkdir()
    assert check.main([str(out)]) == 0
    assert "Checked 0 repositories" in capsys.readouterr().out
