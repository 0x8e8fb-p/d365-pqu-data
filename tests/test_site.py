from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from conftest import FIXTURES, SCHEMA_DIR
from d365_pqu.config import Paths
from d365_pqu.models import SourceDocument
from d365_pqu.pipeline import build_site, run_sync
from d365_pqu.source import parse_markdown_date


def _paths(tmp_path: Path) -> Paths:
    return Paths(
        root=tmp_path,
        data_dir=tmp_path / "data",
        excel_dir=tmp_path / "excel",
        schema_dir=SCHEMA_DIR,
        site_dir=tmp_path / "build" / "site",
        tests_dir=tmp_path / "tests",
    )


def _sync_and_site(tmp_path: Path) -> Paths:
    import hashlib

    paths = _paths(tmp_path)
    markdown = (FIXTURES / "source-minimal.md").read_text(encoding="utf-8")
    document = SourceDocument(
        markdown=markdown,
        source_commit="a" * 40,
        article_url="https://learn.microsoft.com/example",
        raw_url="https://raw.githubusercontent.com/example/a/schedule.md",
        markdown_date=parse_markdown_date(markdown),
        retrieved_at=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
        sha256=hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
    )
    run_sync(paths, source=document, now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC))
    build_site(paths)
    return paths


def test_site_contains_api_schemas_and_downloads(tmp_path: Path) -> None:
    paths = _sync_and_site(tmp_path)
    site = paths.site_dir
    assert (site / ".nojekyll").exists()
    assert (site / "index.html").exists()
    assert (site / "404.html").exists()
    assert (site / "assets" / "styles.css").exists()
    assert (site / "assets" / "app.js").exists()
    assert (site / "api" / "pqu.json").exists()
    assert (site / "api" / "pqu.csv").exists()
    assert (site / "api" / "metadata.json").exists()
    assert (site / "api" / "index.json").exists()
    assert (site / "schemas" / "pqu.schema.json").exists()
    assert (site / "downloads" / "D365-PQU-Tracker.xlsx").exists()


def test_site_api_index_lists_endpoints(tmp_path: Path) -> None:
    paths = _sync_and_site(tmp_path)
    index = json.loads((paths.site_dir / "api" / "index.json").read_text(encoding="utf-8"))
    names = {endpoint["name"] for endpoint in index["endpoints"]}
    assert {"PQU master", "Current PQU", "Upcoming PQU", "Health"} <= names
    pqu = json.loads((paths.site_dir / "api" / "pqu.json").read_text(encoding="utf-8"))
    assert pqu["count"] == 4


def test_site_has_no_external_cdn_assets(tmp_path: Path) -> None:
    paths = _sync_and_site(tmp_path)
    html = (paths.site_dir / "index.html").read_text(encoding="utf-8")
    assert "http://" not in html
    assert "cdn." not in html
    assert "fonts.googleapis" not in html


def test_app_javascript_is_valid_when_node_is_available(tmp_path: Path) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    paths = _sync_and_site(tmp_path)
    result = subprocess.run(
        [node, "--check", str(paths.site_dir / "assets" / "app.js")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
