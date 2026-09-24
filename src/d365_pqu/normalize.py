from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any

from d365_pqu.config import ALLOWED_STATUSES
from d365_pqu.errors import ParserError
from d365_pqu.models import (
    NormalizedDataset,
    ParsedSource,
    PquRecord,
    QualityItem,
    RecordSource,
    RegionRecord,
    SourceDocument,
    SourceProvenance,
    StationRecord,
    VersionRecord,
)
from d365_pqu.parser import plain_text

MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
DATE_WITH_YEAR = re.compile(r"^(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2}),\s*(?P<year>\d{4})$")
DATE_NO_YEAR = re.compile(r"^(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2})$")
RELEASE_TRAIN = re.compile(r"^(?P<app>\d+\.\d+\.\d+)\s+(?P<train>PQU-\d+)$", re.IGNORECASE)
STATION_LABEL = re.compile(r"^Station\s+(\d+)$", re.IGNORECASE)

TRACKED_FIELDS = (
    "change_cutoff_date",
    "train_start_date",
    "train_end_date",
    "status",
    "application_build",
    "platform_build",
    "uep_version",
    "station_schedule_available",
)


def _parse_month_day(value: str) -> tuple[int, int]:
    no_year = DATE_NO_YEAR.match(value.strip())
    if not no_year:
        raise ParserError(f"Could not parse month and day from {value!r}")
    month_name = no_year.group("month").lower()
    if month_name not in MONTHS:
        raise ParserError(f"Unknown month name in {value!r}")
    return MONTHS[month_name], int(no_year.group("day"))


def parse_date(value: str, default_year: int | None = None) -> date:
    text = value.strip()
    match = DATE_WITH_YEAR.match(text)
    if match:
        month_name = match.group("month").lower()
        if month_name not in MONTHS:
            raise ParserError(f"Unknown month name in {value!r}")
        try:
            return date(int(match.group("year")), MONTHS[month_name], int(match.group("day")))
        except ValueError as exc:
            raise ParserError(f"Invalid calendar date {value!r}: {exc}") from exc
    if default_year is not None:
        month, day = _parse_month_day(text)
        try:
            return date(default_year, month, day)
        except ValueError as exc:
            raise ParserError(f"Invalid calendar date {value!r}: {exc}") from exc
    raise ParserError(f"Date was missing a year and no default was available: {value!r}")


def parse_date_iso(value: str, default_year: int | None = None) -> str:
    return parse_date(value, default_year=default_year).isoformat()


def parse_date_range(value: str) -> tuple[str | None, str | None]:
    text = value.strip()
    if text in {"", "-", "N/A", "NA", "n/a"}:
        return None, None
    parts = re.split(r"\s+to\s+", text, maxsplit=1)
    if len(parts) != 2:
        raise ParserError(f"Could not parse date range: {value!r}")
    end = parse_date(parts[1].strip())
    start = parse_date(parts[0].strip(), default_year=end.year)
    if start.month > end.month:
        start = parse_date(parts[0].strip(), default_year=end.year - 1)
    if end < start:
        raise ParserError(f"Date range ended before it started: {value!r}")
    return start.isoformat(), end.isoformat()


def _clean_build(value: str) -> str | None:
    text = value.strip()
    if text in {"", "-", "N/A", "NA", "--"}:
        return None
    return text


def canonical_status(value: str) -> str:
    text = " ".join(value.split())
    lowered = text.lower()
    aliases = {
        "completed": "Completed",
        "in-progress": "In-Progress",
        "in progress": "In-Progress",
        "not started": "Not Started",
        "notstarted": "Not Started",
        "canceled": "Canceled",
        "cancelled": "Canceled",
    }
    if lowered in aliases:
        return aliases[lowered]
    return text


def _record_source(source: SourceDocument) -> RecordSource:
    return {
        "publisher": "Microsoft",
        "repository": "MicrosoftDocs/dynamics-365-unified-operations-public",
        "commit": source.source_commit,
        "url": source.article_url,
        "raw_url": source.raw_url,
    }


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _previous_records(previous: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not previous:
        return {}
    records = previous.get("records")
    if not isinstance(records, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        if isinstance(record, dict) and isinstance(record.get("pqu_id"), str):
            result[record["pqu_id"]] = record
    return result


def _tracked(record: dict[str, Any]) -> dict[str, Any]:
    return {field: record.get(field) for field in TRACKED_FIELDS}


def _first_seen(previous_record: dict[str, Any] | None, observed_at: datetime) -> str:
    if previous_record and isinstance(previous_record.get("first_seen_at"), str):
        return previous_record["first_seen_at"]
    return _iso(observed_at)


def _last_changed(
    previous_record: dict[str, Any] | None,
    current: dict[str, Any],
    observed_at: datetime,
) -> str:
    if previous_record is None:
        return _iso(observed_at)
    if _tracked(previous_record) != _tracked(current):
        return _iso(observed_at)
    previous_value = previous_record.get("last_changed_at")
    return previous_value if isinstance(previous_value, str) else _iso(observed_at)


def _quality(
    code: str,
    severity: str,
    message: str,
    pqu_id: str | None = None,
    field: str | None = None,
) -> QualityItem:
    return QualityItem(
        code=code,
        severity=severity,
        message=message,
        pqu_id=pqu_id,
        field=field,
    )


def normalize_source(
    parsed: ParsedSource,
    source: SourceDocument,
    *,
    previous: dict[str, Any] | None = None,
    observed_at: datetime | None = None,
) -> NormalizedDataset:
    moment = observed_at or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    record_source = _record_source(source)
    previous_records = _previous_records(previous)
    quality: list[QualityItem] = [
        _quality("source-warning", "warning", message) for message in source.warnings
    ]
    quality.extend(_quality("source-warning", "warning", message) for message in parsed.warnings)

    records: list[PquRecord] = []
    seen_ids: set[str] = set()
    for row in parsed.train_rows:
        release_match = RELEASE_TRAIN.match(row.release_train)
        if not release_match:
            quality.append(
                _quality(
                    "invalid-release-train",
                    "error",
                    f"Could not parse PQU release train {row.release_train!r}",
                )
            )
            continue
        application_version = release_match.group("app")
        pqu_train = release_match.group("train").upper()
        pqu_id = f"{application_version}-{pqu_train}"
        if pqu_id in seen_ids:
            quality.append(
                _quality(
                    "duplicate-pqu-id",
                    "error",
                    f"Duplicate PQU identifier {pqu_id}",
                    pqu_id=pqu_id,
                )
            )
            continue
        seen_ids.add(pqu_id)
        status = canonical_status(row.status)
        if status not in ALLOWED_STATUSES:
            quality.append(
                _quality(
                    "unknown-status",
                    "error",
                    f"Unknown PQU status {row.status!r}",
                    pqu_id=pqu_id,
                    field="status",
                )
            )
        try:
            start_date, end_date = parse_date_range(row.train_duration)
        except ParserError as exc:
            quality.append(
                _quality(
                    "invalid-train-duration",
                    "error",
                    str(exc),
                    pqu_id=pqu_id,
                    field="train_end_date",
                )
            )
            start_date, end_date = None, None
        cutoff = None
        try:
            cutoff = parse_date_iso(row.change_cutoff)
        except ParserError as exc:
            quality.append(
                _quality(
                    "invalid-cutoff-date",
                    "error",
                    str(exc),
                    pqu_id=pqu_id,
                    field="change_cutoff_date",
                )
            )
        if start_date and end_date and end_date < start_date:
            quality.append(
                _quality(
                    "end-before-start",
                    "error",
                    f"Train end date {end_date} is before start date {start_date}",
                    pqu_id=pqu_id,
                    field="train_end_date",
                )
            )
        if cutoff and start_date and cutoff[:4] != start_date[:4]:
            quality.append(
                _quality(
                    "cutoff-start-year-mismatch",
                    "warning",
                    f"Change cutoff {cutoff} and train start {start_date} are in different years",
                    pqu_id=pqu_id,
                    field="change_cutoff_date",
                )
            )
        record = PquRecord(
            pqu_id=pqu_id,
            application_version=application_version,
            pqu_train=pqu_train,
            release_number=int(pqu_train.split("-")[1]),
            change_cutoff_date=cutoff,
            train_start_date=start_date,
            train_end_date=end_date,
            status=status,
            application_build=_clean_build(row.application_version),
            platform_build=_clean_build(row.platform_version),
            uep_version=None,
            station_schedule_available=False,
            first_seen_at="",
            last_changed_at="",
            source=record_source,
        )
        records.append(record)

    station_records: list[StationRecord] = []
    matched_ids: set[str] = set()
    for schedule in parsed.station_schedules:
        schedule_pqu_id = schedule.release_train.replace(" ", "-")
        matches = [record for record in records if record["pqu_id"] == schedule_pqu_id]
        if len(matches) == 1:
            master = matches[0]
            if (
                master["application_version"] != schedule.application_version
                or master["application_build"] != schedule.application_build
                or master["platform_build"] != schedule.platform_build
            ):
                quality.append(
                    _quality(
                        "station-schedule-build-mismatch",
                        "error",
                        (
                            f"Station schedule {schedule.release_train} has app "
                            f"{schedule.application_build} and platform {schedule.platform_build}, "
                            f"but the master record has app {master['application_build']} and "
                            f"platform {master['platform_build']}"
                        ),
                        pqu_id=schedule_pqu_id,
                    )
                )
                matches = []
        if len(matches) != 1:
            quality.append(
                _quality(
                    "station-schedule-match",
                    "error",
                    (
                        f"Station schedule {schedule.release_train} "
                        f"(app {schedule.application_build}, platform {schedule.platform_build}) "
                        f"matched {len(matches)} master records"
                    ),
                )
            )
            continue
        master = matches[0]
        pqu_id = master["pqu_id"]
        if pqu_id in matched_ids:
            quality.append(
                _quality(
                    "duplicate-station-schedule",
                    "error",
                    f"More than one detailed station schedule was published for {pqu_id}",
                    pqu_id=pqu_id,
                )
            )
            continue
        matched_ids.add(pqu_id)
        if master["uep_version"] is None and schedule.uep_version:
            master["uep_version"] = schedule.uep_version
        master["station_schedule_available"] = True
        for station_row in schedule.rows:
            label_match = STATION_LABEL.match(station_row.station)
            if not label_match:
                quality.append(
                    _quality(
                        "invalid-station",
                        "error",
                        f"Could not parse station label {station_row.station!r}",
                        pqu_id=pqu_id,
                        field="station",
                    )
                )
                continue
            station = int(label_match.group(1))
            if station not in range(1, 7):
                quality.append(
                    _quality(
                        "invalid-station",
                        "error",
                        f"Station {station} is outside the supported range",
                        pqu_id=pqu_id,
                        field="station",
                    )
                )
                continue
            try:
                sandbox_start, sandbox_end = parse_date_range(station_row.sandbox_schedule)
                production_start, production_end = parse_date_range(station_row.production_schedule)
            except ParserError as exc:
                quality.append(
                    _quality(
                        "invalid-station-dates",
                        "error",
                        str(exc),
                        pqu_id=pqu_id,
                        field=f"station_{station}",
                    )
                )
                continue
            station_records.append(
                StationRecord(
                    pqu_id=pqu_id,
                    application_version=master["application_version"],
                    pqu_train=master["pqu_train"],
                    release_number=master["release_number"],
                    station=station,
                    station_label=f"Station {station}",
                    sandbox_start_date=sandbox_start,
                    sandbox_end_date=sandbox_end,
                    production_start_date=production_start,
                    production_end_date=production_end,
                    source=record_source,
                )
            )

    region_records: list[RegionRecord] = []
    for region_row in parsed.region_rows:
        label_match = STATION_LABEL.match(plain_text(region_row.station))
        if not label_match:
            quality.append(
                _quality(
                    "invalid-station-region",
                    "error",
                    f"Could not parse station label {region_row.station!r}",
                    field="station",
                )
            )
            continue
        station = int(label_match.group(1))
        regions = [
            part.strip() for part in plain_text(region_row.regions).split(",") if part.strip()
        ]
        if not regions:
            quality.append(
                _quality(
                    "empty-region-mapping",
                    "error",
                    f"Station {region_row.station!r} has no region mapping",
                    field="regions",
                )
            )
            continue
        is_region = not (len(regions) == 1 and regions[0].lower().startswith("only for opted-in"))
        for region in regions:
            region_records.append(
                RegionRecord(
                    station=station,
                    station_label=f"Station {station}",
                    region=region,
                    is_region=is_region,
                )
            )

    records.sort(
        key=lambda item: (
            tuple(int(part) for part in item["application_version"].split(".")),
            item["release_number"],
        )
    )
    station_records.sort(
        key=lambda item: (
            tuple(int(part) for part in item["application_version"].split(".")),
            item["release_number"],
            item["station"],
        )
    )
    region_records.sort(key=lambda item: (item["station"], item["region"]))

    for record in records:
        previous_record = previous_records.get(record["pqu_id"])
        record["first_seen_at"] = _first_seen(previous_record, moment)
        record["last_changed_at"] = _last_changed(previous_record, dict(record), moment)

    versions = [
        VersionRecord(
            pqu_id=record["pqu_id"],
            application_version=record["application_version"],
            pqu_train=record["pqu_train"],
            release_number=record["release_number"],
            status=record["status"],
            application_build=record["application_build"],
            platform_build=record["platform_build"],
            uep_version=record["uep_version"],
            change_cutoff_date=record["change_cutoff_date"],
            train_start_date=record["train_start_date"],
            train_end_date=record["train_end_date"],
        )
        for record in records
    ]

    provenance = SourceProvenance(
        publisher="Microsoft",
        repository="MicrosoftDocs/dynamics-365-unified-operations-public",
        branch="main",
        file_path="articles/fin-ops-core/dev-itpro/get-started/quality-updates-schedule.md",
        commit=source.source_commit,
        article_url=source.article_url,
        raw_url=source.raw_url,
        markdown_date=source.markdown_date,
        sha256=source.sha256,
        retrieved_at=_iso(source.retrieved_at),
    )

    return NormalizedDataset(
        source=provenance,
        records=records,
        stations=station_records,
        regions=region_records,
        versions=versions,
        changes=[],
        quality=quality,
        observed_at=moment,
        generated_at=moment,
        previous_metadata=previous.get("metadata") if previous else None,
    )
