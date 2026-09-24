from __future__ import annotations

import csv
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from d365_pqu.config import (
    DATASET_NAME,
    DEFAULT_REPO_SLUG,
    PAGES_BASE_URL,
    PIPELINE_REVISION,
    RAW_BASE_URL,
    SCHEMA_VERSION,
)
from d365_pqu.models import NormalizedDataset

PQU_CSV_FIELDS = (
    "pqu_id",
    "application_version",
    "pqu_train",
    "release_number",
    "change_cutoff_date",
    "train_start_date",
    "train_end_date",
    "status",
    "application_build",
    "platform_build",
    "uep_version",
    "station_schedule_available",
    "first_seen_at",
    "last_changed_at",
    "source_commit",
    "source_url",
    "source_raw_url",
)
STATION_CSV_FIELDS = (
    "pqu_id",
    "application_version",
    "pqu_train",
    "release_number",
    "station",
    "station_label",
    "sandbox_start_date",
    "sandbox_end_date",
    "production_start_date",
    "production_end_date",
    "source_commit",
    "source_url",
    "source_raw_url",
)
REGION_CSV_FIELDS = ("station", "station_label", "region", "is_region")
VERSION_CSV_FIELDS = (
    "pqu_id",
    "application_version",
    "pqu_train",
    "release_number",
    "status",
    "application_build",
    "platform_build",
    "uep_version",
    "change_cutoff_date",
    "train_start_date",
    "train_end_date",
)
CHANGE_CSV_FIELDS = (
    "change_id",
    "changed_at",
    "pqu_id",
    "entity",
    "change_type",
    "field",
    "old_value",
    "new_value",
    "source_commit",
)
QUALITY_CSV_FIELDS = ("code", "severity", "message", "pqu_id", "field")


def isoformat(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def envelope(
    records: Sequence[Mapping[str, Any]],
    *,
    source: Mapping[str, Any],
    generated_at: datetime,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "dataset": DATASET_NAME,
        "schema_version": SCHEMA_VERSION,
        "generated_at": isoformat(generated_at),
    }
    if extra:
        document.update(extra)
    document["source"] = source
    document["count"] = len(records)
    document["records"] = list(records)
    return document


def current_document(dataset: NormalizedDataset) -> dict[str, Any]:
    records = [record for record in dataset.records if record["status"] == "In-Progress"]
    return envelope(
        records,
        source=dataset.source,
        generated_at=dataset.generated_at,
        extra={"latest_pqu_id": latest_pqu_id(dataset)},
    )


def upcoming_document(dataset: NormalizedDataset) -> dict[str, Any]:
    records = [record for record in dataset.records if record["status"] == "Not Started"]
    return envelope(records, source=dataset.source, generated_at=dataset.generated_at)


def changes_document(
    changes: Sequence[Mapping[str, Any]], *, source: Mapping[str, Any], generated_at: datetime
) -> dict[str, Any]:
    return envelope(changes, source=source, generated_at=generated_at)


def quality_document(
    quality: Sequence[Mapping[str, Any]], *, source: Mapping[str, Any], generated_at: datetime
) -> dict[str, Any]:
    errors = sum(1 for item in quality if item["severity"] == "error")
    warnings = sum(1 for item in quality if item["severity"] == "warning")
    return envelope(
        quality,
        source=source,
        generated_at=generated_at,
        extra={
            "status": "error" if errors else "warnings" if warnings else "clean",
            "error_count": errors,
            "warning_count": warnings,
        },
    )


def latest_pqu_id(dataset: NormalizedDataset) -> str | None:
    active = [record for record in dataset.records if record["status"] == "In-Progress"]
    if not active:
        return None
    candidate = max(
        active,
        key=lambda record: (
            tuple(int(part) for part in record["application_version"].split(".")),
            record["release_number"],
            record["train_start_date"] or "",
        ),
    )
    return candidate["pqu_id"]


def semantic_hash(dataset: NormalizedDataset) -> str:
    payload = {
        "records": [_stable_record(record) for record in dataset.records],
        "stations": [_stable_record(record) for record in dataset.stations],
        "regions": [dict(record) for record in dataset.regions],
        "versions": [dict(record) for record in dataset.versions],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _stable_record(record: Mapping[str, Any]) -> dict[str, Any]:
    ignored = {"first_seen_at", "last_changed_at", "source"}
    return {key: value for key, value in record.items() if key not in ignored}


def metadata_document(
    dataset: NormalizedDataset,
    *,
    previous_metadata: dict[str, Any] | None,
    generated_at: datetime,
) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    for record in dataset.records:
        statuses[record["status"]] = statuses.get(record["status"], 0) + 1
    first_published = None
    if previous_metadata and isinstance(previous_metadata.get("first_published_at"), str):
        first_published = previous_metadata["first_published_at"]
    generated = isoformat(generated_at)
    first_published = first_published or generated
    return {
        "dataset": DATASET_NAME,
        "schema_version": SCHEMA_VERSION,
        "pipeline_revision": PIPELINE_REVISION,
        "generated_at": generated,
        "first_published_at": first_published,
        "last_published_at": generated,
        "record_count": len(dataset.records),
        "station_schedule_count": len(dataset.stations),
        "region_count": len(dataset.regions),
        "status_counts": statuses,
        "current_count": statuses.get("In-Progress", 0),
        "upcoming_count": statuses.get("Not Started", 0),
        "latest_pqu_id": latest_pqu_id(dataset),
        "source": dataset.source,
        "links": {
            "repository": f"https://github.com/{DEFAULT_REPO_SLUG}",
            "pages": PAGES_BASE_URL + "/",
            "api_pqu": PAGES_BASE_URL + "/api/pqu.json",
            "api_csv": PAGES_BASE_URL + "/api/pqu.csv",
            "raw_pqu": RAW_BASE_URL + "/data/pqu.json",
            "workbook": PAGES_BASE_URL + "/downloads/D365-PQU-Tracker.xlsx",
            "raw_workbook": RAW_BASE_URL + "/excel/D365-PQU-Tracker.xlsx",
        },
    }


def health_document(
    dataset: NormalizedDataset,
    *,
    previous_health: dict[str, Any] | None,
    checked_at: datetime,
    changed: bool,
) -> dict[str, Any]:
    generated = isoformat(checked_at)
    last_source_change = (
        generated if changed else _previous_timestamp(previous_health, "last_source_change_at")
    )
    last_publish = (
        generated if changed else _previous_timestamp(previous_health, "last_successful_publish_at")
    )
    warning_count = sum(1 for item in dataset.quality if item["severity"] == "warning")
    error_count = sum(1 for item in dataset.quality if item["severity"] == "error")
    return {
        "dataset": DATASET_NAME,
        "schema_version": SCHEMA_VERSION,
        "status": "degraded" if warning_count else "healthy",
        "checked_at": generated,
        "last_successful_check_at": generated,
        "last_successful_publish_at": last_publish or generated,
        "last_source_change_at": last_source_change or generated,
        "source_reachable": True,
        "parser_success": True,
        "validation_passed": True,
        "records": len(dataset.records),
        "current_records": sum(1 for r in dataset.records if r["status"] == "In-Progress"),
        "upcoming_records": sum(1 for r in dataset.records if r["status"] == "Not Started"),
        "warning_count": warning_count,
        "error_count": error_count,
        "source_commit": dataset.source["commit"],
        "source_sha256": dataset.source["sha256"],
    }


def _previous_timestamp(previous: dict[str, Any] | None, key: str) -> str | None:
    if previous and isinstance(previous.get(key), str):
        return previous[key]
    return None


def write_json(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8")


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fieldnames),
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def flatten_pqu_record(record: Mapping[str, Any]) -> dict[str, Any]:
    source = record.get("source") or {}
    flat = {key: record.get(key) for key in PQU_CSV_FIELDS if key in record}
    flat["source_commit"] = source.get("commit")
    flat["source_url"] = source.get("url")
    flat["source_raw_url"] = source.get("raw_url")
    return flat


def flatten_station_record(record: Mapping[str, Any]) -> dict[str, Any]:
    source = record.get("source") or {}
    flat = {key: record.get(key) for key in STATION_CSV_FIELDS if key in record}
    flat["source_commit"] = source.get("commit")
    flat["source_url"] = source.get("url")
    flat["source_raw_url"] = source.get("raw_url")
    return flat
