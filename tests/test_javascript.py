from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from conftest import REPO_ROOT
from d365_pqu.insights import DATE_FLAG_FIELDS

JS_TESTS = REPO_ROOT / "tests" / "js"
HOST_ZONES = ("UTC", "America/Los_Angeles", "Asia/Kolkata", "Pacific/Kiritimati")


def _node() -> str:
    node = shutil.which("node")
    if node:
        return node
    if os.environ.get("REQUIRE_NODE") == "1":
        pytest.fail("REQUIRE_NODE=1 but node is not installed")
    pytest.skip("node is not installed")


def _test_files() -> list[str]:
    files = sorted(str(path) for path in JS_TESTS.glob("*.test.js"))
    assert files, "no JavaScript unit tests were found"
    return files


@pytest.mark.parametrize("zone", HOST_ZONES)
def test_javascript_unit_tests_pass_in_every_host_zone(zone: str) -> None:
    node = _node()
    environment = {**os.environ, "TZ": zone}
    result = subprocess.run(
        [node, "--test", *_test_files()],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
        env=environment,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_every_core_module_has_a_unit_test() -> None:
    core = REPO_ROOT / "src" / "d365_pqu" / "static" / "js" / "core"
    tested = "\n".join(Path(name).read_text(encoding="utf-8") for name in _test_files())
    for module in sorted(core.glob("*.js")):
        assert f"core/{module.name}" in tested, f"{module.name} has no Node unit test"


def test_date_flag_fields_match_the_pipeline() -> None:
    """The browser and the pipeline must agree on which dates a source warning questions."""
    node = _node()
    script = (
        "const health = require('./src/d365_pqu/static/js/core/health.js');"
        "process.stdout.write(JSON.stringify(health.DATE_FLAG_FIELDS));"
    )
    result = subprocess.run(
        [node, "-e", script],
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO_ROOT,
        timeout=60,
    )
    browser = {code: tuple(fields) for code, fields in json.loads(result.stdout).items()}
    assert browser == DATE_FLAG_FIELDS
