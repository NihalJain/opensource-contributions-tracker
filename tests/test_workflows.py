"""Publishing must be impossible from anywhere but main: a branch carries its own data and must never
replace the live site. This pins that rule so an edit to a workflow cannot quietly remove it."""
import pathlib
import re

import pytest
import yaml

WORKFLOWS = pathlib.Path(__file__).resolve().parent.parent / ".github" / "workflows"
MAIN_ONLY = "github.ref == 'refs/heads/main'"


def publishing_jobs():
    """(workflow file, job name, job) for every job that deploys to Pages or Cloudflare."""
    found = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        for name, job in (yaml.safe_load(path.read_text()).get("jobs") or {}).items():
            steps = job.get("steps") or []
            text = " ".join(str(step.get("uses", "")) + " " + str(step.get("run", "")) for step in steps)
            if "actions/deploy-pages" in text or re.search(r"wrangler(@\S+)?\s+(deploy|publish)", text):
                found.append((path.name, name, job))
    return found


def test_the_workflows_that_publish_are_found():
    # Guards the guard: if a rename made this list empty the checks below would pass for nothing.
    names = {(w, j) for w, j, _ in publishing_jobs()}
    assert ("deploy-dashboard.yml", "pages") in names
    assert ("deploy-dashboard.yml", "cloudflare") in names


@pytest.mark.parametrize("workflow,name,job", publishing_jobs(), ids=lambda v: v if isinstance(v, str) else "")
def test_every_publishing_job_only_runs_on_main(workflow, name, job):
    assert MAIN_ONLY in str(job.get("if", "")), f"{workflow}:{name} can publish from a branch"


def test_the_nightly_workflow_publishes_only_through_the_guarded_workflow():
    nightly = yaml.safe_load((WORKFLOWS / "main.yml").read_text())
    for name, job in nightly["jobs"].items():
        steps = " ".join(str(s.get("run", "")) + str(s.get("uses", "")) for s in job.get("steps") or [])
        assert "deploy-pages" not in steps and "wrangler" not in steps, f"main.yml:{name} publishes directly"


def _steps(workflow, job):
    return yaml.safe_load((WORKFLOWS / workflow).read_text())["jobs"][job]["steps"]


def _index(steps, needle):
    return next(i for i, s in enumerate(steps) if needle in str(s.get("run", "")))


def test_the_nightly_run_checks_the_report_after_generating_it_and_before_committing_it():
    steps = _steps("main.yml", "nightly-job")
    generate = _index(steps, "python generate_report.py")
    check = _index(steps, "check_output_visibility.py")
    commit = _index(steps, "git commit")
    assert generate < check < commit      # a check after the commit would be too late to stop the leak


def test_pull_requests_check_the_committed_report_before_regenerating_it():
    steps = _steps("pr.yml", "pr-test")
    assert _index(steps, "check_output_visibility.py") < _index(steps, "python generate_report.py")
