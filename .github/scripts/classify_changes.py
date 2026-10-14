"""
Decide which checks a pull request needs from the files it changes (one path per line on stdin).

Prints `python=true|false` and `output=true|false`, and appends them to $GITHUB_OUTPUT when that is set.

- python: unit tests and the live run of the generator. Needed when the generator, its checker, its
  dependencies, the tests, the input configuration or any workflow changes.
- output: the check that the committed report names only public repositories. Needed when `output/`
  changes (and, with python, whenever the generator might have changed what it writes).

A pull request that only touches the dashboard or the documentation needs neither. When the list of
files is empty, which is what a failed lookup looks like, everything is needed: the safe answer is to run.
"""
import os
import sys

PYTHON_FILES = {"generate_report.py", "check_output_visibility.py", "requirements.txt", "requirements-dev.txt"}
PYTHON_PREFIXES = ("tracker/", "tests/", "input/", ".github/workflows/", ".github/scripts/")
OUTPUT_PREFIXES = ("output/",)


def classify(files):
    files = [f.strip() for f in files if f.strip()]
    if not files:
        return {"python": True, "output": True}
    return {
        "python": any(f in PYTHON_FILES or f.startswith(PYTHON_PREFIXES) for f in files),
        "output": any(f.startswith(OUTPUT_PREFIXES) for f in files),
    }


def main():
    result = classify(sys.stdin.read().splitlines())
    lines = [f"{key}={'true' if value else 'false'}" for key, value in result.items()]
    print("\n".join(lines))
    target = os.environ.get("GITHUB_OUTPUT")
    if target:
        with open(target, "a") as out:
            out.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
