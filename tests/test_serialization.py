from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from conftest import FIXTURES, SCHEMA_DIR
from d365_pqu.config import Paths
from d365_pqu.models import SourceDocument
from d365_pqu.normalize import normalize_source
from d365_pqu.parser import parse_source
from d365_pqu.serialization import (
    current_document,
    envelope,
    flatten_pqu_record,
    health_document,
    latest_pqu_id,
    metadata_document,
    semantic_hash,
    upcoming_document,
)
from d365_pqu.source import parse_markdown_date


def _dataset(name: str = "source-minimal.md"):
    markdown = (FIXTURES / name).read_text(encoding="utf-8")
    source = SourceDocument(
        markdown=markdown,
        source_commit="a" * 40,
        article_url="https://learn.microsoft.com/example",
        raw_url="https://raw.githubusercontent.com/example/a/schedule.md",
        markdown_date=parse_markdown_date(markdown),
        retrieved_at=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
        sha256=hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
    )
    return normalize_source(
        parse_source(markdown), source, observed_at=datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
    )


def test_current_document_contains_only_in_progress() -> None:
    dataset = _dataset()
    document = current_document(dataset)
    assert document["count"] == 2
    assert document["latest_pqu_id"] == "10.0.48-PQU-6"
    assert all(record["status"] == "In-Progress" for record in document["records"])


def test_upcoming_document_contains_only_not_started() -> None:
    dataset = _dataset()
    document = upcoming_document(dataset)
    assert document["count"] == 1
    assert document["records"][0]["pqu_id"] == "10.0.48-PQU-7"


def test_latest_pqu_id_orders_by_version_and_release() -> None:
    dataset = _dataset("source-updated.md")
    assert latest_pqu_id(dataset) == "10.0.48-PQU-6"


def test_metadata_document_summarizes_dataset() -> None:
    dataset = _dataset()
    metadata = metadata_document(dataset, previous_metadata=None, generated_at=dataset.generated_at)
    assert metadata["record_count"] == 4
    assert metadata["current_count"] == 2
    assert metadata["upcoming_count"] == 1
    assert metadata["status_counts"]["Canceled"] == 1
    assert metadata["source"]["commit"] == "a" * 40
    assert metadata["links"]["api_pqu"].endswith("/api/pqu.json")


def test_health_document_preserves_source_change_time() -> None:
    dataset = _dataset()
    previous = {
        "last_source_change_at": "2026-09-01T00:00:00Z",
        "last_successful_publish_at": "2026-09-01T00:00:00Z",
    }
    health = health_document(
        dataset,
        previous_health=previous,
        checked_at=datetime(2026, 9, 24, 12, 0, tzinfo=UTC),
        changed=False,
    )
    assert health["last_source_change_at"] == "2026-09-01T00:00:00Z"
    assert health["checked_at"].startswith("2026-09-24")


def test_envelope_and_flatten_output() -> None:
    dataset = _dataset()
    document = envelope(
        [dict(record) for record in dataset.records],
        source=dataset.source,
        generated_at=dataset.generated_at,
    )
    assert document["dataset"] == "d365-finops-pqu"
    flat = flatten_pqu_record(dict(dataset.records[0]))
    assert flat["source_commit"] == "a" * 40
    assert flat["pqu_id"] == dataset.records[0]["pqu_id"]


def test_semantic_hash_is_stable_and_ignores_provenance_times() -> None:
    dataset = _dataset()
    first = semantic_hash(dataset)
    dataset.records[0]["last_changed_at"] = "2030-01-01T00:00:00Z"
    second = semantic_hash(dataset)
    assert first == second
    dataset.records[0]["platform_build"] = "9.9.9.9"
    assert semantic_hash(dataset) != first


def test_schema_directory_has_all_documents() -> None:
    for name in (
        "pqu.schema.json",
        "station.schema.json",
        "region.schema.json",
        "version.schema.json",
        "change.schema.json",
        "quality-report.schema.json",
        "metadata.schema.json",
        "health.schema.json",
    ):
        assert (SCHEMA_DIR / name).exists()
    assert Paths.from_root(Path.cwd()).root.exists()
