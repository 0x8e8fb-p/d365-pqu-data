from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from markdown_it import MarkdownIt

from d365_pqu.errors import ParserError
from d365_pqu.models import (
    ParsedRegionRow,
    ParsedSource,
    ParsedStationRow,
    ParsedStationSchedule,
    ParsedTrainRow,
)

TRAIN_HEADERS = (
    "PQU release train",
    "Change cutoff date",
    "PQU train duration",
    "Status",
    "Application Version",
    "Platform Version",
)
REGION_HEADERS = ("Station", "Regions")
STATION_HEADERS = ("Stations", "Upcoming sandbox schedule", "Upcoming production schedule")
STATION_HEADING = re.compile(
    r"Proactive quality update upcoming\s+(?P<app>\d+\.\d+\.\d+)\s+Release-(?P<release>\d+)\s+train schedule",
    re.IGNORECASE,
)
APP_VERSION = re.compile(r"App version:\s*([0-9][0-9.]*)", re.IGNORECASE)
PLATFORM_VERSION = re.compile(r"Platform version:\s*([0-9][0-9.]*)", re.IGNORECASE)
UEP_VERSION = re.compile(
    r"Unified Environment Provisioning Application Version:\s*([0-9][0-9.]*|\S+)",
    re.IGNORECASE,
)
_MARKDOWN_MARKS = re.compile(r"[*_`]+")
_HTML_TAGS = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class _Event:
    kind: str
    level: int = 0
    text: str = ""
    rows: tuple[tuple[str, ...], ...] = ()


@dataclass
class _ScheduleBuilder:
    release_train: str
    application_version: str
    rows: list[ParsedStationRow]
    application_build: str = ""
    platform_build: str = ""
    uep_version: str | None = None


def plain_text(text: str) -> str:
    return " ".join(_HTML_TAGS.sub(" ", _MARKDOWN_MARKS.sub("", text)).split())


def _events(markdown: str) -> list[_Event]:
    parser = MarkdownIt("default")
    tokens = parser.parse(markdown)
    events: list[_Event] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.type == "heading_open":
            inline = tokens[index + 1] if index + 1 < len(tokens) else None
            events.append(
                _Event(
                    kind="heading",
                    level=int(token.tag[1:]),
                    text=plain_text(inline.content if inline is not None else ""),
                )
            )
            index += 3
            continue
        if token.type == "paragraph_open":
            inline = tokens[index + 1] if index + 1 < len(tokens) else None
            events.append(
                _Event(
                    kind="paragraph",
                    text=plain_text(inline.content if inline is not None else ""),
                )
            )
            index += 3
            continue
        if token.type == "table_open":
            rows, index = _read_table(tokens, index)
            events.append(_Event(kind="table", rows=rows))
            continue
        index += 1
    return events


def _read_table(tokens: list[Any], start: int) -> tuple[tuple[tuple[str, ...], ...], int]:
    rows: list[tuple[str, ...]] = []
    current: list[str] = []
    in_cell = False
    index = start + 1
    while index < len(tokens):
        token = tokens[index]
        if token.type == "table_close":
            return tuple(rows), index + 1
        if token.type == "tr_open":
            current = []
        elif token.type in {"th_open", "td_open"}:
            in_cell = True
        elif token.type == "inline" and in_cell:
            current.append(plain_text(token.content))
        elif token.type in {"th_close", "td_close"}:
            in_cell = False
        elif token.type == "tr_close":
            rows.append(tuple(current))
        index += 1
    raise ParserError("Markdown table was not closed")


def _require_headers(
    rows: tuple[tuple[str, ...], ...], expected: tuple[str, ...], label: str
) -> None:
    if not rows:
        raise ParserError(f"{label} table is missing")
    actual = tuple(header.strip() for header in rows[0])
    if actual != expected:
        raise ParserError(f"{label} table headers changed: expected {expected}, found {actual}")


def _split_duration(value: str) -> tuple[str, str]:
    parts = re.split(r"\s+to\s+", value.strip(), maxsplit=1)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        raise ParserError(f"Could not split PQU train duration: {value!r}")
    return parts[0].strip(), parts[1].strip()


def _parse_train_table(rows: tuple[tuple[str, ...], ...]) -> list[ParsedTrainRow]:
    _require_headers(rows, TRAIN_HEADERS, "High-level PQU train")
    parsed: list[ParsedTrainRow] = []
    for row in rows[1:]:
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) != len(TRAIN_HEADERS):
            raise ParserError(f"Unexpected column count in PQU train row: {row!r}")
        parsed.append(
            ParsedTrainRow(
                release_train=row[0].strip(),
                change_cutoff=row[1].strip(),
                train_duration=row[2].strip(),
                status=row[3].strip(),
                application_version=row[4].strip(),
                platform_version=row[5].strip(),
            )
        )
    if not parsed:
        raise ParserError("High-level PQU train table contained no data rows")
    return parsed


def _parse_region_table(rows: tuple[tuple[str, ...], ...]) -> list[ParsedRegionRow]:
    _require_headers(rows, REGION_HEADERS, "Station-to-region")
    parsed: list[ParsedRegionRow] = []
    for row in rows[1:]:
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) != len(REGION_HEADERS):
            raise ParserError(f"Unexpected column count in region row: {row!r}")
        parsed.append(ParsedRegionRow(station=row[0].strip(), regions=row[1].strip()))
    if len(parsed) != 6:
        raise ParserError(
            f"Station-to-region table must contain exactly six rows, found {len(parsed)}"
        )
    station_numbers: list[int] = []
    for region_row in parsed:
        match = re.fullmatch(r"Station\s+([1-6])", region_row.station, re.IGNORECASE)
        if not match:
            raise ParserError(f"Invalid station label in region mapping: {region_row.station!r}")
        if not region_row.regions.strip():
            raise ParserError(f"Station {region_row.station} has no region mapping")
        station_numbers.append(int(match.group(1)))
    if sorted(station_numbers) != list(range(1, 7)):
        raise ParserError("Station-to-region table must cover stations 1 through 6 exactly once")
    return parsed


def _parse_station_table(rows: tuple[tuple[str, ...], ...], label: str) -> list[ParsedStationRow]:
    _require_headers(rows, STATION_HEADERS, label)
    parsed: list[ParsedStationRow] = []
    for row in rows[1:]:
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) != len(STATION_HEADERS):
            raise ParserError(f"Unexpected column count in {label} row: {row!r}")
        parsed.append(
            ParsedStationRow(
                station=row[0].strip(),
                sandbox_schedule=row[1].strip(),
                production_schedule=row[2].strip(),
            )
        )
    if len(parsed) != 6:
        raise ParserError(f"{label} must contain exactly six station rows, found {len(parsed)}")
    return parsed


def parse_source(markdown: str) -> ParsedSource:
    parsed = ParsedSource()
    section: str | None = None
    builder: _ScheduleBuilder | None = None
    seen_train_table = False
    seen_region_table = False

    for event in _events(markdown):
        if event.kind == "heading":
            if event.level == 2:
                lowered = event.text.lower()
                if lowered.startswith("station-to-region mapping"):
                    section = "regions"
                elif lowered.startswith("high-level pqu train schedule"):
                    section = "trains"
                else:
                    section = None
                builder = None
            elif event.level == 3 and "proactive quality update upcoming" in event.text.lower():
                match = STATION_HEADING.search(event.text)
                if not match:
                    raise ParserError(f"Unsupported station schedule heading: {event.text!r}")
                section = "schedules"
                builder = _ScheduleBuilder(
                    release_train=f"{match.group('app')} PQU-{int(match.group('release'))}",
                    application_version=match.group("app"),
                    rows=[],
                )
        elif event.kind == "paragraph" and builder is not None:
            app_match = APP_VERSION.search(event.text)
            platform_match = PLATFORM_VERSION.search(event.text)
            uep_match = UEP_VERSION.search(event.text)
            if app_match:
                builder.application_build = app_match.group(1).strip()
            if platform_match:
                builder.platform_build = platform_match.group(1).strip()
            if uep_match:
                value = uep_match.group(1).strip()
                builder.uep_version = None if value in {"-", ""} else value
        elif event.kind == "table":
            if section == "trains":
                parsed.train_rows.extend(_parse_train_table(event.rows))
                seen_train_table = True
                section = "after-trains"
            elif section == "regions":
                parsed.region_rows.extend(_parse_region_table(event.rows))
                seen_region_table = True
                section = "schedules"
            elif builder is not None:
                builder.rows.extend(
                    _parse_station_table(
                        event.rows,
                        f"Station schedule for {builder.release_train}",
                    )
                )
                if not builder.application_build or not builder.platform_build:
                    raise ParserError(
                        f"Station schedule for {builder.release_train} is missing app or platform version"
                    )
                parsed.station_schedules.append(
                    ParsedStationSchedule(
                        release_train=builder.release_train,
                        application_version=builder.application_version,
                        application_build=builder.application_build,
                        platform_build=builder.platform_build,
                        uep_version=builder.uep_version,
                        rows=tuple(builder.rows),
                    )
                )
                builder = None
            elif section is None:
                continue
            else:
                raise ParserError("Unexpected table outside a supported section")

    if not seen_train_table:
        raise ParserError("High-level PQU train schedule table was not found")
    if not seen_region_table:
        raise ParserError("Station-to-region mapping table was not found")
    if not parsed.station_schedules:
        raise ParserError("No detailed station schedule sections were found")
    return parsed
