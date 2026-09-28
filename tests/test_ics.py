from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from conftest import E2E_SYNC_AT, LIVE_FIXTURES, build_fixture_site
from d365_pqu.config import PAGES_BASE_URL
from d365_pqu.ics import (
    LINE_LIMIT,
    MILESTONES_FILE,
    calendar_files,
    duration,
    escape_text,
    fold,
    station_file,
    unfold,
)

DOMAIN = "0x8e8fb-p.github.io"


@pytest.fixture(scope="module")
def live_site(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_fixture_site(tmp_path_factory.mktemp("ics"), [(LIVE_FIXTURES, E2E_SYNC_AT)])


def _json(site: Path, name: str) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((site / "api" / name).read_text(encoding="utf-8"))
    return document


def _events(document: bytes) -> dict[str, dict[str, str]]:
    """UID -> {property name (with parameters): value} for every VEVENT."""
    events: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for line in unfold(document):
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT":
            assert current is not None
            events[current["UID"]] = current
            current = None
        elif current is not None:
            name, _, value = line.partition(":")
            current[name] = value
    return events


def _header(document: bytes) -> dict[str, str]:
    header: dict[str, str] = {}
    for line in unfold(document):
        if line == "BEGIN:VEVENT":
            break
        name, _, value = line.partition(":")
        header[name] = value
    return header


def _assert_well_formed(document: bytes) -> None:
    assert document.endswith(b"\r\n")
    assert b"\n" not in document.replace(b"\r\n", b"")
    for line in document.split(b"\r\n"):
        assert len(line) <= LINE_LIMIT
        line.decode("utf-8")  # A folded line never splits a character.
    lines = unfold(document)
    assert lines[0] == "BEGIN:VCALENDAR"
    assert lines[-1] == "END:VCALENDAR"
    assert lines.count("BEGIN:VEVENT") == lines.count("END:VEVENT")


def test_folding_keeps_characters_whole() -> None:
    line = "DESCRIPTION:" + "10.0.48 PQU-6 \u00b7 Station 4 \u2013 Z\u00fcrich " * 12
    folded = fold(line)
    parts = folded.split(b"\r\n")
    assert len(parts) > 1
    assert all(len(part) <= LINE_LIMIT for part in parts)
    assert all(part.startswith(b" ") for part in parts[1:])
    for part in parts:
        part.decode("utf-8")
    assert unfold(folded + b"\r\n") == [line]
    assert fold("SHORT:value") == b"SHORT:value"


def test_text_values_are_escaped() -> None:
    assert escape_text("a,b;c\\d\ne\r\nf\rg\x07h\ti") == "a\\,b\\;c\\\\d\\ne\\nf\\ng" + "h\ti"


def test_durations() -> None:
    assert [duration(value) for value in (30, 60, 90, 1440, 1500)] == [
        "PT30M",
        "PT1H",
        "PT1H30M",
        "P1D",
        "P1DT1H",
    ]
    with pytest.raises(ValueError):
        duration(0)


def test_station_calendar(live_site: Path) -> None:
    document = (live_site / "calendar" / station_file(4)).read_bytes()
    _assert_well_formed(document)
    header = _header(document)
    assert header["VERSION"] == "2.0"
    assert header["PRODID"] == "-//0x8e8fb-p//D365 PQU dataset//EN"
    assert header["METHOD"] == "PUBLISH"
    assert header["NAME"] == header["X-WR-CALNAME"] == "PQU Station 4 windows"
    assert header["REFRESH-INTERVAL;VALUE=DURATION"] == "PT1H"
    assert header["X-PUBLISHED-TTL"] == "PT1H"
    assert header["SOURCE;VALUE=URI"] == f"{PAGES_BASE_URL}/calendar/station-4.ics"
    assert "Regions on Station 4: Brazil South\\, East Asia\\, East US" in header["DESCRIPTION"]
    assert "CC BY 4.0" in header["DESCRIPTION"]

    events = _events(document)
    assert len(events) == 10
    assert all(key.endswith(f"@{DOMAIN}") for key in events)
    production = events[f"production_window:10.0.48-PQU-6:station-4@{DOMAIN}"]
    assert production["DTSTAMP"] == "20260928T030000Z"
    assert production["DTSTART;VALUE=DATE"] == "20261003"
    # All-day events end on the day after the last day.
    assert production["DTEND;VALUE=DATE"] == "20261005"
    assert production["SUMMARY"] == "10.0.48 PQU-6 \u00b7 Station 4 production"
    assert production["URL"] == f"{PAGES_BASE_URL}/#/train/10.0.48-PQU-6"
    assert production["TRANSP"] == "TRANSPARENT"
    assert production["CATEGORIES"] == "Production window"
    assert production["DESCRIPTION"].split("\\n") == [
        "Production window for Station 4\\, 10.0.48 PQU-6.",
        "Microsoft status of the train: In-Progress.",
        "Dates from Microsoft's detailed station schedule\\; Microsoft can change them.",
        f"Details: {PAGES_BASE_URL}/#/train/10.0.48-PQU-6",
        "Source: https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/"
        "get-started/quality-updates-schedule#schedule",
    ]
    sandbox = events[f"sandbox_window:10.0.48-PQU-6:station-4@{DOMAIN}"]
    assert (sandbox["DTSTART;VALUE=DATE"], sandbox["DTEND;VALUE=DATE"]) == ("20260928", "20261002")

    station_1 = _events((live_site / "calendar" / station_file(1)).read_bytes())
    assert len(station_1) == 5
    assert all(uid.startswith("sandbox_window:") for uid in station_1)
    assert (
        "Station 1: Only for opted-in environments."
        in _header((live_site / "calendar" / station_file(1)).read_bytes())["DESCRIPTION"]
    )


def test_milestones_calendar(live_site: Path) -> None:
    document = (live_site / "calendar" / MILESTONES_FILE).read_bytes()
    _assert_well_formed(document)
    events = _events(document)
    assert len(events) == 101
    kinds = {uid.split(":")[0] for uid in events}
    assert kinds == {
        "change_cutoff",
        "preview",
        "preview_latest_update",
        "general_availability",
        "autoupdate_first",
        "autoupdate_second",
        "end_of_service",
    }

    cutoff = events[f"change_cutoff:10.0.48-PQU-7@{DOMAIN}"]
    assert (cutoff["DTSTART;VALUE=DATE"], cutoff["DTEND;VALUE=DATE"]) == ("20260930", "20261001")
    assert cutoff["SUMMARY"] == "10.0.48 PQU-7 change cutoff"
    assert "The train runs 30 Sep \u2013 24 Oct 2026." in cutoff["DESCRIPTION"]
    assert "Microsoft status: Not Started." in cutoff["DESCRIPTION"]
    assert "STATUS" not in cutoff

    canceled = events[f"change_cutoff:10.0.47-PQU-2@{DOMAIN}"]
    assert canceled["STATUS"] == "CANCELLED"
    assert canceled["SUMMARY"] == "10.0.47 PQU-2 change cutoff (Canceled)"

    flagged = events[f"change_cutoff:10.0.46-PQU-1@{DOMAIN}"]
    assert flagged["SUMMARY"] == "10.0.46 PQU-1 change cutoff (source warning)"
    lines = flagged["DESCRIPTION"].split("\\n")
    assert lines[0] == (
        "Source warning: Change cutoff 2026-02-04 and train start 2025-02-09 are in different "
        "years."
    )
    assert "Microsoft lists the train as running 9 Feb 2025 \u2013 14 Mar 2026." in lines

    ga = events[f"general_availability:10.0.49@{DOMAIN}"]
    assert ga["DTSTART;VALUE=DATE"] == "20260911"
    assert ga["SUMMARY"] == "10.0.49 general availability"
    assert ga["URL"] == f"{PAGES_BASE_URL}/#/versions?version=10.0.49"
    assert ga["CATEGORIES"] == "Service update"


def test_calendars_are_deterministic(live_site: Path) -> None:
    metadata = _json(live_site, "metadata.json")
    inputs = {
        "regions": _json(live_site, "regions.json")["records"],
        "quality": _json(live_site, "quality-report.json")["records"],
        "metadata": metadata,
    }
    events = _json(live_site, "events.json")["records"]
    first = calendar_files(events, **inputs)
    second = calendar_files(list(events), **inputs)
    assert {name: entry["content"] for name, entry in first.items()} == {
        name: entry["content"] for name, entry in second.items()
    }
    for name, entry in first.items():
        assert (live_site / "calendar" / name).read_bytes() == entry["content"]
    assert metadata["generated_at"] == "2026-09-28T03:00:00Z"


def test_an_event_keeps_its_uid_when_microsoft_moves_it() -> None:
    event = {
        "id": "production_window:10.0.48-PQU-6:station-4",
        "kind": "production_window",
        "title": "10.0.48 PQU-6 \u00b7 Station 4 production",
        "start_date": "2026-10-03",
        "end_date": "2026-10-04",
        "pqu_id": "10.0.48-PQU-6",
        "station": 4,
        "status": "In-Progress",
        "url": None,
        "warnings": [],
    }
    moved = {**event, "start_date": "2026-10-10", "end_date": "2026-10-11"}
    metadata = {"generated_at": "2026-09-28T03:00:00Z"}
    before = _events(
        calendar_files([event], regions=[], quality=[], metadata=metadata)[station_file(4)][
            "content"
        ]
    )
    after = _events(
        calendar_files([moved], regions=[], quality=[], metadata=metadata)[station_file(4)][
            "content"
        ]
    )
    assert list(before) == list(after)
    uid = next(iter(after))
    assert after[uid]["DTSTART;VALUE=DATE"] == "20261010"
    assert before[uid]["DTSTART;VALUE=DATE"] == "20261003"


def test_calendars_without_events_are_valid() -> None:
    files = calendar_files(
        [], regions=[], quality=[], metadata={"generated_at": "2026-09-28T03:00:00Z"}
    )
    assert sorted(files) == [MILESTONES_FILE, *(station_file(n) for n in range(1, 7))]
    for entry in files.values():
        _assert_well_formed(entry["content"])
        assert entry["events"] == 0
        assert _events(entry["content"]) == {}
    with pytest.raises(ValueError, match="generated_at"):
        calendar_files([], regions=[], quality=[], metadata={})


def test_the_api_index_lists_the_calendars(live_site: Path) -> None:
    index = _json(live_site, "index.json")
    calendars = {entry["path"]: entry for entry in index["calendars"]}
    assert list(calendars) == [
        *(f"./../calendar/station-{n}.ics" for n in range(1, 7)),
        "./../calendar/milestones.ics",
    ]
    station = calendars["./../calendar/station-4.ics"]
    assert station["name"] == "PQU Station 4 windows"
    assert station["url"] == f"{PAGES_BASE_URL}/calendar/station-4.ics"
    assert station["events"] == 10
    assert calendars["./../calendar/milestones.ics"]["events"] == 101
    for entry in calendars.values():
        assert (live_site / "api" / entry["path"]).resolve().is_file()
