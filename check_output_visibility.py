"""
Fail when the generated report names a repository that is not public.

The report in `output/` is committed to a public repository and published as a public site. The
generator leaves private repositories out by default; this check is the independent last line of
defence for everything that bypasses that: a hand-edited file, output generated locally with a token
that can see private repositories, an older generator, or `private_repos: include` set by accident.

Every repository named in the output files is looked up, and each one must be reported public by the
GitHub API. A repository the token cannot see counts as not public (fail closed), which also means a
repository that has since been deleted is reported until it is removed from the output.

Because CI logs of a public repository are public, the default output carries counts and file names
only. Run it locally with `--show-names` to see which repositories were found.

Usage:
    python check_output_visibility.py [output_dir] [--show-names] [--allow-private]

Exit status: 0 all public, 1 something is not public, 2 the check could not be completed.
"""
import argparse
import csv
import json
import pathlib
import re
import sys

from tracker import privacy

# owner/repo as it appears in any GitHub URL: pull request links, repository links, `repo_url` fields
REPO_URL = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")
TEXT_SUFFIXES = {".csv", ".json", ".md"}
# first path segments on github.com that are not owners, so `orgs/x/...` is not read as a repository
NOT_OWNERS = {"orgs", "sponsors", "settings", "marketplace", "features", "topics", "collections", "apps",
              "users", "about", "pricing", "login", "notifications", "explore"}


def _clean(owner, repo):
    repo = repo.rstrip(".")
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not repo or owner.lower() in NOT_OWNERS:
        return None
    return f"{owner}/{repo}"


def repos_in_file(path):
    """The `owner/repo` names a file mentions, found in URLs and in the report's repository fields."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    found = {name for name in (_clean(o, r) for o, r in REPO_URL.findall(text)) if name}

    if path.suffix == ".csv":
        for row in csv.DictReader(text.splitlines()):
            value = (row.get("Repository") or "").strip()
            if "/" in value:
                found.add(value)
    elif path.suffix == ".json":
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        for record in data if isinstance(data, list) else []:
            if isinstance(record, dict):
                value = str(record.get("repo") or "").strip()
                if "/" in value:
                    found.add(value)
    return found


def repos_in_output(output_dir):
    """{repo (lower case) -> {file name, ...}} for every repository the output files name."""
    where = {}
    for path in sorted(pathlib.Path(output_dir).iterdir()):
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            for name in repos_in_file(path):
                where.setdefault(name.lower(), set()).add(path.name)
    return where


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fail if the report names a repository that is not public.")
    parser.add_argument("output_dir", nargs="?", default="output")
    parser.add_argument("--show-names", action="store_true",
                        help="print the repository names; do not use in CI, whose logs are public")
    parser.add_argument("--allow-private", action="store_true",
                        help="report non-public repositories but exit 0, for output that is published privately")
    args = parser.parse_args(argv)

    if not pathlib.Path(args.output_dir).is_dir():
        print(f"Cannot check: '{args.output_dir}' is not a directory.")
        return 2
    where = repos_in_output(args.output_dir)

    not_public = {}
    try:
        for repo in sorted(where):
            if not privacy.is_public_repo(privacy.get_repo_info_if_visible(repo)):
                not_public[repo] = where[repo]
    except Exception as e:  # the lookup error carries no repository name, see get_repo_info_if_visible
        print(f"Cannot check: could not look up a repository ({e}).")
        return 2

    print(f"Checked {len(where)} repositories named in the output files.")
    if not not_public:
        print("All of them are public.")
        return 0

    per_file = {}
    for files in not_public.values():
        for name in files:
            per_file[name] = per_file.get(name, 0) + 1
    print(f"Not public, not visible to this token, or no longer existing: {len(not_public)}")
    for name, count in sorted(per_file.items()):
        print(f"  {args.output_dir.rstrip('/')}/{name}: {count}")
    if args.show_names:
        for repo in not_public:
            print(f"  - {repo}")
    else:
        print("Names are withheld because CI logs are public; run locally with --show-names to see them.")

    if args.allow_private:
        print("--allow-private is set: continuing.")
        return 0
    print("Do not publish this output. Regenerate it with private_repos set to exclude, or remove "
          "the repositories listed above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
