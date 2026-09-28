from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import FIXTURES, LIVE_FIXTURES, SCHEMA_DIR
from d365_pqu.config import Paths
from d365_pqu.errors import ParserError
from d365_pqu.parser import parse_source


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_source_reads_all_sections() -> None:
    parsed = parse_source(_fixture("source-minimal.md"))
    assert len(parsed.train_rows) == 4
    assert len(parsed.region_rows) == 6
    assert len(parsed.station_schedules) == 2
    schedule = parsed.station_schedules[0]
    assert schedule.release_train == "10.0.48 PQU-6"
    assert schedule.application_build == "10.0.2645.136"
    assert schedule.platform_build == "7.0.7996.119"
    assert schedule.uep_version == "10.0.48.7"
    assert len(schedule.rows) == 6
    assert schedule.rows[0].sandbox_schedule == "September 16 to September 19, 2026"


def test_parse_source_normalizes_headings_with_html_anchor() -> None:
    parsed = parse_source(_fixture("source-minimal.md"))
    assert parsed.station_schedules[0].release_train == "10.0.48 PQU-6"


def test_parse_source_rejects_changed_headers() -> None:
    with pytest.raises(ParserError, match="headers changed"):
        parse_source(_fixture("source-broken.md"))


def test_parse_source_requires_station_schedule() -> None:
    markdown = _fixture("source-minimal.md").split('### <a name="schedule"></a>')[0]
    with pytest.raises(ParserError, match="No detailed station schedule"):
        parse_source(markdown)


def test_paths_helpers(tmp_path: Path) -> None:
    paths = Paths.from_root(tmp_path)
    assert paths.data_dir == tmp_path.resolve() / "data"
    assert paths.workbook_path == tmp_path.resolve() / "excel" / "D365-PQU-Tracker.xlsx"
    assert paths.schema_dir == tmp_path.resolve() / "schema"
    assert SCHEMA_DIR.joinpath("pqu.schema.json").exists()


def _live_dataset(markdown: str | None = None):
    import hashlib
    from datetime import UTC, datetime

    from d365_pqu.models import SourceDocument
    from d365_pqu.normalize import normalize_source
    from d365_pqu.source import parse_markdown_date

    text = markdown or (LIVE_FIXTURES / "quality-updates-schedule.md").read_text(encoding="utf-8")
    document = SourceDocument(
        markdown=text,
        source_commit="d" * 40,
        article_url="https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/quality-updates-schedule",
        raw_url="https://raw.githubusercontent.com/example/schedule.md",
        markdown_date=parse_markdown_date(text),
        retrieved_at=datetime(2026, 9, 28, tzinfo=UTC),
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )
    return normalize_source(
        parse_source(text), document, observed_at=datetime(2026, 9, 28, tzinfo=UTC)
    )


def _subset(rows: list[dict], expected: list[dict]) -> list[dict]:
    keys = set().union(*(row.keys() for row in expected)) if expected else set()
    return [{key: row.get(key) for key in keys if key in row} for row in rows]


def test_live_snapshot_matches_pre_v2_parser_characterization() -> None:
    dataset = _live_dataset()
    for name, rows in (
        ("records", dataset.records),
        ("stations", dataset.stations),
        ("regions", dataset.regions),
    ):
        expected = json.loads((LIVE_FIXTURES / f"expected-{name}.json").read_text(encoding="utf-8"))
        assert _subset([dict(row) for row in rows], expected) == expected, name
    expected_quality = json.loads(
        (LIVE_FIXTURES / "expected-quality.json").read_text(encoding="utf-8")
    )
    observed = [dict(item) for item in dataset.quality if item["severity"] != "info"]
    assert observed == expected_quality


def test_new_marker_flags_exactly_the_new_station_schedules() -> None:
    dataset = _live_dataset()
    flagged = sorted(r["pqu_id"] for r in dataset.records if r["station_schedule_new"])
    assert flagged == ["10.0.46-PQU-8", "10.0.47-PQU-13", "10.0.48-PQU-6"]
    assert all(
        r["station_schedule_available"] for r in dataset.records if r["station_schedule_new"]
    )


@pytest.mark.parametrize("cell", ["Canceled*", "Canceled\\*"])
def test_status_footnote_marker_is_resolved_from_the_article_note(cell: str) -> None:
    markdown = (LIVE_FIXTURES / "quality-updates-schedule.md").read_text(encoding="utf-8")
    edited = markdown.replace(
        "| 10.0.47 PQU-2 | April 22, 2026 | April 22, 2026 to May 16, 2026| Canceled |",
        f"| 10.0.47 PQU-2 | April 22, 2026 | April 22, 2026 to May 16, 2026| {cell} |",
    )
    assert edited != markdown
    dataset = _live_dataset(edited)
    record = next(r for r in dataset.records if r["pqu_id"] == "10.0.47-PQU-2")
    assert record["status"] == "Canceled"
    assert record["status_note"] == (
        "PQU will occur only on Station-1. Releases for other stations have been canceled due "
        "to the holiday deployment freeze, and the build will be available for manual uptake."
    )
    assert not [item for item in dataset.quality if item["code"] == "status-footnote-undefined"]


def test_undefined_status_footnote_is_a_warning_not_a_failure() -> None:
    markdown = (LIVE_FIXTURES / "quality-updates-schedule.md").read_text(encoding="utf-8")
    edited = markdown.replace(
        "| 10.0.48 PQU-4 | August 19, 2026 | August 19, 2026 to September 12, 2026| Completed |",
        "| 10.0.48 PQU-4 | August 19, 2026 | August 19, 2026 to September 12, 2026| Completed† |",
    )
    dataset = _live_dataset(edited)
    record = next(r for r in dataset.records if r["pqu_id"] == "10.0.48-PQU-4")
    assert record["status"] == "Completed"
    assert record["status_note"] is None
    warnings = [item for item in dataset.quality if item["code"] == "status-footnote-undefined"]
    assert [(item["severity"], item["pqu_id"]) for item in warnings] == [
        ("warning", "10.0.48-PQU-4")
    ]


def test_unmarked_statuses_have_no_note() -> None:
    dataset = _live_dataset()
    assert all(record["status_note"] is None for record in dataset.records)
    assert dataset.articles[0]["key"] == "schedule"
    assert dataset.articles[0]["commit"] == "d" * 40
