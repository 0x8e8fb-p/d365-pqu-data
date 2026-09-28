from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from d365_pqu.models import ChangeRecord

COMPARED_FIELDS = (
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
    "status_note",
)
STATION_FIELDS = (
    "sandbox_start_date",
    "sandbox_end_date",
    "production_start_date",
    "production_end_date",
)
GUIDANCE_DATASET_ID = "dataset"


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _change_id(parts: tuple[Any, ...]) -> str:
    payload = json.dumps(parts, default=str, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _entity_change(
    *,
    pqu_id: str,
    entity: str,
    change_type: str,
    field: str | None,
    old_value: Any,
    new_value: Any,
    source_commit: str,
    changed_at: str,
    identity: tuple[Any, ...],
) -> ChangeRecord:
    return ChangeRecord(
        change_id=_change_id(identity),
        changed_at=changed_at,
        pqu_id=pqu_id,
        entity=entity,
        change_type=change_type,
        field=field,
        old_value=_jsonable(old_value),
        new_value=_jsonable(new_value),
        source_commit=source_commit,
    )


def _pqu_changes(
    previous_records: list[dict[str, Any]],
    current_records: list[dict[str, Any]],
    *,
    source_commit: str,
    changed_at: str,
) -> list[ChangeRecord]:
    previous_by_id = {
        record["pqu_id"]: record
        for record in previous_records
        if isinstance(record, dict) and isinstance(record.get("pqu_id"), str)
    }
    current_by_id = {record["pqu_id"]: record for record in current_records}
    changes: list[ChangeRecord] = []

    for pqu_id in sorted(current_by_id.keys() - previous_by_id.keys()):
        record = current_by_id[pqu_id]
        changes.append(
            _entity_change(
                pqu_id=pqu_id,
                entity="pqu",
                change_type="added",
                field=None,
                old_value=None,
                new_value={field: record.get(field) for field in COMPARED_FIELDS},
                source_commit=source_commit,
                changed_at=changed_at,
                identity=(pqu_id, "pqu", "added", changed_at),
            )
        )
    for pqu_id in sorted(previous_by_id.keys() - current_by_id.keys()):
        record = previous_by_id[pqu_id]
        changes.append(
            _entity_change(
                pqu_id=pqu_id,
                entity="pqu",
                change_type="removed",
                field=None,
                old_value={field: record.get(field) for field in COMPARED_FIELDS},
                new_value=None,
                source_commit=source_commit,
                changed_at=changed_at,
                identity=(pqu_id, "pqu", "removed", changed_at),
            )
        )
    for pqu_id in sorted(previous_by_id.keys() & current_by_id.keys()):
        old_record = previous_by_id[pqu_id]
        new_record = current_by_id[pqu_id]
        for field in COMPARED_FIELDS:
            if field not in old_record:
                # Field introduced by a newer pipeline revision: a baseline, not a change.
                continue
            old_value = old_record.get(field)
            new_value = new_record.get(field)
            if old_value != new_value:
                changes.append(
                    _entity_change(
                        pqu_id=pqu_id,
                        entity="pqu",
                        change_type="modified",
                        field=field,
                        old_value=old_value,
                        new_value=new_value,
                        source_commit=source_commit,
                        changed_at=changed_at,
                        identity=(pqu_id, "pqu", field, changed_at),
                    )
                )
    return changes


def _station_changes(
    previous_stations: list[dict[str, Any]],
    current_stations: list[dict[str, Any]],
    *,
    source_commit: str,
    changed_at: str,
) -> list[ChangeRecord]:
    previous_by_key = {
        (row["pqu_id"], int(row["station"])): row
        for row in previous_stations
        if isinstance(row, dict) and row.get("pqu_id") and row.get("station") is not None
    }
    current_by_key = {
        (row["pqu_id"], int(row["station"])): row
        for row in current_stations
        if isinstance(row, dict) and row.get("pqu_id") and row.get("station") is not None
    }
    changes: list[ChangeRecord] = []
    for key in sorted(current_by_key.keys() - previous_by_key.keys()):
        row = current_by_key[key]
        changes.append(
            _entity_change(
                pqu_id=key[0],
                entity="station",
                change_type="added",
                field=f"station.{key[1]}",
                old_value=None,
                new_value={field: row.get(field) for field in STATION_FIELDS},
                source_commit=source_commit,
                changed_at=changed_at,
                identity=(key, "station", "added", changed_at),
            )
        )
    for key in sorted(previous_by_key.keys() - current_by_key.keys()):
        row = previous_by_key[key]
        changes.append(
            _entity_change(
                pqu_id=key[0],
                entity="station",
                change_type="removed",
                field=f"station.{key[1]}",
                old_value={field: row.get(field) for field in STATION_FIELDS},
                new_value=None,
                source_commit=source_commit,
                changed_at=changed_at,
                identity=(key, "station", "removed", changed_at),
            )
        )
    for key in sorted(previous_by_key.keys() & current_by_key.keys()):
        old_row = previous_by_key[key]
        new_row = current_by_key[key]
        for field in STATION_FIELDS:
            if field not in old_row:
                continue
            if old_row.get(field) != new_row.get(field):
                changes.append(
                    _entity_change(
                        pqu_id=key[0],
                        entity="station",
                        change_type="modified",
                        field=f"station.{key[1]}.{field}",
                        old_value=old_row.get(field),
                        new_value=new_row.get(field),
                        source_commit=source_commit,
                        changed_at=changed_at,
                        identity=(key, "station", field, changed_at),
                    )
                )
    return changes


def _region_changes(
    previous_regions: list[dict[str, Any]],
    current_regions: list[dict[str, Any]],
    *,
    source_commit: str,
    changed_at: str,
) -> list[ChangeRecord]:
    previous_by_key = {
        (int(row["station"]), str(row["region"])): row
        for row in previous_regions
        if isinstance(row, dict) and row.get("station") is not None and row.get("region")
    }
    current_by_key = {
        (int(row["station"]), str(row["region"])): row
        for row in current_regions
        if isinstance(row, dict) and row.get("station") is not None and row.get("region")
    }
    changes: list[ChangeRecord] = []
    for key in sorted(current_by_key.keys() - previous_by_key.keys()):
        changes.append(
            _entity_change(
                pqu_id="dataset",
                entity="region",
                change_type="added",
                field=f"region.{key[1]}",
                old_value=None,
                new_value=current_by_key[key],
                source_commit=source_commit,
                changed_at=changed_at,
                identity=(key, "region", "added", changed_at),
            )
        )
    for key in sorted(previous_by_key.keys() - current_by_key.keys()):
        changes.append(
            _entity_change(
                pqu_id="dataset",
                entity="region",
                change_type="removed",
                field=f"region.{key[1]}",
                old_value=previous_by_key[key],
                new_value=None,
                source_commit=source_commit,
                changed_at=changed_at,
                identity=(key, "region", "removed", changed_at),
            )
        )
    for key in sorted(previous_by_key.keys() & current_by_key.keys()):
        old_row = previous_by_key[key]
        new_row = current_by_key[key]
        # Compare only the fields the previous snapshot published.
        if any(old_row.get(field) != new_row.get(field) for field in old_row):
            changes.append(
                _entity_change(
                    pqu_id="dataset",
                    entity="region",
                    change_type="modified",
                    field=f"region.{key[1]}",
                    old_value=old_row,
                    new_value=new_row,
                    source_commit=source_commit,
                    changed_at=changed_at,
                    identity=(key, "region", "modified", changed_at),
                )
            )
    return changes


def _guidance_sections(
    articles: list[dict[str, Any]] | None,
) -> dict[tuple[str, str], dict[str, Any]]:
    sections: dict[tuple[str, str], dict[str, Any]] = {}
    for article in articles or []:
        if not isinstance(article, dict) or not isinstance(article.get("key"), str):
            continue
        for section in article.get("sections") or []:
            if isinstance(section, dict) and isinstance(section.get("id"), str):
                sections[(article["key"], section["id"])] = section
    return sections


def _guidance_summary(section: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": section.get("title"),
        "url": section.get("url"),
        "text_sha256": section.get("text_sha256"),
    }


def _guidance_changes(
    previous_articles: list[dict[str, Any]],
    current_articles: list[dict[str, Any]],
    *,
    source_commit: str,
    changed_at: str,
) -> list[ChangeRecord]:
    """Section-level changes in Microsoft's guidance text, for articles in both snapshots."""
    shared = {article.get("key") for article in previous_articles} & {
        article.get("key") for article in current_articles
    }
    article_commits = {
        article.get("key"): article.get("commit")
        for article in current_articles
        if isinstance(article.get("commit"), str)
    }
    previous = {
        key: section
        for key, section in _guidance_sections(previous_articles).items()
        if key[0] in shared
    }
    current = {
        key: section
        for key, section in _guidance_sections(current_articles).items()
        if key[0] in shared
    }
    changes: list[ChangeRecord] = []

    def change(key: tuple[str, str], change_type: str, old: Any, new: Any) -> ChangeRecord:
        article_commit = article_commits.get(key[0]) or source_commit
        return _entity_change(
            pqu_id=GUIDANCE_DATASET_ID,
            entity="guidance",
            change_type=change_type,
            field=f"{key[0]}#{key[1]}",
            old_value=old,
            new_value=new,
            source_commit=article_commit,
            changed_at=changed_at,
            identity=(key, "guidance", change_type, changed_at),
        )

    for key in sorted(current.keys() - previous.keys()):
        changes.append(change(key, "added", None, _guidance_summary(current[key])))
    for key in sorted(previous.keys() - current.keys()):
        changes.append(change(key, "removed", _guidance_summary(previous[key]), None))
    for key in sorted(previous.keys() & current.keys()):
        if previous[key].get("text_sha256") != current[key].get("text_sha256"):
            changes.append(
                change(
                    key,
                    "modified",
                    _guidance_summary(previous[key]),
                    _guidance_summary(current[key]),
                )
            )
    return changes


SERVICE_UPDATE_FIELDS = (
    "release_label",
    "is_major",
    "preview_date",
    "preview_latest_update_date",
    "general_availability_date",
    "first_autoupdate_date",
    "second_autoupdate_date",
    "end_of_service_date",
)
MAINTENANCE_WINDOW_FIELDS = ("start_time_utc", "days", "duration_hours", "duration_text")


@dataclass(frozen=True)
class KeyedRecords:
    """Records from one optional article, compared by a key field (version, geography, ...).

    ``previous``/``current`` are ``None`` when that snapshot did not publish the article; no
    changes are reported then, so a source becoming available is a baseline, not a change.
    """

    entity: str
    key: str
    fields: tuple[str, ...]
    previous: list[dict[str, Any]] | None
    current: list[dict[str, Any]] | None
    source_commit: str | None = None


def _keyed_changes(
    records: KeyedRecords, *, source_commit: str, changed_at: str
) -> list[ChangeRecord]:
    if records.previous is None or records.current is None:
        return []
    key = records.key
    old_by_key = {row[key]: row for row in records.previous if isinstance(row.get(key), str)}
    new_by_key = {row[key]: row for row in records.current if isinstance(row.get(key), str)}
    commit = records.source_commit or source_commit
    changes: list[ChangeRecord] = []

    def change(name: str, change_type: str, field: str | None, old: Any, new: Any) -> ChangeRecord:
        return _entity_change(
            pqu_id=GUIDANCE_DATASET_ID,
            entity=records.entity,
            change_type=change_type,
            field=f"{name}#{field}" if field else name,
            old_value=old,
            new_value=new,
            source_commit=commit,
            changed_at=changed_at,
            identity=(name, records.entity, field or change_type, changed_at),
        )

    def summary(row: dict[str, Any]) -> dict[str, Any]:
        return {field: row.get(field) for field in records.fields}

    for name in sorted(new_by_key.keys() - old_by_key.keys()):
        changes.append(change(name, "added", None, None, summary(new_by_key[name])))
    for name in sorted(old_by_key.keys() - new_by_key.keys()):
        changes.append(change(name, "removed", None, summary(old_by_key[name]), None))
    for name in sorted(old_by_key.keys() & new_by_key.keys()):
        old_row = old_by_key[name]
        new_row = new_by_key[name]
        for field in records.fields:
            if field in old_row and old_row.get(field) != new_row.get(field):
                changes.append(
                    change(name, "modified", field, old_row.get(field), new_row.get(field))
                )
    return changes


def compute_changes(
    previous_records: list[dict[str, Any]] | None,
    current_records: list[dict[str, Any]],
    *,
    source_commit: str,
    changed_at: datetime,
    previous_stations: list[dict[str, Any]] | None = None,
    current_stations: list[dict[str, Any]] | None = None,
    previous_regions: list[dict[str, Any]] | None = None,
    current_regions: list[dict[str, Any]] | None = None,
    previous_articles: list[dict[str, Any]] | None = None,
    current_articles: list[dict[str, Any]] | None = None,
    keyed: Sequence[KeyedRecords] = (),
) -> list[ChangeRecord]:
    if previous_records is None:
        return []
    timestamp = _iso(changed_at)
    changes = _pqu_changes(
        previous_records,
        current_records,
        source_commit=source_commit,
        changed_at=timestamp,
    )
    if previous_stations is not None and current_stations is not None:
        changes.extend(
            _station_changes(
                previous_stations,
                current_stations,
                source_commit=source_commit,
                changed_at=timestamp,
            )
        )
    if previous_regions is not None and current_regions is not None:
        changes.extend(
            _region_changes(
                previous_regions,
                current_regions,
                source_commit=source_commit,
                changed_at=timestamp,
            )
        )
    if previous_articles is not None and current_articles is not None:
        changes.extend(
            _guidance_changes(
                previous_articles,
                current_articles,
                source_commit=source_commit,
                changed_at=timestamp,
            )
        )
    for records in keyed:
        changes.extend(_keyed_changes(records, source_commit=source_commit, changed_at=timestamp))
    return changes
