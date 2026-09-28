"""Service update lifecycle dates from Microsoft's "Service update availability" article."""

from __future__ import annotations

import re
from datetime import date
from itertools import pairwise
from typing import Any

from d365_pqu import mdtext
from d365_pqu.errors import ParserError
from d365_pqu.learn import ArticleRules
from d365_pqu.models import QualityItem

SERVICE_UPDATE_HEADERS = (
    "Release version",
    "Preview availability",
    "Preview latest possible update",
    "General availability (self-update)",
    "First autoupdate schedule for production start date",
    "Second autoupdate schedule for production start date",
    "End of service",
)
DATE_FIELDS = (
    "preview_date",
    "preview_latest_update_date",
    "general_availability_date",
    "first_autoupdate_date",
    "second_autoupdate_date",
    "end_of_service_date",
)
FIELD_LABELS = {
    "preview_date": "Preview availability",
    "preview_latest_update_date": "Preview latest possible update",
    "general_availability_date": "General availability",
    "first_autoupdate_date": "First autoupdate (production)",
    "second_autoupdate_date": "Second autoupdate (production)",
    "end_of_service_date": "End of service",
}
SERVICE_UPDATE_RULES = ArticleRules(dataset_tables={SERVICE_UPDATE_HEADERS: "service_updates"})

# "CY26Q4: 10.0.49*" -> label CY26Q4, version 10.0.49, asterisk marks a major release.
RELEASE_VERSION = re.compile(
    r"^(?:(?P<label>[A-Za-z0-9]+)\s*:\s*)?(?P<version>\d+\.\d+\.\d+)\s*(?P<major>\*)?$"
)
FULL_DATE = re.compile(r"^(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2}),\s*(?P<year>\d{4})$")
BLANK = {"", "-", "\u2013", "\u2014", "n/a", "na", "tbd", "tba"}
MONTHS = {
    name: index
    for index, name in enumerate(
        (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ),
        start=1,
    )
}


def _quality(code: str, message: str, field: str | None = None) -> QualityItem:
    return QualityItem(code=code, severity="warning", message=message, pqu_id=None, field=field)


def find_table(markdown: str) -> tuple[tuple[str, ...], ...]:
    """The service update schedule table (header matched ignoring case and spacing)."""
    rows = mdtext.find_table(markdown, SERVICE_UPDATE_HEADERS)
    if rows is None:
        raise ParserError("Service update schedule table was not found or its headers changed")
    return rows


def _parse_date(value: str) -> str | None:
    text = mdtext.collapse(value)
    if text.casefold() in BLANK:
        return None
    match = FULL_DATE.match(text)
    if not match or match.group("month").casefold() not in MONTHS:
        raise ValueError(f"unrecognized date {value!r}")
    return date(
        int(match.group("year")), MONTHS[match.group("month").casefold()], int(match.group("day"))
    ).isoformat()


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def parse_service_updates(markdown: str) -> tuple[list[dict[str, Any]], list[QualityItem]]:
    """Normalized service update records sorted by version, plus non-fatal findings.

    Rows that cannot be read become warnings; a table with no readable rows is a parser error so
    the previously published lifecycle data is kept.
    """
    rows = find_table(markdown)
    records: list[dict[str, Any]] = []
    quality: list[QualityItem] = []
    seen: set[str] = set()
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != len(SERVICE_UPDATE_HEADERS):
            quality.append(
                _quality("service-update-row-invalid", f"Unexpected column count: {row!r}")
            )
            continue
        match = RELEASE_VERSION.match(mdtext.collapse(row[0]))
        if not match:
            quality.append(
                _quality("service-update-row-invalid", f"Could not read release version {row[0]!r}")
            )
            continue
        version = match.group("version")
        if version in seen:
            quality.append(
                _quality(
                    "service-update-duplicate", f"Service update {version} is listed twice", version
                )
            )
            continue
        record: dict[str, Any] = {
            "version": version,
            "release_label": match.group("label"),
            "is_major": bool(match.group("major")),
        }
        for field, cell in zip(DATE_FIELDS, row[1:], strict=True):
            try:
                record[field] = _parse_date(cell)
            except (ValueError, OverflowError) as exc:
                quality.append(
                    _quality(
                        "service-update-date-invalid",
                        f"Service update {version} {FIELD_LABELS[field]}: {exc}",
                        f"{version}#{field}",
                    )
                )
                record[field] = None
        seen.add(version)
        records.append(record)
        dated = [(field, record[field]) for field in DATE_FIELDS if record[field]]
        for (left, left_value), (right, right_value) in pairwise(dated):
            if right_value < left_value:
                quality.append(
                    _quality(
                        "service-update-dates-out-of-order",
                        (
                            f"Service update {version}: {FIELD_LABELS[right]} {right_value} is "
                            f"before {FIELD_LABELS[left]} {left_value}"
                        ),
                        f"{version}#{right}",
                    )
                )
    if not records:
        raise ParserError("Service update schedule table contained no readable rows")
    records.sort(key=lambda item: _version_key(item["version"]))
    return records, quality
