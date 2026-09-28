from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import date
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from d365_pqu.config import ALLOWED_STATUSES
from d365_pqu.errors import ValidationError
from d365_pqu.models import NormalizedDataset, QualityItem

APPLICATION_BUILD = re.compile(r"^\d+\.\d+\.\d+\.\d+$")
PLATFORM_BUILD = re.compile(r"^\d+\.\d+\.\d+\.\d+$")
UEP_VERSION = re.compile(r"^\d+\.\d+\.\d+\.\d+$")
APPLICATION_VERSION = re.compile(r"^\d+\.\d+\.\d+$")
PQU_TRAIN = re.compile(r"^PQU-\d+$")
SERVICE_UPDATE_DATES = (
    "preview_date",
    "preview_latest_update_date",
    "general_availability_date",
    "first_autoupdate_date",
    "second_autoupdate_date",
    "end_of_service_date",
)


def validate_service_updates(records: Iterable[Mapping[str, Any]]) -> None:
    seen: set[str] = set()
    for record in records:
        version = record.get("version")
        if not isinstance(version, str) or not APPLICATION_VERSION.match(version):
            raise ValidationError(f"Invalid service update version {version!r}")
        if version in seen:
            raise ValidationError(f"Duplicate service update version {version}")
        seen.add(version)
        for field in SERVICE_UPDATE_DATES:
            value = record.get(field)
            if value is None:
                continue
            try:
                date.fromisoformat(str(value))
            except ValueError as exc:
                raise ValidationError(f"Invalid {field} for service update {version}") from exc


START_TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
WEEKDAY_NAMES = frozenset(
    ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
)


def validate_maintenance_windows(records: Iterable[Mapping[str, Any]]) -> None:
    seen: set[str] = set()
    for record in records:
        geo = record.get("geo")
        if not isinstance(geo, str) or not geo.strip():
            raise ValidationError(f"Invalid maintenance window geography {geo!r}")
        if geo.casefold() in seen:
            raise ValidationError(f"Duplicate maintenance window geography {geo}")
        seen.add(geo.casefold())
        if not START_TIME.match(str(record.get("start_time_utc") or "")):
            raise ValidationError(f"Invalid maintenance window start time for {geo}")
        days = record.get("days")
        if (
            not isinstance(days, list)
            or not days
            or len(set(days)) != len(days)
            or not set(days) <= WEEKDAY_NAMES
        ):
            raise ValidationError(f"Invalid maintenance window days for {geo}")
        duration = record.get("duration_hours")
        if duration is not None and not (isinstance(duration, int | float) and 0 < duration <= 24):
            raise ValidationError(f"Invalid maintenance window duration for {geo}")


def validate_region_geos(
    regions: Iterable[Mapping[str, Any]], windows: Iterable[Mapping[str, Any]]
) -> None:
    geos = {str(window.get("geo")) for window in windows}
    for region in regions:
        geo = region.get("maintenance_geo")
        if geo is not None and geo not in geos:
            raise ValidationError(
                f"Region {region.get('region')} refers to unknown maintenance geography {geo!r}"
            )


def _fatal(items: list[QualityItem]) -> list[QualityItem]:
    return [item for item in items if item["severity"] == "error"]


def validate_quality(dataset: NormalizedDataset) -> None:
    errors = _fatal(dataset.quality)
    if errors:
        messages = "; ".join(f"{item['code']}: {item['message']}" for item in errors[:10])
        raise ValidationError(f"Fatal data quality errors: {messages}")


def validate_records(dataset: NormalizedDataset) -> None:
    if not dataset.records:
        raise ValidationError("Dataset contained no PQU train records")
    seen: set[str] = set()
    for record in dataset.records:
        pqu_id = record["pqu_id"]
        if pqu_id in seen:
            raise ValidationError(f"Duplicate PQU identifier {pqu_id}")
        seen.add(pqu_id)
        if not APPLICATION_VERSION.match(record["application_version"]):
            raise ValidationError(f"Invalid application version for {pqu_id}")
        if not PQU_TRAIN.match(record["pqu_train"]):
            raise ValidationError(f"Invalid PQU train for {pqu_id}")
        if record["status"] not in ALLOWED_STATUSES:
            raise ValidationError(f"Invalid status for {pqu_id}: {record['status']!r}")
        if record["application_build"] and not APPLICATION_BUILD.match(record["application_build"]):
            raise ValidationError(f"Invalid application build for {pqu_id}")
        if record["platform_build"] and not PLATFORM_BUILD.match(record["platform_build"]):
            raise ValidationError(f"Invalid platform build for {pqu_id}")
        if record["uep_version"] and not UEP_VERSION.match(record["uep_version"]):
            raise ValidationError(f"Invalid UEP version for {pqu_id}")
        start = record["train_start_date"]
        end = record["train_end_date"]
        if start and end and date.fromisoformat(end) < date.fromisoformat(start):
            raise ValidationError(f"Train end date precedes start date for {pqu_id}")
    station_keys: set[tuple[str, int]] = set()
    station_groups: dict[str, set[int]] = {}
    for station in dataset.stations:
        key = (station["pqu_id"], station["station"])
        if key in station_keys:
            raise ValidationError(f"Duplicate station row for {station['pqu_id']} station {key[1]}")
        station_keys.add(key)
        if station["station"] not in range(1, 7):
            raise ValidationError(
                f"Unsupported station {station['station']} for {station['pqu_id']}"
            )
        if station["pqu_id"] not in {record["pqu_id"] for record in dataset.records}:
            raise ValidationError(f"Station schedule references unknown PQU {station['pqu_id']}")
        station_groups.setdefault(station["pqu_id"], set()).add(station["station"])
    for pqu_id, stations in station_groups.items():
        if stations != set(range(1, 7)):
            raise ValidationError(
                f"Station schedule for {pqu_id} does not cover stations 1 through 6"
            )

    region_keys: set[tuple[int, str]] = set()
    region_stations: set[int] = set()
    for region in dataset.regions:
        if region["station"] not in range(1, 7):
            raise ValidationError(f"Unsupported region station {region['station']}")
        region_key = (region["station"], region["region"])
        if region_key in region_keys:
            raise ValidationError(
                f"Duplicate region mapping for station {region_key[0]}: {region_key[1]}"
            )
        region_keys.add(region_key)
        region_stations.add(region["station"])
    if region_stations != set(range(1, 7)):
        raise ValidationError("Region mapping does not cover stations 1 through 6")


def validate_document(document: dict[str, Any], schema_path: Path) -> None:
    import json

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    if errors:
        raise ValidationError(f"{schema_path.name}: {_format_schema_error(errors[0])}")


def _format_schema_error(error: JsonSchemaValidationError) -> str:
    location = "/".join(str(part) for part in error.absolute_path)
    prefix = f"{location}: " if location else ""
    return f"{prefix}{error.message}"
