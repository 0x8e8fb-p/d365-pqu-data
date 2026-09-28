from __future__ import annotations

import pytest

from conftest import LIVE_FIXTURES
from d365_pqu.errors import ParserError
from d365_pqu.lifecycle import parse_service_updates

LIVE = (LIVE_FIXTURES / "public-preview-releases.md").read_text(encoding="utf-8")
HEADER = (
    "| Release version | Preview availability | Preview latest possible update | "
    "General availability (self-update) | First autoupdate schedule for production start date | "
    "Second autoupdate schedule for production start date | End of service |\n"
    "|---|---|---|---|---|---|---|\n"
)


def _table(*rows: str, header: str = HEADER) -> str:
    return "# Service update availability\n\n" + header + "\n".join(rows) + "\n"


def test_live_article_yields_every_release_in_version_order() -> None:
    records, quality = parse_service_updates(LIVE)
    assert quality == []
    assert [record["version"] for record in records] == [
        "10.0.45",
        "10.0.46",
        "10.0.47",
        "10.0.48",
        "10.0.49",
        "10.0.50",
        "10.0.51",
    ]
    by_version = {record["version"]: record for record in records}
    assert by_version["10.0.46"]["end_of_service_date"] == "2026-08-21"
    assert by_version["10.0.49"]["general_availability_date"] == "2026-09-11"
    assert by_version["10.0.49"] == {
        "version": "10.0.49",
        "release_label": "CY26Q4",
        "is_major": True,
        "preview_date": "2026-07-27",
        "preview_latest_update_date": "2026-08-17",
        "general_availability_date": "2026-09-11",
        "first_autoupdate_date": "2026-10-02",
        "second_autoupdate_date": "2026-11-01",
        "end_of_service_date": "2027-05-21",
    }


def test_major_release_marker_is_read_escaped_or_not() -> None:
    records, _ = parse_service_updates(LIVE)
    majors = {record["version"]: record["is_major"] for record in records}
    # 10.0.51 uses a bare asterisk in the source; the others use an escaped one.
    assert majors == {
        "10.0.45": True,
        "10.0.46": False,
        "10.0.47": True,
        "10.0.48": False,
        "10.0.49": True,
        "10.0.50": False,
        "10.0.51": True,
    }


def test_headers_are_matched_ignoring_case_and_spacing() -> None:
    header = HEADER.replace("Release version", "  release  VERSION ").replace(
        "End of service", "End of Service"
    )
    markdown = _table(
        "| CY26Q3: 10.0.48 | April 24, 2026 | May 11, 2026 | June 5, 2026 | July 3, 2026 | "
        "July 31, 2026 | February 16, 2027 |",
        header=header,
    )
    records, _ = parse_service_updates(markdown)
    assert [record["version"] for record in records] == ["10.0.48"]


def test_rows_without_a_label_blank_cells_and_bad_rows() -> None:
    markdown = _table(
        "| 10.0.52 | TBD | - | May 1, 2027 | | | |",
        "| Next release | May 1, 2027 | | | | | |",
        "| CY27Q3: 10.0.53 | Someday 2027 | | | | | |",
    )
    records, quality = parse_service_updates(markdown)
    by_version = {record["version"]: record for record in records}
    assert by_version["10.0.52"]["release_label"] is None
    assert by_version["10.0.52"]["preview_date"] is None
    assert by_version["10.0.52"]["general_availability_date"] == "2027-05-01"
    assert by_version["10.0.53"]["preview_date"] is None
    codes = [(item["code"], item["field"]) for item in quality]
    assert ("service-update-row-invalid", None) in codes
    assert ("service-update-date-invalid", "10.0.53#preview_date") in codes
    assert all(item["severity"] == "warning" for item in quality)


def test_out_of_order_and_duplicate_rows_are_warnings() -> None:
    markdown = _table(
        "| CY26Q3: 10.0.48 | April 24, 2026 | May 11, 2026 | March 5, 2026 | July 3, 2026 | "
        "July 31, 2026 | February 16, 2027 |",
        "| CY26Q3: 10.0.48 | April 24, 2026 | | | | | |",
    )
    records, quality = parse_service_updates(markdown)
    assert len(records) == 1
    codes = [(item["code"], item["field"]) for item in quality]
    assert codes == [
        ("service-update-dates-out-of-order", "10.0.48#general_availability_date"),
        ("service-update-duplicate", "10.0.48"),
    ]


def test_missing_or_changed_table_is_a_parser_error() -> None:
    with pytest.raises(ParserError, match="not found or its headers changed"):
        parse_service_updates(LIVE.replace("| Release version |", "| Release |"))
    with pytest.raises(ParserError, match="no readable rows"):
        parse_service_updates(_table("| Coming soon | | | | | | |"))
