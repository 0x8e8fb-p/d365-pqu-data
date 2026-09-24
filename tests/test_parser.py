from __future__ import annotations

from pathlib import Path

import pytest

from conftest import FIXTURES, SCHEMA_DIR
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
