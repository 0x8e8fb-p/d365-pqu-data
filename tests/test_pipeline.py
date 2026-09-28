from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pytest

from conftest import FIXTURES, LIVE_FIXTURES, SCHEMA_DIR
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
        source=_document("source-minimal.md", "f" * 40),
        now=datetime(2026, 10, 25, 12, 0, tzinfo=UTC),
    )
    assert result.changed is True
    assert result.status == "heartbeat"
    assert hashlib.sha256((paths.data_dir / "pqu.json").read_bytes()).hexdigest() == pqu_digest
    health = load_json(paths.data_dir / "health.json")
    assert health is not None
    assert health["checked_at"].startswith("2026-10-25")
    assert health["source_commit"] == "a" * 40
    assert health["last_source_change_at"] == "2026-09-24T12:00:00Z"
    run_health = load_json(paths.run_health_path)
    assert run_health is not None
    assert run_health["run_status"] == "heartbeat"
    assert run_health["checked_commit"] == "f" * 40


def test_same_content_at_a_new_commit_is_not_a_data_change(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    run_sync(
        paths,
        source=_document("source-minimal.md", "a" * 40),
        now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
    )
    before = {
        path.relative_to(tmp_path): path.read_bytes()
        for folder in (paths.data_dir, paths.excel_dir)
        for path in folder.rglob("*")
        if path.is_file()
    }
    result = run_sync(
        paths,
        source=_document("source-minimal.md", "b" * 40),
        now=datetime(2026, 9, 24, 13, 0, tzinfo=UTC),
    )
    assert result.changed is False
    assert result.status == "unchanged"
    assert result.source_commit == "a" * 40
    assert result.checked_commit == "b" * 40
    after = {
        path.relative_to(tmp_path): path.read_bytes()
        for folder in (paths.data_dir, paths.excel_dir)
        for path in folder.rglob("*")
        if path.is_file()
    }
    assert after == before
    pqu = load_json(paths.data_dir / "pqu.json")
    assert pqu is not None
    assert pqu["source"]["commit"] == "a" * 40
    run_health = load_json(paths.run_health_path)
    assert run_health is not None
    assert run_health["checked_at"] == "2026-09-24T13:00:00Z"
    assert run_health["last_successful_check_at"] == "2026-09-24T13:00:00Z"
    assert run_health["checked_commit"] == "b" * 40
    assert run_health["content_commit"] == "a" * 40
    assert run_health["source_commit"] == "a" * 40
    assert run_health["run_status"] == "unchanged"
    assert run_health["last_source_change_at"] == "2026-09-24T12:00:00Z"
    assert run_health["sources"]["schedule"]["state"] == "unchanged"
    assert run_health["check_interval_minutes"] == 60


def test_content_change_rewrites_data_and_run_health(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    run_sync(
        paths,
        source=_document("source-minimal.md", "a" * 40),
        now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
    )
    result = run_sync(
        paths,
        source=_document("source-updated.md", "d" * 40),
        now=datetime(2026, 9, 25, 12, 0, tzinfo=UTC),
    )
    assert result.status == "updated"
    run_health = load_json(paths.run_health_path)
    assert run_health is not None
    assert run_health["run_status"] == "updated"
    assert run_health["checked_commit"] == run_health["content_commit"] == "d" * 40
    assert run_health["last_source_change_at"] == "2026-09-25T12:00:00Z"
    assert run_health["sources"]["schedule"]["state"] == "updated"


def test_check_mode_writes_nothing(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    run_sync(
        paths,
        source=_document("source-minimal.md", "a" * 40),
        now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
        write=False,
    )
    assert not paths.data_dir.exists()
    assert not paths.run_health_path.exists()


def test_failed_check_records_run_health_without_touching_data(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    run_sync(
        paths,
        source=_document("source-minimal.md", "a" * 40),
        now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
    )
    data_health = (paths.data_dir / "health.json").read_bytes()
    with pytest.raises(ParserError):
        run_sync(
            paths,
            source=_document("source-broken.md", "e" * 40),
            now=datetime(2026, 9, 24, 13, 0, tzinfo=UTC),
        )
    assert (paths.data_dir / "health.json").read_bytes() == data_health
    run_health = load_json(paths.run_health_path)
    assert run_health is not None
    assert run_health["status"] == "failed"
    assert run_health["run_status"] == "failed"
    assert run_health["checked_at"] == "2026-09-24T13:00:00Z"
    assert run_health["last_successful_check_at"] == "2026-09-24T12:00:00Z"
    assert run_health["source_reachable"] is True
    assert run_health["parser_success"] is False
    assert run_health["validation_passed"] is False
    assert run_health["checked_commit"] == "e" * 40
    assert run_health["content_commit"] == "a" * 40
    assert "headers changed" in run_health["error"]
    assert run_health["sources"]["schedule"]["state"] == "failed"


def test_unreachable_source_is_recorded_as_a_failed_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from d365_pqu.errors import SourceFetchError

    paths = _paths(tmp_path)
    run_sync(
        paths,
        source=_document("source-minimal.md", "a" * 40),
        now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
    )

    def unreachable(**kwargs):
        raise SourceFetchError("Could not resolve MicrosoftDocs@main: timed out")

    monkeypatch.setattr("d365_pqu.pipeline.fetch_bundle", unreachable)
    with pytest.raises(SourceFetchError):
        run_sync(paths, now=datetime(2026, 9, 24, 13, 0, tzinfo=UTC))
    run_health = load_json(paths.run_health_path)
    assert run_health is not None
    assert run_health["source_reachable"] is False
    assert run_health["parser_success"] is False
    assert run_health["checked_commit"] is None
    assert run_health["error"].startswith("SourceFetchError: Could not resolve")


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


def _live_document(commit: str, markdown: str | None = None) -> SourceDocument:
    text = markdown or (LIVE_FIXTURES / "quality-updates-schedule.md").read_text(encoding="utf-8")
    return SourceDocument(
        markdown=text,
        source_commit=commit,
        article_url="https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/quality-updates-schedule",
        raw_url=f"https://raw.githubusercontent.com/example/{commit}/schedule.md",
        markdown_date=parse_markdown_date(text),
        retrieved_at=datetime(2026, 9, 28, 3, 0, tzinfo=UTC),
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def _downgrade_to_v1(paths: Paths) -> None:
    """Rewrite published data the way pipeline revision 1.0.0 wrote it."""
    import json

    pqu_path = paths.data_dir / "pqu.json"
    pqu = json.loads(pqu_path.read_text(encoding="utf-8"))
    for record in pqu["records"]:
        record.pop("station_schedule_new", None)
        record.pop("status_note", None)
    pqu_path.write_text(json.dumps(pqu), encoding="utf-8")
    metadata_path = paths.data_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["pipeline_revision"] = "1.0.0"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    (paths.data_dir / "learn.json").unlink()


def test_upgrade_from_previous_pipeline_revision_records_no_changes(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    first = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
    run_sync(paths, source=_live_document("a" * 40), now=first)
    _downgrade_to_v1(paths)
    result = run_sync(
        paths, source=_live_document("b" * 40), now=datetime(2026, 9, 28, 3, 0, tzinfo=UTC)
    )
    assert result.status == "updated"
    changes = load_json(paths.data_dir / "pqu-changes.json")
    assert changes is not None
    assert changes["records"] == []
    pqu = load_json(paths.data_dir / "pqu.json")
    assert pqu is not None
    assert {record["last_changed_at"] for record in pqu["records"]} == {"2026-09-24T12:00:00Z"}
    assert sum(record["station_schedule_new"] for record in pqu["records"]) == 3
    learn = load_json(paths.data_dir / "learn.json")
    assert learn is not None
    assert [article["key"] for article in learn["articles"]] == ["schedule"]


def test_guidance_text_change_is_recorded_per_section(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    run_sync(paths, source=_live_document("a" * 40), now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC))
    markdown = (LIVE_FIXTURES / "quality-updates-schedule.md").read_text(encoding="utf-8")
    edited = markdown.replace("receive PQUs on weekends", "receive PQUs on weekends or weekdays")
    run_sync(
        paths,
        source=_live_document("c" * 40, edited),
        now=datetime(2026, 9, 25, 12, 0, tzinfo=UTC),
    )
    changes = load_json(paths.data_dir / "pqu-changes.json")
    assert changes is not None
    guidance = [change for change in changes["records"] if change["entity"] == "guidance"]
    assert [(c["change_type"], c["field"], c["pqu_id"]) for c in guidance] == [
        ("modified", "schedule#station-to-region-mapping", "dataset")
    ]
    assert guidance[0]["old_value"]["title"] == "Station-to-region mapping"
    assert guidance[0]["old_value"]["text_sha256"] != guidance[0]["new_value"]["text_sha256"]
    assert guidance[0]["new_value"]["url"].endswith("#station-to-region-mapping")
    assert [c for c in changes["records"] if c["entity"] != "guidance"] == []


def test_guidance_failure_keeps_the_last_published_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _paths(tmp_path)
    run_sync(paths, source=_live_document("a" * 40), now=datetime(2026, 9, 24, 12, 0, tzinfo=UTC))
    before = load_json(paths.data_dir / "learn.json")

    def broken(*args, **kwargs):
        raise ParserError("simulated guidance failure")

    monkeypatch.setattr("d365_pqu.normalize.extract_article", broken)
    markdown = (LIVE_FIXTURES / "quality-updates-schedule.md").read_text(encoding="utf-8")
    edited = markdown.replace("10.0.2645.136 | 7.0.7996.119", "10.0.2645.136 | 7.0.7996.130")
    edited = edited.replace(
        "**Platform version: 7.0.7996.119**", "**Platform version: 7.0.7996.130**"
    )
    assert edited != markdown
    run_sync(
        paths,
        source=_live_document("e" * 40, edited),
        now=datetime(2026, 9, 25, 12, 0, tzinfo=UTC),
    )
    after = load_json(paths.data_dir / "learn.json")
    assert before is not None and after is not None
    assert after["articles"] == before["articles"]
    assert after["articles"][0]["commit"] == "a" * 40
    quality = load_json(paths.data_dir / "quality-report.json")
    assert quality is not None
    assert "guidance-parse-failed" in {item["code"] for item in quality["records"]}
    pqu = load_json(paths.data_dir / "pqu.json")
    assert pqu is not None
    assert pqu["source"]["commit"] == "e" * 40
