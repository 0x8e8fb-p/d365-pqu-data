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

STATIC_ROOT = Path(__file__).resolve().parents[1] / "src" / "d365_pqu" / "static"


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


def test_dashboard_shell_supports_dark_first_console() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    assert '<html lang="en" data-theme="dark">' in html
    assert 'id="theme-toggle"' in html
    assert 'id="page-size"' in html
    assert 'id="prev-page"' in html
    assert "aria-sort" in html
    assert "overview-heading" not in html
    assert "latest-pqu" not in html
    assert "next-stat" not in html
    assert "record-count" not in html
    assert "stations-heading" not in html
    assert "station-table" not in html
    assert "station-note" not in html
    assert "station-pqu-filter" not in html
    assert "station-search" not in html
    assert "reset-stations" not in html
    assert "show-station" not in html
    assert "Asia/Kolkata" in html
    assert 'class="workspace"' in html
    assert 'class="filters-rail"' in html
    assert 'class="filter-group"' in html
    assert 'class="toolbar' not in html
    for control_id in (
        "search",
        "status-filter",
        "version-filter",
        "page-size",
        "reset-filters",
        "region-select",
        "region-result",
    ):
        assert html.count(f'id="{control_id}"') == 1
    assert "reset-region" not in html
    assert "quality-block" not in html
    assert "quality-list" not in html
    assert "Data quality" not in html
    order = [
        html.index('id="search"'),
        html.index('id="status-filter"'),
        html.index('id="version-filter"'),
        html.index('id="region-select"'),
        html.index('id="page-size"'),
        html.index('id="reset-filters"'),
    ]
    assert order == sorted(order)
    assert "http://" not in html
    assert "fonts.googleapis" not in html
    assert "Public API" not in html
    assert "endpoint-list" not in html
    assert "api/index.json" not in html
    assert "api/pqu.json" not in html
    assert "api/pqu.csv" not in html


def test_dashboard_javascript_uses_ist_theme_sorting_and_pagination() -> None:
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    assert "Asia/Kolkata" in script
    assert "d365-pqu-theme" in script
    assert "aria-sort" in script
    assert "prev-page" in script
    assert "activeStation" in script
    assert "hasStations" in script
    assert "On-Going" in script
    assert "In-Progress" in script
    assert "Not Started" in script
    assert "Expanded trains show only this station." in script
    assert "aria-expanded" in script
    assert "aria-controls" in script
    assert "station-detail" in script
    assert "resetAllFilters" in script
    assert "Reset all filters" in (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    assert "reset-region" not in script
    assert "resetSchedule" not in script
    assert "quality-report.json" not in script
    assert "quality-block" not in script
    assert "quality-list" not in script
    assert "warning(s)" not in script
    assert "renderStations" not in script
    assert "station-pqu-filter" not in script
    assert "station-search" not in script
    assert "isDueSoon" in script
    assert "Due soon" in script
    assert "due-soon" in script
    assert "next-stat" not in script
    assert "latest-pqu" not in script
    assert "api/index.json" not in script
    assert "endpoint-list" not in script
    assert "navigator.clipboard" not in script
    assert "innerHTML" not in script


def test_dashboard_css_uses_responsive_dark_light_tokens() -> None:
    css = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")
    assert ":root" in css
    assert '[data-theme="light"]' in css
    assert "--bg:" in css
    assert "tabular-nums" in css
    assert ".row-toggle" in css
    assert ".station-detail" in css
    assert "max-width: 760px" in css
    assert "table-layout: fixed" in css
    assert ".stats" not in css
    assert ".quality" not in css
    assert "@media (max-width:" in css
    assert "prefers-reduced-motion" in css
    assert "http://" not in css


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
