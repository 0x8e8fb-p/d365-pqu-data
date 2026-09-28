from __future__ import annotations

import re

from conftest import REPO_ROOT
from d365_pqu.config import CHECK_INTERVAL_MINUTES, UPDATE_CRON

UPDATE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "update-pqu.yml"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"


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
