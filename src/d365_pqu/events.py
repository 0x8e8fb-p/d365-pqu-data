"""Key dates from the published data: one event per change cutoff, train, station window, and
service update milestone.

Event identifiers name what an event is, not when it happens
(``production_window:10.0.48-PQU-6:station-4``), so an event keeps its identifier when Microsoft
moves its dates. Feeds and calendar subscriptions then update the event instead of adding a
second one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from d365_pqu.config import SOURCE_SPECS_BY_KEY
from d365_pqu.insights import DATE_FLAG_FIELDS

Row = Mapping[str, Any]

# kind -> (category, label used in titles)
EVENT_KINDS: dict[str, tuple[str, str]] = {
    "change_cutoff": ("train", "change cutoff"),
    "train_window": ("train", "train"),
    "sandbox_window": ("station", "sandbox"),
    "production_window": ("station", "production"),
    "preview": ("service_update", "preview"),
    "preview_latest_update": ("service_update", "latest preview update"),
    "general_availability": ("service_update", "general availability"),
    "autoupdate_first": ("service_update", "first autoupdate (production)"),
    "autoupdate_second": ("service_update", "second autoupdate (production)"),
    "end_of_service": ("service_update", "end of service"),
}
KIND_ORDER = {kind: index for index, kind in enumerate(EVENT_KINDS)}
SERVICE_UPDATE_FIELDS = {
    "preview": "preview_date",
    "preview_latest_update": "preview_latest_update_date",
    "general_availability": "general_availability_date",
    "autoupdate_first": "first_autoupdate_date",
    "autoupdate_second": "second_autoupdate_date",
    "end_of_service": "end_of_service_date",
}
# The published date fields each train event is built from.
TRAIN_EVENT_FIELDS = {
    "change_cutoff": ("change_cutoff_date",),
    "train_window": ("train_start_date", "train_end_date"),
}
# Learn dataset placeholder whose section explains each category's dates.
SECTION_DATASETS = {"train": "trains", "station": "stations", "service_update": "service_updates"}
CATEGORY_SOURCES = {"train": "schedule", "station": "schedule", "service_update": "service_updates"}
EVENT_FIELDS = (
    "id",
    "kind",
    "category",
    "title",
    "start_date",
    "end_date",
    "pqu_id",
    "application_version",
    "station",
    "status",
    "source_key",
    "url",
    "warnings",
)


def _day(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _version_key(version: Any) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in str(version).split("."))
    except ValueError:
        return (0,)


def section_urls(articles: Sequence[Row]) -> dict[str, str]:
    """URL of the article section that holds each dataset, falling back to the article."""
    urls: dict[str, str] = {}
    for category, dataset in SECTION_DATASETS.items():
        for article in articles:
            for section in article.get("sections") or []:
                blocks = section.get("blocks") or []
                if any(b.get("type") == "dataset" and b.get("name") == dataset for b in blocks):
                    urls.setdefault(category, str(section.get("url")))
        if category not in urls:
            urls[category] = SOURCE_SPECS_BY_KEY[CATEGORY_SOURCES[category]].article_url
    return urls


def _train_warnings(quality: Sequence[Row]) -> dict[str, dict[str, set[str]]]:
    """pqu_id -> date field -> warning codes that make the field unreliable."""
    flags: dict[str, dict[str, set[str]]] = {}
    for item in quality:
        pqu_id = item.get("pqu_id")
        if item.get("severity") != "warning" or not pqu_id:
            continue
        code = str(item.get("code"))
        fields = DATE_FLAG_FIELDS.get(code, (item["field"],) if item.get("field") else ())
        for field in fields:
            flags.setdefault(str(pqu_id), {}).setdefault(field, set()).add(code)
    return flags


def _field_warnings(quality: Sequence[Row]) -> dict[str, set[str]]:
    """ "10.0.49#general_availability_date" -> warning codes (service update findings)."""
    flags: dict[str, set[str]] = {}
    for item in quality:
        field = item.get("field")
        if item.get("severity") == "warning" and not item.get("pqu_id") and field:
            flags.setdefault(str(field), set()).add(str(item.get("code")))
    return flags


def _event(
    kind: str,
    subject: str,
    *,
    title: str,
    start: str,
    end: str | None,
    urls: Mapping[str, str],
    pqu_id: str | None = None,
    version: str | None = None,
    station: int | None = None,
    status: str | None = None,
    warnings: set[str] | None = None,
) -> dict[str, Any]:
    category = EVENT_KINDS[kind][0]
    finish = end if end and end >= start else start
    return {
        "id": f"{kind}:{subject}",
        "kind": kind,
        "category": category,
        "title": title,
        "start_date": start,
        "end_date": finish,
        "pqu_id": pqu_id,
        "application_version": version,
        "station": station,
        "status": status,
        "source_key": CATEGORY_SOURCES[category],
        "url": urls[category],
        "warnings": sorted(warnings or ()),
    }


def build_events(
    *,
    records: Sequence[Row],
    stations: Sequence[Row],
    service_updates: Sequence[Row],
    articles: Sequence[Row],
    quality: Sequence[Row],
) -> list[dict[str, Any]]:
    urls = section_urls(articles)
    train_flags = _train_warnings(quality)
    field_flags = _field_warnings(quality)
    by_id = {str(record["pqu_id"]): record for record in records}
    events: list[dict[str, Any]] = []

    for record in records:
        pqu_id = str(record["pqu_id"])
        label = f"{record['application_version']} {record['pqu_train']}"
        flags = train_flags.get(pqu_id, {})

        def warnings_for(kind: str, flags: dict[str, set[str]] = flags) -> set[str]:
            found: set[str] = set()
            for field in TRAIN_EVENT_FIELDS[kind]:
                found |= flags.get(field, set())
            return found

        version = str(record["application_version"])
        status = str(record["status"])
        cutoff = _day(record.get("change_cutoff_date"))
        if cutoff:
            events.append(
                _event(
                    "change_cutoff",
                    pqu_id,
                    title=f"{label} change cutoff",
                    start=cutoff,
                    end=None,
                    urls=urls,
                    pqu_id=pqu_id,
                    version=version,
                    status=status,
                    warnings=warnings_for("change_cutoff"),
                )
            )
        start = _day(record.get("train_start_date"))
        if start:
            events.append(
                _event(
                    "train_window",
                    pqu_id,
                    title=f"{label} train",
                    start=start,
                    end=_day(record.get("train_end_date")),
                    urls=urls,
                    pqu_id=pqu_id,
                    version=version,
                    status=status,
                    warnings=warnings_for("train_window"),
                )
            )

    for row in stations:
        pqu_id = str(row["pqu_id"])
        record = by_id.get(pqu_id, {})
        station = int(row["station"])
        label = f"{row['application_version']} {row['pqu_train']}"
        for kind, prefix in (("sandbox_window", "sandbox"), ("production_window", "production")):
            start = _day(row.get(f"{prefix}_start_date"))
            if not start:
                continue
            events.append(
                _event(
                    kind,
                    f"{pqu_id}:station-{station}",
                    title=f"{label} · Station {station} {EVENT_KINDS[kind][1]}",
                    start=start,
                    end=_day(row.get(f"{prefix}_end_date")),
                    urls=urls,
                    pqu_id=pqu_id,
                    version=str(row["application_version"]),
                    station=station,
                    status=str(record["status"]) if record.get("status") else None,
                )
            )

    for update in service_updates:
        version = str(update["version"])
        for kind, field in SERVICE_UPDATE_FIELDS.items():
            day = _day(update.get(field))
            if not day:
                continue
            events.append(
                _event(
                    kind,
                    version,
                    title=f"{version} {EVENT_KINDS[kind][1]}",
                    start=day,
                    end=None,
                    urls=urls,
                    version=version,
                    warnings=field_flags.get(f"{version}#{field}"),
                )
            )

    events.sort(
        key=lambda event: (
            event["start_date"],
            KIND_ORDER[event["kind"]],
            _version_key(event["application_version"]),
            int(by_id.get(str(event["pqu_id"]), {}).get("release_number") or 0),
            event["station"] or 0,
            event["id"],
        )
    )
    return events
