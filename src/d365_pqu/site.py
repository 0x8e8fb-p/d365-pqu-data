from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from d365_pqu.config import (
    ALLOWED_STATUSES,
    DEFAULT_BRANCH,
    DEFAULT_REPO_SLUG,
    PAGES_BASE_URL,
)
from d365_pqu.errors import PublishError
from d365_pqu.feed import FEED_FILE, FEED_LIMIT, feed_document
from d365_pqu.ics import CALENDAR_DIR, calendar_files, interval_text
from d365_pqu.serialization import write_json

JSON_FILES = {
    "pqu.json": "pqu.json",
    "pqu-current.json": "current.json",
    "pqu-upcoming.json": "upcoming.json",
    "pqu-stations.json": "stations.json",
    "pqu-regions.json": "regions.json",
    "pqu-versions.json": "versions.json",
    "pqu-changes.json": "changes.json",
    "quality-report.json": "quality-report.json",
    "learn.json": "learn.json",
    "service-updates.json": "service-updates.json",
    "maintenance-windows.json": "maintenance-windows.json",
    "insights.json": "insights.json",
    "events.json": "events.json",
    "metadata.json": "metadata.json",
    "health.json": "health.json",
}
CSV_FILES = {
    "pqu.csv": "pqu.csv",
    "pqu-stations.csv": "stations.csv",
    "pqu-regions.csv": "regions.csv",
    "pqu-versions.csv": "versions.csv",
    "pqu-changes.csv": "changes.csv",
    "pqu-current.csv": "current.csv",
    "pqu-upcoming.csv": "upcoming.csv",
    "service-updates.csv": "service-updates.csv",
    "maintenance-windows.csv": "maintenance-windows.csv",
    "insights.csv": "insights.csv",
    "events.csv": "events.csv",
}
SCHEMA_FILES = (
    "pqu.schema.json",
    "station.schema.json",
    "region.schema.json",
    "version.schema.json",
    "change.schema.json",
    "quality-report.schema.json",
    "learn.schema.json",
    "service-update.schema.json",
    "maintenance-window.schema.json",
    "insights.schema.json",
    "event.schema.json",
    "metadata.schema.json",
    "health.schema.json",
)
STATIC_FILES = ("index.html", "404.html", "styles.css", "icon.svg", "robots.txt")
JS_BUNDLE = (
    "js/core/dates.js",
    "js/core/versions.js",
    "js/core/text.js",
    "js/core/records.js",
    "js/core/health.js",
    "js/core/router.js",
    "js/core/phase.js",
    "js/core/lifecycle.js",
    "js/core/windows.js",
    "js/core/agenda.js",
    "js/core/builds.js",
    "js/core/rollout.js",
    "js/core/changes.js",
    "js/core/timeline.js",
    "js/ui/dom.js",
    "js/ui/prefs.js",
    "js/ui/theme.js",
    "js/ui/layout.js",
    "js/ui/zone.js",
    "js/ui/rich.js",
    "js/ui/guidance.js",
    "js/ui/common.js",
    "js/ui/health.js",
    "js/ui/timeline.js",
    "js/ui/calendar.js",
    "js/ui/views/notfound.js",
    "js/ui/views/overview.js",
    "js/ui/views/region.js",
    "js/ui/views/trains.js",
    "js/ui/views/train.js",
    "js/ui/views/versions.js",
    "js/ui/views/learn.js",
    "js/ui/views/changes.js",
    "js/ui/views/data.js",
    "js/ui/app.js",
    "js/main.js",
)
ASSET_VERSION_PLACEHOLDER = "__ASSET_VERSION__"
# Replaced at build time with the CSP hash sources of the page's inline scripts.
INLINE_SCRIPT_PLACEHOLDER = "'__INLINE_SCRIPT_HASHES__'"
SITE_ROOT_PLACEHOLDER = "__SITE_ROOT__"
# Inline scripts only: <script> without attributes (external scripts carry src).
INLINE_SCRIPT = re.compile(r"<script>(.*?)</script>", re.DOTALL)
LLMS_FILE = "llms.txt"
VERSIONED_ASSETS = (
    ("styles.css", "styles", ".css"),
    ("icon.svg", "icon", ".svg"),
)


def _copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _content_hash(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest[:12]


def _write_versioned_asset(source: Path, assets: Path, prefix: str, suffix: str) -> str:
    name = f"{prefix}.{_content_hash(source)}{suffix}"
    _copy(source, assets / name)
    return name


def _write_versioned_text(source: Path, target: Path, replacements: dict[str, str]) -> None:
    text = source.read_text(encoding="utf-8")
    for old, new in replacements.items():
        if old not in text:
            raise PublishError(f"{source.name} is missing expected asset reference: {old}")
        text = text.replace(old, new)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def bundle_javascript(static_dir: Path) -> str:
    """Concatenate the ordered JavaScript modules into one classic script."""
    parts: list[str] = []
    for name in JS_BUNDLE:
        source = static_dir / name
        if not source.is_file():
            raise PublishError(f"JavaScript module is missing from the bundle manifest: {source}")
        parts.append(f"/* ---- {name} ---- */\n{source.read_text(encoding='utf-8').rstrip()}\n")
    bundle = "\n".join(parts)
    if ASSET_VERSION_PLACEHOLDER not in bundle:
        raise PublishError("JavaScript bundle is missing the asset version placeholder")
    return bundle


def _preflight(data_dir: Path, schema_dir: Path, workbook_path: Path, static_dir: Path) -> None:
    required = [data_dir / name for name in (*JSON_FILES, *CSV_FILES)]
    required.extend(schema_dir / name for name in SCHEMA_FILES)
    required.extend(static_dir / name for name in STATIC_FILES)
    required.extend(static_dir / name for name in JS_BUNDLE)
    required.append(workbook_path)
    missing = [path for path in required if not path.is_file()]
    if missing:
        rendered = ", ".join(str(path) for path in missing)
        raise PublishError(f"Cannot build site; required inputs are missing: {rendered}")


def _replace_site(staging: Path, target: Path) -> None:
    backup = target.with_name(f".{target.name}.backup-{uuid.uuid4().hex}")
    if target.exists():
        os.replace(target, backup)
    try:
        os.replace(staging, target)
    except Exception:
        if backup.exists():
            os.replace(backup, target)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def generate_site(
    *,
    site_dir: Path,
    data_dir: Path,
    schema_dir: Path,
    workbook_path: Path,
    metadata: dict[str, Any],
    static_dir: Path,
    health_path: Path | None = None,
) -> None:
    _preflight(data_dir, schema_dir, workbook_path, static_dir)
    staging = site_dir.parent / f".{site_dir.name}.staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=True, exist_ok=False)
    try:
        api_dir = staging / "api"
        schema_target = staging / "schemas"
        downloads = staging / "downloads"
        assets = staging / "assets"

        for source_name, target_name in JSON_FILES.items():
            _copy(data_dir / source_name, api_dir / target_name)
        if health_path is not None:
            _copy(health_path, api_dir / "health.json")
        for source_name, target_name in CSV_FILES.items():
            _copy(data_dir / source_name, api_dir / target_name)
        for schema_name in SCHEMA_FILES:
            _copy(schema_dir / schema_name, schema_target / schema_name)
        _copy(workbook_path, downloads / workbook_path.name)
        versioned = {}
        for source_name, prefix, suffix in VERSIONED_ASSETS:
            versioned[source_name] = _write_versioned_asset(
                static_dir / source_name, assets, prefix, suffix
            )
        bundle = bundle_javascript(static_dir)
        bundle_hash = hashlib.sha256(bundle.encode("utf-8")).hexdigest()[:12]
        app_name = f"app.{bundle_hash}.js"
        asset_version = f"{bundle_hash}-{versioned['styles.css'].split('.')[1]}"
        assets.mkdir(parents=True, exist_ok=True)
        (assets / app_name).write_text(
            bundle.replace(ASSET_VERSION_PLACEHOLDER, asset_version), encoding="utf-8"
        )
        html_replacements = {
            "index.html": {
                "./assets/styles.css": f"./assets/{versioned['styles.css']}",
                "./assets/app.js": f"./assets/{app_name}",
                "./assets/icon.svg": f"./assets/{versioned['icon.svg']}",
            },
            # GitHub Pages serves 404.html at whatever path was missing, so its links and assets
            # use absolute paths from the site root instead of relative ones.
            "404.html": {
                f"{SITE_ROOT_PLACEHOLDER}/assets/styles.css": (
                    f"{site_root()}/assets/{versioned['styles.css']}"
                ),
                f"{SITE_ROOT_PLACEHOLDER}/assets/icon.svg": (
                    f"{site_root()}/assets/{versioned['icon.svg']}"
                ),
                SITE_ROOT_PLACEHOLDER: site_root(),
            },
        }
        for name, replacements in html_replacements.items():
            source_text = (static_dir / name).read_text(encoding="utf-8")
            csp = {INLINE_SCRIPT_PLACEHOLDER: inline_script_hashes(source_text)}
            _write_versioned_text(static_dir / name, staging / name, {**replacements, **csp})
        _copy(static_dir / "robots.txt", staging / "robots.txt")
        _write_feed(staging / FEED_FILE, data_dir / "pqu-changes.json", metadata)
        calendars = _write_calendars(staging / CALENDAR_DIR, data_dir, metadata)
        index = api_index_document(metadata, calendars)
        write_json(api_dir / "index.json", index)
        (staging / LLMS_FILE).write_text(llms_text(index, metadata), encoding="utf-8")
        (staging / ".nojekyll").write_text("", encoding="utf-8")
        _replace_site(staging, site_dir)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def site_root(pages_url: str = PAGES_BASE_URL) -> str:
    """Path of the published site's root, without a trailing slash (``/d365-pqu-data``)."""
    return urlparse(pages_url).path.rstrip("/")


def inline_script_hashes(html: str) -> str:
    """CSP sources for every inline ``<script>`` in ``html``: ``'sha256-…'`` separated by spaces.

    The hash covers the exact text between the tags, which is what browsers hash.
    """
    hashes = []
    for body in INLINE_SCRIPT.findall(html):
        digest = hashlib.sha256(body.encode("utf-8")).digest()
        hashes.append(f"'sha256-{base64.b64encode(digest).decode('ascii')}'")
    if not hashes:
        raise PublishError("The page has a script hash placeholder but no inline script")
    return " ".join(hashes)


def _records(path: Path) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    records = document.get("records") if isinstance(document, dict) else None
    if not isinstance(records, list):
        raise PublishError(f"{path.name} has no records collection")
    return records


def _write_feed(path: Path, changes_path: Path, metadata: dict[str, Any]) -> None:
    path.write_bytes(feed_document(_records(changes_path), metadata))


def _write_calendars(
    target: Path, data_dir: Path, metadata: dict[str, Any]
) -> list[dict[str, Any]]:
    """Write every calendar and return their API index entries."""
    files = calendar_files(
        _records(data_dir / "events.json"),
        regions=_records(data_dir / "pqu-regions.json"),
        quality=_records(data_dir / "quality-report.json"),
        metadata=metadata,
    )
    target.mkdir(parents=True, exist_ok=True)
    listing = []
    for file_name, entry in files.items():
        (target / file_name).write_bytes(entry["content"])
        listing.append(
            {
                "name": entry["name"],
                "path": f"./../{CALENDAR_DIR}/{file_name}",
                "url": f"{PAGES_BASE_URL}/{CALENDAR_DIR}/{file_name}",
                "events": entry["events"],
                "description": entry["description"],
            }
        )
    return listing


def api_index_document(
    metadata: dict[str, Any], calendars: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """``api/index.json``: every published file, with paths relative to ``api/``."""
    base = "."
    endpoints: list[dict[str, Any]] = [
        {
            "name": "PQU master",
            "path": f"{base}/pqu.json",
            "csv": f"{base}/pqu.csv",
            "description": "Every published PQU train with builds, status, and provenance.",
        },
        {
            "name": "Current PQU",
            "path": f"{base}/current.json",
            "csv": f"{base}/current.csv",
            "description": "All PQU trains currently marked In-Progress.",
        },
        {
            "name": "Upcoming PQU",
            "path": f"{base}/upcoming.json",
            "csv": f"{base}/upcoming.csv",
            "description": "All PQU trains not yet started, sorted by application version and train.",
        },
        {
            "name": "Station schedule",
            "path": f"{base}/stations.json",
            "csv": f"{base}/stations.csv",
            "description": "Sandbox and production windows for stations 1 through 6.",
        },
        {
            "name": "Key dates",
            "path": f"{base}/events.json",
            "csv": f"{base}/events.csv",
            "description": (
                "One event per change cutoff, train, station window, and service update "
                "milestone, in date order, with identifiers that stay the same when Microsoft "
                "moves a date."
            ),
        },
        {
            "name": "Region mapping",
            "path": f"{base}/regions.json",
            "csv": f"{base}/regions.csv",
            "description": (
                "Station-to-region mapping used to locate environment update windows, with the "
                "maintenance-window geography matched from each region name."
            ),
        },
        {
            "name": "Maintenance windows",
            "path": f"{base}/maintenance-windows.json",
            "csv": f"{base}/maintenance-windows.csv",
            "description": (
                "Microsoft's planned maintenance (dark hours) window per geography: UTC start "
                "time, weekdays, and length, with that article's provenance."
            ),
        },
        {
            "name": "Versions",
            "path": f"{base}/versions.json",
            "csv": f"{base}/versions.csv",
            "description": "Application, platform, and UEP build numbers by PQU.",
        },
        {
            "name": "Service updates",
            "path": f"{base}/service-updates.json",
            "csv": f"{base}/service-updates.csv",
            "description": (
                "Microsoft's targeted release schedule for service updates: preview, general "
                "availability, autoupdate, and end-of-service dates, with that article's provenance."
            ),
        },
        {
            "name": "Change history",
            "path": f"{base}/changes.json",
            "csv": f"{base}/changes.csv",
            "description": "Field-level changes detected between source revisions.",
        },
        {
            "name": "Change feed",
            "path": f"{base}/../{FEED_FILE}",
            "csv": None,
            "description": (
                f"Atom feed of the newest {FEED_LIMIT} changes, newest first. Entry identifiers "
                "come from the change identifiers, so a reader never shows a change twice."
            ),
        },
        {
            "name": "Quality report",
            "path": f"{base}/quality-report.json",
            "csv": None,
            "description": "Non-fatal source warnings and validation details.",
        },
        {
            "name": "Learn content",
            "path": f"{base}/learn.json",
            "csv": None,
            "description": (
                "Structured guidance text from Microsoft Learn articles (CC BY 4.0), with "
                "section anchors, change hashes, and provenance."
            ),
        },
        {
            "name": "Calculated figures",
            "path": f"{base}/insights.json",
            "csv": f"{base}/insights.csv",
            "description": (
                "Figures calculated from Microsoft's published dates (release cadence, station "
                "offsets, service update rhythm), each with its statistic, sample size, and "
                "what was left out. Microsoft does not publish these figures."
            ),
        },
        {
            "name": "Metadata",
            "path": f"{base}/metadata.json",
            "csv": None,
            "description": "Dataset summary, counts, source provenance, and links.",
        },
        {
            "name": "Health",
            "path": f"{base}/health.json",
            "csv": None,
            "description": (
                "State of the most recent check: when it ran, which Microsoft commit it examined, "
                "and whether the published data is current."
            ),
        },
    ]
    from d365_pqu.pipeline import SCHEMA_FOR_DOCUMENT

    # Each JSON endpoint names the JSON Schema that validates it.
    data_names = {target: source for source, target in JSON_FILES.items()}
    for endpoint in endpoints:
        data_name = data_names.get(str(endpoint["path"]).removeprefix(f"{base}/"))
        schema = SCHEMA_FOR_DOCUMENT.get(data_name) if data_name else None
        endpoint["schema"] = f"{base}/../schemas/{schema}" if schema else None
    return {
        "dataset": metadata["dataset"],
        "schema_version": metadata["schema_version"],
        "generated_at": metadata["generated_at"],
        "pages": PAGES_BASE_URL + "/",
        "endpoints": endpoints,
        "calendars": calendars or [],
        "schemas": f"{base}/../schemas/",
        "workbook": f"{base}/../downloads/D365-PQU-Tracker.xlsx",
        "llms": f"{base}/../{LLMS_FILE}",
        "repository": f"https://github.com/{DEFAULT_REPO_SLUG}",
        # GitHub Pages does not list folders; the schema sources are browsable in the repository.
        "schema_source": f"https://github.com/{DEFAULT_REPO_SLUG}/tree/{DEFAULT_BRANCH}/schema",
        "notice": f"https://github.com/{DEFAULT_REPO_SLUG}/blob/{DEFAULT_BRANCH}/NOTICE.md",
    }


SOURCE_STATE_TEXT = {
    "current": "current copy",
    "stale": "last good copy; the latest version could not be read",
    "unavailable": "not available",
}


def llms_text(index: dict[str, Any], metadata: dict[str, Any]) -> str:
    """``llms.txt``: what the dataset is and where each file is, for language-model tools.

    Built from the API index and metadata of the same build, so every count, date and link is the
    published one.
    """
    api = f"{PAGES_BASE_URL}/api/"

    def absolute(path: str) -> str:
        return urljoin(api, path)

    counts = metadata.get("status_counts") or {}
    statuses = [f"{counts[status]} {status}" for status in ALLOWED_STATUSES if counts.get(status)]
    sources = [
        entry
        for entry in (metadata.get("sources") or {}).values()
        if isinstance(entry, dict) and entry.get("state") in SOURCE_STATE_TEXT
    ]
    used = [entry for entry in sources if entry["state"] in ("current", "stale")]
    facts = (
        f"This copy was generated at {metadata['generated_at']} and lists "
        f"{metadata['record_count']} trains ({', '.join(statuses)})."
    )
    if metadata.get("latest_pqu_id"):
        facts += f" The newest train Microsoft lists as In-Progress is {metadata['latest_pqu_id']}."
    interval = metadata.get("check_interval_minutes")
    if isinstance(interval, int) and interval > 0:
        facts += f" Microsoft's articles are checked {interval_text(interval)}."
    lines = [
        "# D365 PQU dataset",
        "",
        "> Machine-readable data about Microsoft Dynamics 365 Finance and Operations proactive "
        "quality updates (PQUs): release trains, station rollout windows, service update "
        "milestones and planned maintenance windows, rebuilt from Microsoft Learn articles.",
        "",
        facts,
        "",
        f"Values come from {len(used)} Microsoft Learn articles, read at a pinned commit of the "
        "MicrosoftDocs repository and used under CC BY 4.0; every document records its source. "
        "insights.json, events.json and the calendars are calculated from those values. This "
        "project is independent and not affiliated with Microsoft; for decisions about one "
        "environment, use the notifications Microsoft sends for that environment.",
        "",
        "## Data",
        "",
    ]
    for endpoint in index["endpoints"]:
        line = f"- [{endpoint['name']}]({absolute(endpoint['path'])}): {endpoint['description']}"
        if endpoint.get("csv"):
            line += f" CSV: {absolute(endpoint['csv'])}"
        if endpoint.get("schema"):
            line += f" Schema: {absolute(endpoint['schema'])}"
        lines.append(line)
    if index.get("calendars"):
        lines += ["", "## Calendars", ""]
        for calendar in index["calendars"]:
            lines.append(
                f"- [{calendar['name']}]({calendar['url']}): iCalendar subscription with "
                f"{calendar['events']} all-day events."
            )
    if sources:
        lines += ["", "## Sources", ""]
        for entry in sources:
            source = entry.get("source") or {}
            details = [SOURCE_STATE_TEXT[entry["state"]]]
            if source.get("commit"):
                details.append(f"Microsoft commit {str(source['commit'])[:7]}")
            if source.get("markdown_date"):
                details.append(f"article dated {source['markdown_date']}")
            lines.append(f"- [{entry['label']}]({entry['article_url']}): {'; '.join(details)}")
    lines += [
        "",
        "## Optional",
        "",
        f"- [Dashboard]({PAGES_BASE_URL}/)",
        f"- [API index]({api}index.json)",
        f"- [Excel workbook]({absolute(index['workbook'])})",
        f"- [JSON Schemas]({index['schema_source']})",
        f"- [Source repository]({index['repository']})",
        f"- [License and attribution]({index['notice']})",
    ]
    return "\n".join(lines) + "\n"
