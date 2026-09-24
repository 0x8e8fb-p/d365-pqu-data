from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from conftest import FIXTURES, SCHEMA_DIR
from d365_pqu.config import Paths
from d365_pqu.errors import ParserError, ValidationError
from d365_pqu.models import SourceDocument
from d365_pqu.pipeline import load_json, run_sync
from d365_pqu.source import parse_markdown_date


def _paths(tmp_path: Path) -> Paths:
    return Paths(
        root=tmp_path,
        data_dir=tmp_path / "data",
        excel_dir=tmp_path / "excel",
        schema_dir=SCHEMA_DIR,
        site_dir=tmp_path / "build" / "site",
        tests_dir=tmp_path / "tests",
    )


def _commit(hash_hex: str) -> str:
    return hash_hex.rjust(40, "0")[:40]


def _document(name: str, commit: str) -> SourceDocument:
    markdown = (FIXTURES / name).read_text(encoding="utf-8")
    return SourceDocument(
        markdown=markdown,
        source_commit=commit,
        article_url="https://learn.microsoft.com/example",
        raw_url=f"https://raw.githubusercontent.com/example/{commit}/schedule.md",
        markdown_date=parse_markdown_date(markdown),
        retrieved_at=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
        sha256=hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
    )


def test_sync_writes_complete_valid_dataset(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    result = run_sync(
        paths,
        source=_document("source-minimal.md", "a" * 40),
        now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
    )
    assert result.changed is True
    assert result.record_count == 4
    assert result.current_count == 2
    assert result.upcoming_count == 1
    assert (paths.data_dir / "pqu.json").exists()
    assert (paths.data_dir / "pqu.csv").exists()
    assert paths.workbook_path.exists()
    history = list((paths.data_dir / "history").rglob("*.json"))
    assert len(history) == 1
    metadata = load_json(paths.data_dir / "metadata.json")
    assert metadata is not None
    assert metadata["latest_pqu_id"] == "10.0.48-PQU-6"
    health = load_json(paths.data_dir / "health.json")
    assert health is not None
    assert health["status"] == "healthy"
    assert health["warning_count"] == 0


def test_sync_no_change_is_idempotent(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    document = _document("source-minimal.md", "a" * 40)
    run_sync(paths, source=document, now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC))
    pqu_before = (paths.data_dir / "pqu.json").read_bytes()
    digest_before = hashlib.sha256(pqu_before).hexdigest()
    result = run_sync(
        paths,
        source=document,
        now=datetime(2026, 9, 24, 12, 5, tzinfo=UTC),
    )
    assert result.changed is False
    assert result.status == "unchanged"
    assert hashlib.sha256((paths.data_dir / "pqu.json").read_bytes()).hexdigest() == digest_before


def test_sync_records_field_changes(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    run_sync(
        paths,
        source=_document("source-minimal.md", "a" * 40),
        now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
    )
    pqu_before = load_json(paths.data_dir / "pqu.json")
    assert pqu_before is not None
    first_seen = {record["pqu_id"]: record["first_seen_at"] for record in pqu_before["records"]}
    run_sync(
        paths,
        source=_document("source-updated.md", "d" * 40),
        now=datetime(2026, 9, 25, 12, 0, tzinfo=UTC),
    )
    changes = load_json(paths.data_dir / "pqu-changes.json")
    assert changes is not None
    pairs = {(change["pqu_id"], change["field"]) for change in changes["records"]}
    assert ("10.0.48-PQU-6", "platform_build") in pairs
    assert ("10.0.48-PQU-6", "status") not in pairs
    assert ("10.0.48-PQU-5", "status") in pairs
    assert ("10.0.48-PQU-7", "application_build") in pairs
    pqu_after = load_json(paths.data_dir / "pqu.json")
    assert pqu_after is not None
    for record in pqu_after["records"]:
        if record["pqu_id"] in first_seen:
            assert record["first_seen_at"] == first_seen[record["pqu_id"]]
    new_record = next(r for r in pqu_after["records"] if r["pqu_id"] == "10.0.48-PQU-7")
    assert new_record["application_build"] == "10.0.2645.140"
    assert new_record["first_seen_at"] == first_seen["10.0.48-PQU-7"]
    assert new_record["last_changed_at"].startswith("2026-09-25")


def test_sync_preserves_data_on_parser_failure(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    run_sync(
        paths,
        source=_document("source-minimal.md", "a" * 40),
        now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
    )
    before = (paths.data_dir / "pqu.json").read_bytes()
    with pytest.raises(ParserError):
        run_sync(
            paths,
            source=_document("source-broken.md", "e" * 40),
            now=datetime(2026, 9, 25, 12, 0, tzinfo=UTC),
        )
    assert (paths.data_dir / "pqu.json").read_bytes() == before


def test_sync_heartbeat_updates_only_health(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    document = _document("source-minimal.md", "a" * 40)
    run_sync(paths, source=document, now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC))
    pqu_digest = hashlib.sha256((paths.data_dir / "pqu.json").read_bytes()).hexdigest()
    result = run_sync(
        paths,
        source=document,
        now=datetime(2026, 10, 25, 12, 0, tzinfo=UTC),
    )
    assert result.changed is True
    assert result.status == "heartbeat"
    assert hashlib.sha256((paths.data_dir / "pqu.json").read_bytes()).hexdigest() == pqu_digest
    health = load_json(paths.data_dir / "health.json")
    assert health is not None
    assert health["checked_at"].startswith("2026-10-25")


def test_same_markdown_with_new_source_commit_refreshes_provenance(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    original = _document("source-minimal.md", "a" * 40)
    run_sync(paths, source=original, now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC))
    refreshed = _document("source-minimal.md", "b" * 40)
    result = run_sync(
        paths,
        source=refreshed,
        now=datetime(2026, 9, 24, 12, 5, tzinfo=UTC),
    )
    assert result.changed is True
    pqu = load_json(paths.data_dir / "pqu.json")
    assert pqu is not None
    assert pqu["source"]["commit"] == "b" * 40
    assert all(record["source"]["commit"] == "b" * 40 for record in pqu["records"])


def test_failed_workbook_generation_preserves_previous_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = _paths(tmp_path)
    run_sync(
        paths,
        source=_document("source-minimal.md", "a" * 40),
        now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
    )
    before = (paths.data_dir / "pqu.json").read_bytes()
    workbook_before = paths.workbook_path.read_bytes()

    def fail_workbook(*args, **kwargs):
        raise RuntimeError("simulated workbook failure")

    monkeypatch.setattr("d365_pqu.pipeline.generate_workbook", fail_workbook)
    with pytest.raises(RuntimeError, match="simulated workbook failure"):
        run_sync(
            paths,
            source=_document("source-updated.md", "d" * 40),
            now=datetime(2026, 9, 25, 12, 0, tzinfo=UTC),
        )
    assert (paths.data_dir / "pqu.json").read_bytes() == before
    assert paths.workbook_path.read_bytes() == workbook_before


def test_sync_rejects_missing_source_hash(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    with pytest.raises(ValidationError):
        from d365_pqu.pipeline import verify_artifacts

        verify_artifacts(paths)
