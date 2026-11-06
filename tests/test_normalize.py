from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from conftest import FIXTURES
from d365_pqu.errors import ParserError, ValidationError
from d365_pqu.models import SourceDocument
from d365_pqu.normalize import (
    canonical_status,
    normalize_source,
    parse_date_range,
    parse_station_date_range,
)
from d365_pqu.parser import parse_source
from d365_pqu.source import parse_markdown_date
from d365_pqu.validation import validate_quality, validate_records


def _source(name: str, commit: str = "a" * 40) -> SourceDocument:
    markdown = (FIXTURES / name).read_text(encoding="utf-8")
    return SourceDocument(
        markdown=markdown,
        source_commit=commit,
        article_url="https://learn.microsoft.com/example",
        raw_url=f"https://raw.githubusercontent.com/example/{commit}/schedule.md",
        markdown_date=parse_markdown_date(markdown),
        retrieved_at=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
        sha256="b" * 64,
    )


def test_normalize_builds_records_stations_and_regions() -> None:
    source = _source("source-minimal.md")
    dataset = normalize_source(parse_source(source.markdown), source)
    assert len(dataset.records) == 4
    by_id = {record["pqu_id"]: record for record in dataset.records}
    assert by_id["10.0.48-PQU-6"]["status"] == "In-Progress"
    assert by_id["10.0.48-PQU-6"]["uep_version"] == "10.0.48.7"
    assert by_id["10.0.48-PQU-6"]["station_schedule_available"] is True
    assert by_id["10.0.48-PQU-7"]["application_build"] is None
    assert by_id["10.0.47-PQU-2"]["status"] == "Canceled"
    assert len(dataset.stations) == 12
    station_two = next(
        row for row in dataset.stations if row["pqu_id"] == "10.0.48-PQU-6" and row["station"] == 2
    )
    assert station_two["sandbox_start_date"] == "2026-09-21"
    assert station_two["production_start_date"] == "2026-09-26"
    assert len(dataset.regions) == 9
    assert any(row["region"] == "India Central" for row in dataset.regions)
    validate_quality(dataset)
    validate_records(dataset)


def test_normalize_detects_year_mismatch_warning() -> None:
    markdown = (
        (FIXTURES / "source-minimal.md")
        .read_text(encoding="utf-8")
        .replace(
            "September 2, 2026 to September 26, 2026",
            "September 2, 2025 to September 26, 2026",
        )
    )
    source = _source("source-minimal.md")
    dataset = normalize_source(parse_source(markdown), source)
    codes = {item["code"] for item in dataset.quality}
    assert "cutoff-start-year-mismatch" in codes
    warning = next(item for item in dataset.quality if item["code"] == "cutoff-start-year-mismatch")
    assert warning["pqu_id"] == "10.0.48-PQU-5"


def test_normalize_flags_unmatched_station_schedule() -> None:
    markdown = (
        (FIXTURES / "source-minimal.md")
        .read_text(encoding="utf-8")
        .replace(
            "**App version: 10.0.2645.136**",
            "**App version: 10.0.9999.999**",
        )
    )
    source = _source("source-minimal.md")
    dataset = normalize_source(parse_source(markdown), source)
    errors = [item for item in dataset.quality if item["severity"] == "error"]
    assert any(item["code"] == "station-schedule-match" for item in errors)
    with pytest.raises(ValidationError):
        validate_quality(dataset)


def test_station_heading_and_build_must_agree() -> None:
    markdown = (
        (FIXTURES / "source-minimal.md")
        .read_text(encoding="utf-8")
        .replace(
            "upcoming 10.0.48 Release-6 train schedule",
            "upcoming 10.0.48 Release-7 train schedule",
            1,
        )
    )
    dataset = normalize_source(parse_source(markdown), _source("source-minimal.md"))
    errors = [item for item in dataset.quality if item["severity"] == "error"]
    assert any(item["code"] == "station-schedule-match" for item in errors)


def test_station_date_cells_accept_only_the_canceled_footnote() -> None:
    assert parse_station_date_range("Canceled*") == (None, None)
    assert parse_station_date_range("Canceled†") == (None, None)
    assert parse_station_date_range("N/A") == (None, None)
    assert parse_station_date_range("December 28 to January 3, 2027") == (
        "2026-12-28",
        "2027-01-03",
    )
    # Train durations and every other date range keep the original strict parsing.
    with pytest.raises(ParserError):
        parse_date_range("Canceled*")


def test_canceled_footnote_station_rows_have_no_dates() -> None:
    markdown = (
        (FIXTURES / "source-minimal.md")
        .read_text(encoding="utf-8")
        .replace(
            "| Station 2 | September 21 to September 24, 2026 | September 26 to September 27, 2026 |",
            "| Station 2 | Canceled* | Canceled* |",
        )
    )
    dataset = normalize_source(parse_source(markdown), _source("source-minimal.md"))
    assert not any(item["code"] == "invalid-station-dates" for item in dataset.quality)
    canceled = [
        row for row in dataset.stations if row["pqu_id"] == "10.0.48-PQU-6" and row["station"] == 2
    ]
    assert len(canceled) == 1
    assert canceled[0]["sandbox_start_date"] is None
    assert canceled[0]["sandbox_end_date"] is None
    assert canceled[0]["production_start_date"] is None
    assert canceled[0]["production_end_date"] is None
    validate_quality(dataset)


def test_reciprocal_station_build_swap_is_a_warning() -> None:
    # Microsoft exchanged the build labels of two station sections on 2026-11-04 while the
    # high-level table stayed canonical. The headings and rollout dates are still correct.
    text = (FIXTURES / "source-minimal.md").read_text(encoding="utf-8")
    text = (
        text.replace("**App version: 10.0.2645.136**", "**App version: 10.0.9999.001**")
        .replace("**Platform version: 7.0.7996.119**", "**Platform version: 7.0.9999.001**")
        .replace("**App version: 10.0.2645.124**", "**App version: 10.0.2645.136**")
        .replace("**Platform version: 7.0.7996.111**", "**Platform version: 7.0.7996.119**")
        .replace("**App version: 10.0.9999.001**", "**App version: 10.0.2645.124**")
        .replace("**Platform version: 7.0.9999.001**", "**Platform version: 7.0.7996.111**")
    )
    dataset = normalize_source(parse_source(text), _source("source-minimal.md"))
    mismatches = [
        item for item in dataset.quality if item["code"] == "station-schedule-build-mismatch"
    ]
    assert len(mismatches) == 2
    assert all(item["severity"] == "warning" for item in mismatches)
    assert not any(item["severity"] == "error" for item in dataset.quality)
    assert len(dataset.stations) == 12  # neither schedule was discarded
    validate_quality(dataset)


def test_one_sided_station_build_mismatch_stays_fatal() -> None:
    markdown = (
        (FIXTURES / "source-minimal.md")
        .read_text(encoding="utf-8")
        .replace("**App version: 10.0.2645.136**", "**App version: 10.0.2645.124**")
        .replace("**Platform version: 7.0.7996.119**", "**Platform version: 7.0.7996.111**")
    )
    dataset = normalize_source(parse_source(markdown), _source("source-minimal.md"))
    errors = [item for item in dataset.quality if item["severity"] == "error"]
    assert any(item["code"] == "station-schedule-match" for item in errors)
    with pytest.raises(ValidationError):
        validate_quality(dataset)


def test_invalid_calendar_date_is_a_parser_error() -> None:
    with pytest.raises(ParserError, match="Invalid calendar date"):
        parse_date_range("February 30, 2026 to March 1, 2026")


def test_parse_date_range_handles_rollover_and_na() -> None:
    assert parse_date_range("December 28 to January 3, 2027") == ("2026-12-28", "2027-01-03")
    assert parse_date_range("N/A") == (None, None)
    with pytest.raises(ParserError):
        parse_date_range("January 5")


def test_canonical_status_aliases() -> None:
    assert canonical_status("in progress") == "In-Progress"
    assert canonical_status("cancelled") == "Canceled"
    assert canonical_status("Not Started") == "Not Started"


def test_record_first_seen_is_preserved(tmp_path: Path) -> None:
    source = _source("source-minimal.md")
    first = normalize_source(
        parse_source(source.markdown), source, observed_at=datetime(2026, 9, 24, tzinfo=UTC)
    )
    previous = {"records": [dict(record) for record in first.records]}
    second = normalize_source(
        parse_source(source.markdown),
        source,
        previous=previous,
        observed_at=datetime(2026, 9, 25, tzinfo=UTC),
    )
    first_seen = {record["pqu_id"]: record["first_seen_at"] for record in first.records}
    for record in second.records:
        assert record["first_seen_at"] == first_seen[record["pqu_id"]]
    assert tmp_path.exists()
