from __future__ import annotations

import hashlib
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from d365_pqu.config import PAGES_BASE_URL
from d365_pqu.errors import PublishError
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
}
SCHEMA_FILES = (
    "pqu.schema.json",
    "station.schema.json",
    "region.schema.json",
    "version.schema.json",
    "change.schema.json",
    "quality-report.schema.json",
    "metadata.schema.json",
    "health.schema.json",
)
STATIC_FILES = ("index.html", "404.html", "styles.css", "app.js", "icon.svg", "robots.txt")
VERSIONED_ASSETS = (
    ("styles.css", "styles", ".css"),
    ("app.js", "app", ".js"),
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


def _preflight(data_dir: Path, schema_dir: Path, workbook_path: Path, static_dir: Path) -> None:
    required = [data_dir / name for name in (*JSON_FILES, *CSV_FILES)]
    required.extend(schema_dir / name for name in SCHEMA_FILES)
    required.extend(static_dir / name for name in STATIC_FILES)
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
        asset_version = (
            f"{versioned['app.js'].split('.')[1]}-{versioned['styles.css'].split('.')[1]}"
        )
        html_replacements = {
            "index.html": {
                "./assets/styles.css": f"./assets/{versioned['styles.css']}",
                "./assets/app.js": f"./assets/{versioned['app.js']}",
                "./assets/icon.svg": f"./assets/{versioned['icon.svg']}",
            },
            "404.html": {
                "./assets/styles.css": f"./assets/{versioned['styles.css']}",
                "./assets/icon.svg": f"./assets/{versioned['icon.svg']}",
            },
        }
        for name, replacements in html_replacements.items():
            _write_versioned_text(static_dir / name, staging / name, replacements)
        _write_versioned_text(
            static_dir / "app.js",
            assets / versioned["app.js"],
            {"__ASSET_VERSION__": asset_version},
        )
        _copy(static_dir / "robots.txt", staging / "robots.txt")
        _write_api_index(api_dir / "index.json", metadata)
        (staging / ".nojekyll").write_text("", encoding="utf-8")
        _replace_site(staging, site_dir)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _write_api_index(path: Path, metadata: dict[str, Any]) -> None:
    base = "."
    endpoints = [
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
            "name": "Region mapping",
            "path": f"{base}/regions.json",
            "csv": f"{base}/regions.csv",
            "description": "Station-to-region mapping used to locate environment update windows.",
        },
        {
            "name": "Versions",
            "path": f"{base}/versions.json",
            "csv": f"{base}/versions.csv",
            "description": "Application, platform, and UEP build numbers by PQU.",
        },
        {
            "name": "Change history",
            "path": f"{base}/changes.json",
            "csv": f"{base}/changes.csv",
            "description": "Field-level changes detected between source revisions.",
        },
        {
            "name": "Quality report",
            "path": f"{base}/quality-report.json",
            "csv": None,
            "description": "Non-fatal source warnings and validation details.",
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
            "description": "Last successful synchronization and validation state.",
        },
    ]
    document = {
        "dataset": metadata["dataset"],
        "schema_version": metadata["schema_version"],
        "generated_at": metadata["generated_at"],
        "pages": PAGES_BASE_URL + "/",
        "endpoints": endpoints,
        "schemas": f"{base}/../schemas/",
        "workbook": f"{base}/../downloads/D365-PQU-Tracker.xlsx",
    }
    write_json(path, document)
