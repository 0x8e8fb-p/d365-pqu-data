from __future__ import annotations

import hashlib
import json
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
)
STATION_FIELDS = (
    "sandbox_start_date",
    "sandbox_end_date",
    "production_start_date",
    "production_end_date",
)


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
                field=None,
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
                field=None,
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
        if old_row != new_row:
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
    return changes
