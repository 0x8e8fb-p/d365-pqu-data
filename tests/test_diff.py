from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from conftest import SCHEMA_DIR
from d365_pqu.config import Paths
from d365_pqu.diff import compute_changes
from d365_pqu.errors import ValidationError
from d365_pqu.pipeline import verify_artifacts


def _paths(tmp_path: Path) -> Paths:
    return Paths(
        root=tmp_path,
        data_dir=tmp_path / "data",
        excel_dir=tmp_path / "excel",
        schema_dir=SCHEMA_DIR,
        site_dir=tmp_path / "build" / "site",
        tests_dir=tmp_path / "tests",
    )


def test_compute_changes_detects_field_and_added() -> None:
    previous = [
        {
            "pqu_id": "10.0.48-PQU-6",
            "application_version": "10.0.48",
            "pqu_train": "PQU-6",
            "release_number": 6,
            "change_cutoff_date": "2026-09-16",
            "train_start_date": "2026-09-16",
            "train_end_date": "2026-10-10",
            "status": "In-Progress",
            "application_build": "10.0.2645.136",
            "platform_build": "7.0.7996.119",
            "uep_version": "10.0.48.7",
            "station_schedule_available": True,
        }
    ]
    current = [
        {**previous[0], "platform_build": "7.0.7996.130"},
        {
            "pqu_id": "10.0.48-PQU-7",
            "application_version": "10.0.48",
            "pqu_train": "PQU-7",
            "release_number": 7,
            "change_cutoff_date": "2026-09-30",
            "train_start_date": "2026-09-30",
            "train_end_date": "2026-10-24",
            "status": "Not Started",
            "application_build": "10.0.2645.140",
            "platform_build": "7.0.7996.135",
            "uep_version": None,
            "station_schedule_available": False,
        },
    ]
    changes = compute_changes(
        previous,
        current,
        source_commit="c" * 40,
        changed_at=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
    )
    types = {(change["change_type"], change["field"]) for change in changes}
    assert ("modified", "platform_build") in types
    assert ("added", None) in types
    assert all(len(change["change_id"]) == 20 for change in changes)


def test_compute_changes_without_previous_returns_empty() -> None:
    changes = compute_changes(None, [], source_commit="c" * 40, changed_at=datetime.now(UTC))
    assert changes == []


def test_verify_artifacts_requires_committed_output(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    with pytest.raises(ValidationError):
        verify_artifacts(paths)
