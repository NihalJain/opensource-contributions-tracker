import importlib.util
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / ".github" / "scripts" / "classify_changes.py"
spec = importlib.util.spec_from_file_location("classify_changes", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
classify = module.classify


@pytest.mark.parametrize("files", [
    ["dashboard/app/src/App.tsx"],
    ["dashboard/app/src/App.tsx", "dashboard/README.md", "dashboard/app/package-lock.json"],
    ["README.md"],
    ["README.md", "dashboard/docs/preview-light.png", "LICENSE"],
])
def test_dashboard_and_documentation_changes_need_no_python_checks(files):
    assert classify(files) == {"python": False, "output": False}


@pytest.mark.parametrize("path", [
    "generate_report.py", "check_output_visibility.py", "requirements.txt", "requirements-dev.txt",
    "tests/test_private_repos.py", "input/github.json",
    ".github/workflows/pr.yml", ".github/workflows/main.yml", ".github/workflows/deploy-dashboard.yml",
    ".github/scripts/classify_changes.py",
])
def test_anything_the_python_side_depends_on_runs_the_python_checks(path):
    assert classify([path])["python"] is True


def test_a_change_to_the_committed_report_runs_the_visibility_check_only():
    assert classify(["output/github_contributions_report.md", "output/github_activity_data.json"]) == \
        {"python": False, "output": True}


def test_one_relevant_file_among_many_irrelevant_ones_is_enough():
    files = ["dashboard/app/src/a.tsx"] * 50 + ["README.md", "generate_report.py"]
    assert classify(files)["python"] is True


def test_the_dashboard_workflow_is_a_workflow_and_so_runs_the_workflow_tests():
    # tests/test_workflows.py parses every workflow, so editing one must run the unit tests
    assert classify([".github/workflows/deploy-dashboard.yml"])["python"] is True


@pytest.mark.parametrize("empty", [[], [""], ["", "  "]])
def test_when_the_file_list_is_unknown_everything_runs(empty):
    assert classify(empty) == {"python": True, "output": True}


def test_a_name_that_merely_resembles_a_relevant_one_does_not_count():
    assert classify(["docs/generate_report.py.md", "dashboard/tests/x.ts", "dashboard/input/a.json"]) == \
        {"python": False, "output": False}
