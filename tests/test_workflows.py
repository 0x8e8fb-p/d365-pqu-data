from __future__ import annotations

import re

from conftest import REPO_ROOT
from d365_pqu.config import CHECK_INTERVAL_MINUTES, UPDATE_CRON

UPDATE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "update-pqu.yml"
TIMER_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "update-timer.yml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
OPERATIONS_DOC = REPO_ROOT / "docs" / "operations.md"
# The wait timer of the pqu-timer environment, a repository setting (see docs/operations.md).
TIMER_WAIT_MINUTES = 58


def _interval_minutes(cron: str) -> int:
    minute, hour, day, month, weekday = cron.split()
    assert minute.isdigit(), cron
    assert (day, month, weekday) == ("*", "*", "*"), cron
    if hour == "*":
        return 60
    match = re.fullmatch(r"\*/(\d+)", hour)
    assert match, cron
    return 60 * int(match.group(1))


def test_update_schedule_matches_the_published_check_interval() -> None:
    text = UPDATE_WORKFLOW.read_text(encoding="utf-8")
    assert re.findall(r'cron:\s*"([^"]+)"', text) == [UPDATE_CRON]
    assert _interval_minutes(UPDATE_CRON) == CHECK_INTERVAL_MINUTES


def test_update_workflow_builds_the_site_once_after_committing() -> None:
    text = UPDATE_WORKFLOW.read_text(encoding="utf-8")
    assert "--build-site" not in text
    sync = text.index("python -m d365_pqu sync")
    commit = text.index("git commit")
    build = text.index("python -m d365_pqu build-site")
    upload = text.index("upload-pages-artifact")
    assert sync < commit < build < upload
    assert "path: build/site" in text


def test_ci_runs_javascript_and_browser_tests_strictly() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")
    assert 'REQUIRE_NODE: "1"' in text
    assert 'REQUIRE_E2E: "1"' in text
    assert "playwright install --with-deps chromium" in text


def test_hourly_timer_waits_in_an_environment_then_restarts_itself_and_the_update() -> None:
    text = TIMER_WORKFLOW.read_text(encoding="utf-8")
    # Only dispatch starts it: the hourly cadence must not depend on GitHub's cron scheduler.
    assert "schedule:" not in text
    assert "workflow_dispatch:" in text
    # The hour is spent in the environment's wait timer, which holds the job without a runner.
    assert re.search(r"environment:\s*\n\s+name: pqu-timer\s*\n\s+deployment: false", text)
    # One loop: a newer run replaces a pending one and never cancels the waiting one.
    assert "group: pqu-update-timer" in text
    assert "cancel-in-progress: false" in text
    # A run that did not wait stops the loop instead of starting runs back to back.
    match = re.search(r'MIN_WAIT_SECONDS: "(\d+)"', text)
    assert match is not None
    assert 0 < int(match.group(1)) < TIMER_WAIT_MINUTES * 60
    assert TIMER_WAIT_MINUTES < CHECK_INTERVAL_MINUTES
    # The next timer is started before the update, so a failing update never ends the loop.
    assert text.index("dispatch update-timer.yml") < text.index("dispatch update-pqu.yml")
    assert "actions: write" in text


def test_update_workflow_restarts_a_stopped_timer() -> None:
    text = UPDATE_WORKFLOW.read_text(encoding="utf-8")
    job = text[text.index("\n  ensure-timer:") :]
    assert "if: always()" in job
    assert "actions: write" in job
    assert 'select(.status != "completed")' in job
    assert "update-timer.yml/dispatches" in job


def test_operations_guide_describes_the_timer_environment() -> None:
    text = OPERATIONS_DOC.read_text(encoding="utf-8")
    assert "pqu-timer" in text
    assert f"wait_timer={TIMER_WAIT_MINUTES}" in text
