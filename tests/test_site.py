from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from conftest import FIXTURES, SCHEMA_DIR
from d365_pqu.config import Paths
from d365_pqu.errors import PublishError
from d365_pqu.models import SourceDocument
from d365_pqu.pipeline import build_site, run_sync
from d365_pqu.site import JS_BUNDLE, bundle_javascript
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


def _built_script(site: Path) -> Path:
    scripts = sorted((site / "assets").glob("app.*.js"))
    assert len(scripts) == 1
    return scripts[0]


def test_site_contains_api_schemas_and_downloads(tmp_path: Path) -> None:
    paths = _sync_and_site(tmp_path)
    site = paths.site_dir
    assert (site / ".nojekyll").exists()
    assert (site / "index.html").exists()
    assert (site / "404.html").exists()
    assert not (site / "assets" / "styles.css").exists()
    assert not (site / "assets" / "app.js").exists()
    assert not (site / "assets" / "icon.svg").exists()
    assert not (site / "js").exists()
    assert (site / "api" / "pqu.json").exists()
    assert (site / "api" / "pqu.csv").exists()
    assert (site / "api" / "metadata.json").exists()
    assert (site / "api" / "index.json").exists()
    assert (site / "schemas" / "pqu.schema.json").exists()
    assert (site / "downloads" / "D365-PQU-Tracker.xlsx").exists()


def test_site_versions_dashboard_assets(tmp_path: Path) -> None:
    paths = _sync_and_site(tmp_path)
    site = paths.site_dir
    html = (site / "index.html").read_text(encoding="utf-8")
    css_match = re.search(r"\./assets/(styles\.[0-9a-f]{12}\.css)", html)
    js_match = re.search(r"\./assets/(app\.[0-9a-f]{12}\.js)", html)
    icon_match = re.search(r"\./assets/(icon\.[0-9a-f]{12}\.svg)", html)
    assert css_match is not None
    assert js_match is not None
    assert icon_match is not None
    assert (site / "assets" / css_match.group(1)).exists()
    assert (site / "assets" / js_match.group(1)).exists()
    assert (site / "assets" / icon_match.group(1)).exists()
    assert "./assets/styles.css" not in html
    assert "./assets/app.js" not in html
    built_js = (site / "assets" / js_match.group(1)).read_text(encoding="utf-8")
    assert "__ASSET_VERSION__" not in built_js
    assert "showLoadError" in built_js
    not_found = (site / "404.html").read_text(encoding="utf-8")
    # GitHub Pages serves 404.html at any missing path, so it uses paths from the site root.
    assert f'href="/d365-pqu-data/assets/{css_match.group(1)}"' in not_found
    assert f'href="/d365-pqu-data/assets/{icon_match.group(1)}"' in not_found
    assert 'href="/d365-pqu-data/#/data"' in not_found
    assert "__SITE_ROOT__" not in not_found
    assert "./assets/" not in not_found


def _csp(html: str) -> dict[str, list[str]]:
    match = re.search(r'<meta http-equiv="Content-Security-Policy" content="([^"]+)">', html)
    assert match is not None
    policy: dict[str, list[str]] = {}
    for directive in match.group(1).split(";"):
        name, *values = directive.split()
        policy[name] = values
    return policy


def test_pages_carry_a_content_security_policy_with_the_inline_script_hash(
    tmp_path: Path,
) -> None:
    import base64
    import hashlib

    from d365_pqu.site import inline_script_hashes

    paths = _sync_and_site(tmp_path)
    for name in ("index.html", "404.html"):
        html = (paths.site_dir / name).read_text(encoding="utf-8")
        assert "__INLINE_SCRIPT_HASHES__" not in html
        scripts = re.findall(r"<script>(.*?)</script>", html, re.DOTALL)
        assert len(scripts) == 1
        digest = base64.b64encode(hashlib.sha256(scripts[0].encode("utf-8")).digest()).decode()
        policy = _csp(html)
        assert f"'sha256-{digest}'" in policy["script-src"]
        sources = [source for values in policy.values() for source in values]
        assert "'unsafe-inline'" not in sources
        assert "'unsafe-eval'" not in sources
        assert policy["style-src"] == ["'self'"]
        assert policy["base-uri"] == ["'none'"]
        assert policy["object-src"] == ["'none'"]
        assert policy["form-action"] == ["'none'"]
        # The policy must come before anything it governs.
        assert html.index("Content-Security-Policy") < html.index("<script>")
        assert html.index("Content-Security-Policy") < html.index('rel="stylesheet"')
    index = _csp((paths.site_dir / "index.html").read_text(encoding="utf-8"))
    assert index["default-src"] == ["'self'"]
    assert index["connect-src"] == ["'self'"]
    assert index["img-src"] == ["'self'", "data:"]
    with pytest.raises(PublishError, match="no inline script"):
        inline_script_hashes("<script src='x.js'></script>")


def test_site_publishes_llms_txt(tmp_path: Path) -> None:
    paths = _sync_and_site(tmp_path)
    site = paths.site_dir
    text = (site / "llms.txt").read_text(encoding="utf-8")
    metadata = json.loads((site / "api" / "metadata.json").read_text(encoding="utf-8"))
    index = json.loads((site / "api" / "index.json").read_text(encoding="utf-8"))
    lines = text.splitlines()
    assert lines[0] == "# D365 PQU dataset"
    assert lines[2].startswith("> ")
    assert f"generated at {metadata['generated_at']}" in text
    assert f"lists {metadata['record_count']} trains" in text
    assert "## Data" in lines
    for endpoint in index["endpoints"]:
        assert f"- [{endpoint['name']}](" in text
    assert "https://0x8e8fb-p.github.io/d365-pqu-data/api/pqu.json" in text
    assert "https://0x8e8fb-p.github.io/d365-pqu-data/feed.xml" in text
    assert "https://0x8e8fb-p.github.io/d365-pqu-data/calendar/station-4.ics" in text
    assert "## Sources" in lines
    assert "[Release schedule for proactive quality updates](https://learn.microsoft.com/" in text
    assert "http://" not in text
    assert text.endswith("\n")
    assert index["llms"] == "./../llms.txt"
    assert (site / "api" / index["llms"]).resolve() == (site / "llms.txt").resolve()


def test_api_index_names_each_schema_and_the_license(tmp_path: Path) -> None:
    paths = _sync_and_site(tmp_path)
    site = paths.site_dir
    index = json.loads((site / "api" / "index.json").read_text(encoding="utf-8"))
    schemas = {endpoint["name"]: endpoint["schema"] for endpoint in index["endpoints"]}
    assert schemas["PQU master"] == "./../schemas/pqu.schema.json"
    assert schemas["Current PQU"] == "./../schemas/pqu.schema.json"
    assert schemas["Key dates"] == "./../schemas/event.schema.json"
    assert schemas["Change feed"] is None
    for schema in filter(None, schemas.values()):
        assert (site / "api" / schema).resolve().is_file()
    assert index["notice"] == "https://github.com/0x8e8fb-p/d365-pqu-data/blob/main/NOTICE.md"
    assert index["schema_source"] == "https://github.com/0x8e8fb-p/d365-pqu-data/tree/main/schema"
    assert index["repository"] == "https://github.com/0x8e8fb-p/d365-pqu-data"


def test_bundle_concatenates_manifest_in_order(tmp_path: Path) -> None:
    paths = _sync_and_site(tmp_path)
    built = _built_script(paths.site_dir).read_text(encoding="utf-8")
    positions = [built.index(f"/* ---- {name} ---- */") for name in JS_BUNDLE]
    assert positions == sorted(positions)
    assert JS_BUNDLE[0].startswith("js/core/")
    assert JS_BUNDLE[-1] == "js/main.js"
    for name in JS_BUNDLE:
        assert (STATIC_ROOT / name).is_file()


def test_bundle_requires_every_manifest_module(tmp_path: Path) -> None:
    static = tmp_path / "static"
    shutil.copytree(STATIC_ROOT, static)
    (static / JS_BUNDLE[1]).unlink()
    with pytest.raises(PublishError, match="missing from the bundle manifest"):
        bundle_javascript(static)


def test_every_javascript_module_is_bundled() -> None:
    modules = {
        path.relative_to(STATIC_ROOT).as_posix() for path in (STATIC_ROOT / "js").rglob("*.js")
    }
    assert modules == set(JS_BUNDLE)


def test_site_api_index_lists_endpoints(tmp_path: Path) -> None:
    paths = _sync_and_site(tmp_path)
    index = json.loads((paths.site_dir / "api" / "index.json").read_text(encoding="utf-8"))
    names = {endpoint["name"] for endpoint in index["endpoints"]}
    assert {"PQU master", "Current PQU", "Upcoming PQU", "Health", "Learn content"} <= names
    pqu = json.loads((paths.site_dir / "api" / "pqu.json").read_text(encoding="utf-8"))
    assert pqu["count"] == 4


def test_site_publishes_the_change_feed(tmp_path: Path) -> None:
    import xml.etree.ElementTree as ET

    paths = _sync_and_site(tmp_path)
    site = paths.site_dir
    feed = ET.fromstring((site / "feed.xml").read_bytes())
    assert feed.tag == "{http://www.w3.org/2005/Atom}feed"
    html = (site / "index.html").read_text(encoding="utf-8")
    assert (
        '<link rel="alternate" type="application/atom+xml" title="PQU changes (Atom feed)" '
        'href="./feed.xml">'
    ) in html
    index = json.loads((site / "api" / "index.json").read_text(encoding="utf-8"))
    endpoint = next(item for item in index["endpoints"] if item["name"] == "Change feed")
    assert endpoint["path"] == "./../feed.xml"
    assert (site / "api" / endpoint["path"]).resolve() == (site / "feed.xml").resolve()


def test_site_publishes_the_health_of_this_run(tmp_path: Path) -> None:
    paths = _sync_and_site(tmp_path)
    health = json.loads((paths.site_dir / "api" / "health.json").read_text(encoding="utf-8"))
    assert health["run_status"] == "updated"
    assert health["checked_commit"] == "a" * 40
    assert health["content_commit"] == "a" * 40
    assert build_site(paths)["health_source"] == "run"


def test_site_falls_back_to_committed_health_when_run_health_does_not_apply(
    tmp_path: Path,
) -> None:
    paths = _sync_and_site(tmp_path)
    published = paths.site_dir / "api" / "health.json"
    committed = (paths.data_dir / "health.json").read_bytes()
    original = json.loads(paths.run_health_path.read_text(encoding="utf-8"))

    mismatched = {**original, "content_commit": "f" * 40}
    paths.run_health_path.write_text(json.dumps(mismatched), encoding="utf-8")
    assert build_site(paths)["health_source"] == "data"
    assert published.read_bytes() == committed

    older = {**original, "checked_at": "2026-09-24T11:00:00Z"}
    paths.run_health_path.write_text(json.dumps(older), encoding="utf-8")
    assert build_site(paths)["health_source"] == "data"

    invalid = {**original, "run_status": "exploded"}
    paths.run_health_path.write_text(json.dumps(invalid), encoding="utf-8")
    assert build_site(paths)["health_source"] == "data"

    paths.run_health_path.write_text("{not json", encoding="utf-8")
    assert build_site(paths)["health_source"] == "data"

    paths.run_health_path.unlink()
    assert build_site(paths)["health_source"] == "data"
    assert published.read_bytes() == committed


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
    assert 'id="view"' in html
    assert 'id="load-error"' in html
    assert 'rel="icon"' in html
    assert 'rel="mask-icon"' in html
    assert 'name="theme-color"' in html
    assert "./assets/icon.svg" in html
    assert "./assets/app.js" in html
    assert "http://" not in html
    assert "fonts.googleapis" not in html
    assert "<noscript>" in html


def test_brand_icon_is_valid_self_contained_svg() -> None:
    import xml.etree.ElementTree as ET

    text = (STATIC_ROOT / "icon.svg").read_text(encoding="utf-8")
    root = ET.fromstring(text)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.attrib.get("viewBox") == "0 0 64 64"
    assert len(root.findall(".//{http://www.w3.org/2000/svg}path")) >= 2
    assert "xlink:href" not in text
    assert "<image" not in text


def test_dashboard_javascript_avoids_unsafe_dom_apis() -> None:
    for path in (STATIC_ROOT / "js").rglob("*.js"):
        script = path.read_text(encoding="utf-8")
        assert "innerHTML" not in script, path
        assert "outerHTML" not in script, path
        assert "insertAdjacentHTML" not in script, path
        assert "document.write" not in script, path
        assert "eval(" not in script, path
        assert "new Function" not in script, path
        assert "http://" not in script, path
        assert "navigator.clipboard" not in script, path
        assert 'setAttribute("style"' not in script, path


def test_trains_view_keeps_table_controls() -> None:
    script = (STATIC_ROOT / "js" / "ui" / "views" / "trains.js").read_text(encoding="utf-8")
    for control_id in (
        "search",
        "status-filter",
        "version-filter",
        "region-select",
        "region-result",
        "page-size",
        "reset-filters",
        "pqu-table",
        "prev-page",
        "next-page",
    ):
        assert f'"{control_id}"' in script, control_id
    assert "aria-sort" in script
    assert "aria-expanded" in script
    assert "aria-controls" in script
    assert "station-detail" in script
    assert "Reset all filters" in script
    assert "Due soon" in script


def test_dashboard_css_uses_responsive_dark_light_tokens() -> None:
    css = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")
    assert ":root" in css
    assert '[data-theme="light"]' in css
    assert "--bg:" in css
    assert "tabular-nums" in css
    assert ".row-toggle" in css
    assert ".station-detail" in css
    assert "table-layout: fixed" in css
    assert "@media (max-width:" in css
    assert "prefers-reduced-motion" in css
    assert "http://" not in css


def test_app_javascript_is_valid_when_node_is_available(tmp_path: Path) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    paths = _sync_and_site(tmp_path)
    result = subprocess.run(
        [node, "--check", str(_built_script(paths.site_dir))],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
