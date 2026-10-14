"""Repo details and contributor ranks are only fetched for repositories someone was active in."""
import generate_report as g

API = "https://api.github.com"


def person(login):
    return {"login": login}


# ---------------------------------------------------------------- get_top_contributors

class Pages:
    """Serves /contributors pages of 100 from a fixed ranked list and counts the requests."""

    def __init__(self, logins):
        self.logins = logins
        self.requested = []

    def __call__(self, url, params, *a, with_pagination=True, **k):
        assert url.endswith("/contributors")
        if with_pagination:  # the original, fetch-everything behaviour
            self.requested.append("all")
            return [person(l) for l in self.logins]
        page = params["page"]
        self.requested.append(page)
        chunk = self.logins[(page - 1) * 100: page * 100]
        return [person(l) for l in chunk]


def test_without_a_wanted_set_behaviour_is_unchanged(monkeypatch):
    pages = Pages([f"u{i}" for i in range(250)])
    monkeypatch.setattr(g, "get_all_pages", pages)
    assert len(g.get_top_contributors("o/r")) == 250
    assert pages.requested == ["all"]


def test_stops_as_soon_as_everyone_wanted_is_found(monkeypatch):
    logins = [f"u{i}" for i in range(450)]
    pages = Pages(logins)
    monkeypatch.setattr(g, "get_all_pages", pages)
    result = g.get_top_contributors("o/r", wanted={"U5", "u150"})  # case-insensitive
    assert pages.requested == [1, 2]          # u150 is on page 2; pages 3 to 5 are never asked for
    assert [c["login"] for c in result][:3] == ["u0", "u1", "u2"]
    assert len(result) == 200


def test_scans_every_page_when_someone_is_not_in_the_list(monkeypatch):
    pages = Pages([f"u{i}" for i in range(450)])
    monkeypatch.setattr(g, "get_all_pages", pages)
    result = g.get_top_contributors("o/r", wanted={"u1", "nobody"})
    assert pages.requested == [1, 2, 3, 4, 5]
    assert len(result) == 450


def test_a_short_page_ends_the_listing(monkeypatch):
    pages = Pages([f"u{i}" for i in range(30)])
    monkeypatch.setattr(g, "get_all_pages", pages)
    g.get_top_contributors("o/r", wanted={"nobody"})
    assert pages.requested == [1]


def test_ranks_match_the_full_listing(monkeypatch):
    logins = [f"u{i}" for i in range(300)]
    monkeypatch.setattr(g, "get_all_pages", Pages(logins))
    partial = g.get_top_contributors("o/r", wanted={"u120"})
    full = g.get_top_contributors("o/r")
    rank = lambda lst, who: [str(c["login"]).lower() for c in lst].index(who) + 1
    assert rank(partial, "u120") == rank(full, "u120") == 121


# ---------------------------------------------------------------- process_github_data

class World:
    def __init__(self):
        self.info_calls, self.contributor_calls = [], []


def issue(number, repo):
    return {"number": number, "state": "closed", "title": f"t{number}", "html_url": "u",
            "created_at": "2024-02-01T00:00:00Z", "updated_at": "2024-02-02T00:00:00Z", "labels": [],
            "repository_url": f"{API}/repos/{repo}", "pull_request": {"merged_at": None}}


def build(monkeypatch, active_repo_by_user):
    world = World()

    def pages(url, params, *a, meta=None, **k):
        if "/search/issues" in url:
            q = params["q"]
            who = next((u for u in active_repo_by_user if f"author:{u} " in q), None)
            if meta is not None:
                meta["total_count"] = 1 if who else 0
                meta["incomplete_results"] = False
            return [issue(1, active_repo_by_user[who])] if who and "reviewed-by" not in q else []
        if "/search/commits" in url:
            if meta is not None:
                meta["total_count"] = 0
            return []
        return []

    monkeypatch.setattr(g, "get_all_pages", pages)
    monkeypatch.setattr(g, "get_user_info", lambda u: {"name": u, "avatar_url": "a", "html_url": f"https://github.com/{u}"})

    def info(repo):
        world.info_calls.append(repo)
        return {"full_name": repo, "description": f"about {repo}", "html_url": f"https://github.com/{repo}",
                "owner": {"avatar_url": f"https://a/{repo.split('/')[0]}"}}

    def contributors(repo, per_page=100, wanted=None):
        world.contributor_calls.append((repo, sorted(wanted) if wanted is not None else None))
        return [{"login": "bob"}, {"login": "ada"}]

    monkeypatch.setattr(g, "get_repo_info", info)
    monkeypatch.setattr(g, "get_top_contributors", contributors)
    monkeypatch.setattr(g, "get_commits", lambda *a, **k: [])
    return world


CFG = {"line_stats": {"enabled": False}, "commits": {"enabled": False}, "code_reviews": {"enabled": False}}
REPOS = {"P": ["apache/a", "apache/b", "apache/c", "apache/d"]}


def run():
    return g.process_github_data("2024-01-01", "2024-12-31", ["ada", "bob"], REPOS, CFG)


def test_only_repos_with_activity_are_looked_up(monkeypatch):
    world = build(monkeypatch, {"ada": "apache/b"})
    data, activity = run()
    assert world.info_calls == ["apache/b"]
    assert [r for r, _ in world.contributor_calls] == ["apache/b"]


def test_contributors_are_asked_for_only_the_active_users(monkeypatch):
    world = build(monkeypatch, {"ada": "apache/b"})
    run()
    assert world.contributor_calls == [("apache/b", ["ada"])]


def test_every_pair_still_gets_a_row_and_an_activity_record(monkeypatch):
    build(monkeypatch, {"ada": "apache/b"})
    data, activity = run()
    assert len(data) == len(activity) == 8   # 2 users x 4 repos, as before


def test_active_rows_carry_real_repo_details_and_rank(monkeypatch):
    build(monkeypatch, {"ada": "apache/b"})
    data, activity = run()
    row = next(r for r in data if r["User"] == "ada" and r["Repository"] == "apache/b")
    assert row["Repository Description"] == "about apache/b"
    assert row["Repository Avatar"] == "https://a/apache"
    assert row["Rank"] == 2       # ada is second in the stubbed contributor list
    assert row["Pull Requests (Closed)"] == 1


def test_inactive_rows_are_zero_and_keep_a_usable_repo_url(monkeypatch):
    build(monkeypatch, {"ada": "apache/b"})
    data, activity = run()
    idle = next(r for r in data if r["User"] == "bob" and r["Repository"] == "apache/c")
    assert idle["Overall Contribution"] == 0 and idle["Rank"] == -1
    record = next(a for a in activity if a["user"] == "bob" and a["repo"] == "apache/c")
    assert record["repo_url"] == "https://github.com/apache/c"
