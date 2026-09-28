from __future__ import annotations

import json
import os
import shutil
import uuid
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from d365_pqu.config import HEARTBEAT_DAYS, PIPELINE_REVISION, SCHEDULE_SPEC, SOURCE_SPECS, Paths
from d365_pqu.diff import (
    MAINTENANCE_WINDOW_FIELDS,
    SERVICE_UPDATE_FIELDS,
    KeyedRecords,
    compute_changes,
)
from d365_pqu.errors import PublishError, ValidationError
from d365_pqu.excel import generate_workbook
from d365_pqu.maintenance import assign_maintenance_geos
from d365_pqu.models import NormalizedDataset, SourceBundle, SourceDocument, SyncResult
from d365_pqu.normalize import normalize_source
from d365_pqu.parser import parse_source
from d365_pqu.serialization import (
    CHANGE_CSV_FIELDS,
    EVENT_CSV_FIELDS,
    INSIGHT_CSV_FIELDS,
    MAINTENANCE_WINDOW_CSV_FIELDS,
    PQU_CSV_FIELDS,
    QUALITY_CSV_FIELDS,
    REGION_CSV_FIELDS,
    SERVICE_UPDATE_CSV_FIELDS,
    STATION_CSV_FIELDS,
    VERSION_CSV_FIELDS,
    changes_document,
    current_document,
    envelope,
    events_document,
    flatten_pqu_record,
    flatten_sourced_record,
    flatten_station_record,
    health_document,
    insights_document,
    learn_document_for,
    metadata_document,
    quality_document,
    run_health_document,
    source_dataset_document,
    upcoming_document,
    write_csv,
    write_json,
)
from d365_pqu.source import (
    bundle_from_directory,
    bundle_from_document,
    bundle_from_file,
    document_for,
    fetch_bundle,
    raw_url_for_commit,
)
from d365_pqu.sources import (
    PUBLISHED_STATES,
    SourceOutput,
    previous_sources,
    process_optional_sources,
    source_entry,
    source_identity,
)
from d365_pqu.validation import (
    validate_document,
    validate_maintenance_windows,
    validate_quality,
    validate_records,
    validate_region_geos,
    validate_service_updates,
)

EXPECTED_SHEETS = (
    "00_README",
    "01_PQU_MASTER",
    "02_CURRENT_PQU",
    "03_UPCOMING_PQU",
    "04_STATION_SCHEDULE",
    "05_REGION_MAPPING",
    "06_APPLICATION_BUILDS",
    "07_PLATFORM_BUILDS",
    "08_UEP_BUILDS",
    "09_STATUS_HISTORY",
    "10_CHANGE_HISTORY",
    "11_SOURCE_METADATA",
    "12_SYNC_HEALTH",
    "13_DATA_QUALITY",
    "14_SERVICE_UPDATES",
    "15_MAINTENANCE_WINDOWS",
    "16_INSIGHTS",
    "17_KEY_DATES",
)


@dataclass(frozen=True)
class SourcedDataset:
    """A dataset published from one optional article, with that article's own provenance."""

    document: str
    csv: str
    schema: str
    source_key: str
    attr: str
    count_key: str
    csv_fields: tuple[str, ...]
    sheet: str
    entity: str
    key: str
    fields: tuple[str, ...]
    validate: Callable[[Iterable[Mapping[str, Any]]], None]

    def records(self, dataset: NormalizedDataset) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = getattr(dataset, self.attr)
        return records


SOURCED_DATASETS = (
    SourcedDataset(
        document="service-updates.json",
        csv="service-updates.csv",
        schema="service-update.schema.json",
        source_key="service_updates",
        attr="service_updates",
        count_key="service_update_count",
        csv_fields=SERVICE_UPDATE_CSV_FIELDS,
        sheet="14_SERVICE_UPDATES",
        entity="service_update",
        key="version",
        fields=SERVICE_UPDATE_FIELDS,
        validate=validate_service_updates,
    ),
    SourcedDataset(
        document="maintenance-windows.json",
        csv="maintenance-windows.csv",
        schema="maintenance-window.schema.json",
        source_key="maintenance",
        attr="maintenance_windows",
        count_key="maintenance_window_count",
        csv_fields=MAINTENANCE_WINDOW_CSV_FIELDS,
        sheet="15_MAINTENANCE_WINDOWS",
        entity="maintenance_window",
        key="geo",
        fields=MAINTENANCE_WINDOW_FIELDS,
        validate=validate_maintenance_windows,
    ),
)

SCHEMA_FOR_DOCUMENT = {
    "pqu.json": "pqu.schema.json",
    "pqu-current.json": "pqu.schema.json",
    "pqu-upcoming.json": "pqu.schema.json",
    "pqu-stations.json": "station.schema.json",
    "pqu-regions.json": "region.schema.json",
    "pqu-versions.json": "version.schema.json",
    "pqu-changes.json": "change.schema.json",
    "quality-report.json": "quality-report.schema.json",
    "learn.json": "learn.schema.json",
    **{sourced.document: sourced.schema for sourced in SOURCED_DATASETS},
    "insights.json": "insights.schema.json",
    "events.json": "event.schema.json",
    "metadata.json": "metadata.schema.json",
    "health.json": "health.schema.json",
}
# Documents built from one optional article carry that article's provenance.
SOURCE_DOCUMENTS = {sourced.document: sourced.source_key for sourced in SOURCED_DATASETS}
CHANGE_ENTITIES = frozenset(
    {"pqu", "station", "region", "guidance", *(sourced.entity for sourced in SOURCED_DATASETS)}
)


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path} is not valid JSON: {exc}") from exc


def load_previous(
    paths: Paths,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    pqu = load_json(paths.pqu_path)
    metadata = load_json(paths.metadata_path)
    health = load_json(paths.health_path)
    return pqu, metadata, health


def previous_records(pqu: dict[str, Any] | None) -> list[dict[str, Any]] | None:
    if not pqu:
        return None
    records = pqu.get("records")
    if not isinstance(records, list):
        return None
    return [record for record in records if isinstance(record, dict)]


def source_document_from_file(
    path: Path,
    *,
    commit: str,
    now: datetime,
) -> SourceDocument:
    """The schedule article read from a local file, with provenance for ``commit``."""
    return document_for(
        SCHEDULE_SPEC,
        path.read_text(encoding="utf-8"),
        commit=commit,
        raw_url=raw_url_for_commit(commit, file_path=SCHEDULE_SPEC.file_path),
        retrieved_at=now,
    )


def _records_of(document: dict[str, Any] | None) -> list[dict[str, Any]]:
    records = document.get("records") if document else None
    if not isinstance(records, list):
        return []
    return [record for record in records if isinstance(record, dict)]


def heartbeat_due(health: dict[str, Any] | None, now: datetime) -> bool:
    if not health:
        return True
    checked = health.get("checked_at")
    if not isinstance(checked, str):
        return True
    try:
        previous = datetime.fromisoformat(checked.replace("Z", "+00:00"))
    except ValueError:
        return True
    if previous.tzinfo is None:
        previous = previous.replace(tzinfo=UTC)
    return now - previous >= timedelta(days=HEARTBEAT_DAYS)


def _atomic_write_json(path: Path, document: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    write_json(temporary, document)
    os.replace(temporary, path)


def _write_artifacts(
    paths: Paths,
    *,
    dataset: NormalizedDataset,
    documents: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
    health: dict[str, Any],
    quality: Mapping[str, Any],
) -> None:
    staging = paths.root / f".d365-pqu-staging-{uuid.uuid4().hex}"
    staged_paths = Paths(
        root=staging,
        data_dir=staging / "data",
        excel_dir=staging / "excel",
        schema_dir=paths.schema_dir,
        site_dir=staging / "site",
        tests_dir=paths.tests_dir,
    )
    try:
        if (paths.data_dir / "history").exists():
            shutil.copytree(
                paths.data_dir / "history",
                staged_paths.data_dir / "history",
                dirs_exist_ok=True,
            )
        _write_artifacts_in_place(
            staged_paths,
            dataset=dataset,
            documents=documents,
            metadata=metadata,
            health=health,
            quality=quality,
        )
        verify_artifacts(staged_paths)
        _swap_directories(
            (staged_paths.data_dir, paths.data_dir),
            (staged_paths.excel_dir, paths.excel_dir),
        )
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _swap_directories(*pairs: tuple[Path, Path]) -> None:
    backups: list[tuple[Path, Path | None]] = []
    try:
        for source, target in pairs:
            backup = target.with_name(f".{target.name}.backup-{uuid.uuid4().hex}")
            if target.exists():
                os.replace(target, backup)
                backups.append((target, backup))
            else:
                backups.append((target, None))
            os.replace(source, target)
        for _, saved in backups:
            if saved is not None and saved.exists():
                shutil.rmtree(saved)
    except Exception:
        for target, saved in reversed(backups):
            if target.exists():
                shutil.rmtree(target)
            if saved is not None and saved.exists():
                os.replace(saved, target)
        raise


def _write_artifacts_in_place(
    paths: Paths,
    *,
    dataset: NormalizedDataset,
    documents: dict[str, dict[str, Any]],
    metadata: dict[str, Any],
    health: dict[str, Any],
    quality: Mapping[str, Any],
) -> None:
    for name, document in documents.items():
        _atomic_write_json(paths.data_dir / name, document)

    records = dataset.records
    write_csv(
        paths.data_dir / "pqu.csv",
        (flatten_pqu_record(record) for record in records),
        PQU_CSV_FIELDS,
    )
    write_csv(
        paths.data_dir / "pqu-current.csv",
        (flatten_pqu_record(r) for r in records if r["status"] == "In-Progress"),
        PQU_CSV_FIELDS,
    )
    write_csv(
        paths.data_dir / "pqu-upcoming.csv",
        (flatten_pqu_record(r) for r in records if r["status"] == "Not Started"),
        PQU_CSV_FIELDS,
    )
    write_csv(
        paths.data_dir / "pqu-stations.csv",
        (flatten_station_record(record) for record in dataset.stations),
        STATION_CSV_FIELDS,
    )
    write_csv(
        paths.data_dir / "pqu-regions.csv",
        (dict(record) for record in dataset.regions),
        REGION_CSV_FIELDS,
    )
    write_csv(
        paths.data_dir / "pqu-versions.csv",
        (dict(record) for record in dataset.versions),
        VERSION_CSV_FIELDS,
    )
    write_csv(
        paths.data_dir / "pqu-changes.csv",
        (dict(record) for record in dataset.changes),
        CHANGE_CSV_FIELDS,
    )
    write_csv(
        paths.data_dir / "quality-report.csv",
        (dict(record) for record in quality.get("records", [])),
        QUALITY_CSV_FIELDS,
    )
    for sourced in SOURCED_DATASETS:
        source = dataset.sources.get(sourced.source_key, {}).get("source")
        write_csv(
            paths.data_dir / sourced.csv,
            (flatten_sourced_record(record, source) for record in sourced.records(dataset)),
            sourced.csv_fields,
        )
    insights = documents["insights.json"]
    write_csv(
        paths.data_dir / "insights.csv",
        (dict(record) for record in insights["records"]),
        INSIGHT_CSV_FIELDS,
    )
    events = documents["events.json"]
    write_csv(
        paths.data_dir / "events.csv",
        (dict(record) for record in events["records"]),
        EVENT_CSV_FIELDS,
    )

    history_dir = (
        paths.data_dir
        / "history"
        / f"{dataset.generated_at.year:04d}"
        / f"{dataset.generated_at.month:02d}"
    )
    history_name = (
        f"{dataset.generated_at.strftime('%Y-%m-%dT%H%M%S%fZ')}-"
        f"{dataset.source['commit'][:12]}.json"
    )
    _atomic_write_json(history_dir / history_name, documents["pqu.json"])

    generate_workbook(
        paths.workbook_path,
        dataset=dataset,
        metadata=metadata,
        health=health,
        quality=quality,
        insights=insights,
        events=events,
    )


def build_documents(
    dataset: NormalizedDataset,
    previous_metadata: dict[str, Any] | None,
    previous_health: dict[str, Any] | None,
    changed: bool,
) -> dict[str, dict[str, Any]]:
    source = dict(dataset.source)
    metadata = metadata_document(
        dataset,
        previous_metadata=previous_metadata,
        generated_at=dataset.generated_at,
    )
    health = health_document(
        dataset,
        previous_health=previous_health,
        checked_at=dataset.generated_at,
        changed=changed,
    )
    quality = quality_document(
        dataset.quality,
        source=source,
        generated_at=dataset.generated_at,
    )
    documents = {
        "pqu.json": envelope(
            [dict(record) for record in dataset.records],
            source=source,
            generated_at=dataset.generated_at,
        ),
        "pqu-current.json": current_document(dataset),
        "pqu-upcoming.json": upcoming_document(dataset),
        "pqu-stations.json": envelope(
            [dict(record) for record in dataset.stations],
            source=source,
            generated_at=dataset.generated_at,
        ),
        "pqu-regions.json": envelope(
            [dict(record) for record in dataset.regions],
            source=source,
            generated_at=dataset.generated_at,
        ),
        "pqu-versions.json": envelope(
            [dict(record) for record in dataset.versions],
            source=source,
            generated_at=dataset.generated_at,
        ),
        "pqu-changes.json": changes_document(
            [dict(record) for record in dataset.changes],
            source=source,
            generated_at=dataset.generated_at,
        ),
        "quality-report.json": quality,
        "learn.json": learn_document_for(
            dataset.articles, source=source, generated_at=dataset.generated_at
        ),
        **{
            sourced.document: source_dataset_document(
                sourced.records(dataset),
                source_key=sourced.source_key,
                entry=dataset.sources[sourced.source_key],
                generated_at=dataset.generated_at,
            )
            for sourced in SOURCED_DATASETS
        },
        "insights.json": insights_document(
            dataset, source=source, generated_at=dataset.generated_at
        ),
        "events.json": events_document(dataset, source=source, generated_at=dataset.generated_at),
        "metadata.json": metadata,
        "health.json": health,
    }
    return documents


def validate_documents(paths: Paths, documents: dict[str, dict[str, Any]]) -> None:
    for name, document in documents.items():
        schema_name = SCHEMA_FOR_DOCUMENT[name]
        validate_document(document, paths.schema_dir / schema_name)


def _unchanged_result(
    paths: Paths,
    *,
    source_hash: str,
    source_commit: str,
    checked_commit: str,
    previous_metadata: dict[str, Any] | None,
    heartbeat: bool,
    source_states: dict[str, str] | None = None,
) -> SyncResult:
    metadata = previous_metadata or {}
    quality = load_json(paths.data_dir / "quality-report.json") or {}
    warnings = int(quality.get("warning_count", 0)) if isinstance(quality, dict) else 0
    return SyncResult(
        changed=heartbeat,
        status="heartbeat" if heartbeat else "unchanged",
        source_hash=source_hash,
        source_commit=source_commit,
        record_count=int(metadata.get("record_count", 0)),
        current_count=int(metadata.get("current_count", 0)),
        upcoming_count=int(metadata.get("upcoming_count", 0)),
        warning_count=warnings,
        error_count=0,
        data_dir=str(paths.data_dir),
        workbook_path=str(paths.workbook_path),
        site_dir=str(paths.site_dir),
        checked_commit=checked_commit,
        source_states=dict(source_states or {}),
    )


@dataclass
class _Attempt:
    """How far a sync run got, so a failed run can still report an accurate check."""

    stage: str = "fetch"
    checked_commit: str | None = None


def run_sync(
    paths: Paths,
    *,
    source: SourceDocument | None = None,
    bundle: SourceBundle | None = None,
    now: datetime | None = None,
    write: bool = True,
) -> SyncResult:
    """Check the Microsoft sources and publish a new dataset when their content changed.

    ``bundle`` supplies pre-read source articles; ``source`` supplies only the schedule article;
    with neither, every configured article is downloaded at the current MicrosoftDocs commit.
    """
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    attempt = _Attempt()
    try:
        return _sync(
            paths, source=source, bundle=bundle, moment=moment, write=write, attempt=attempt
        )
    except Exception as exc:
        if write:
            write_failed_run_health(paths, moment=moment, attempt=attempt, error=exc)
        raise


def _published_source(pqu: dict[str, Any] | None) -> dict[str, Any] | None:
    source = pqu.get("source") if pqu else None
    return source if isinstance(source, dict) else None


def _sticky_schedule(document: SourceDocument, published: dict[str, Any] | None) -> SourceDocument:
    """Keep the published provenance while the schedule article bytes are unchanged."""
    if (
        published
        and published.get("sha256") == document.sha256
        and published.get("file_path", document.file_path) == document.file_path
        and isinstance(published.get("commit"), str)
        and isinstance(published.get("raw_url"), str)
    ):
        return replace(
            document,
            source_commit=published["commit"],
            raw_url=published["raw_url"],
            retrieved_at=_instant(published.get("retrieved_at")) or document.retrieved_at,
        )
    return document


def _apply_outputs(dataset: NormalizedDataset, outputs: dict[str, SourceOutput]) -> None:
    dataset.sources = {SCHEDULE_SPEC.key: source_entry(SCHEDULE_SPEC, "current", dataset.source)}
    for spec in SOURCE_SPECS:
        output = outputs.get(spec.key)
        if spec.required or output is None:
            continue
        dataset.sources[spec.key] = source_entry(spec, output.state, output.source)
        dataset.articles.extend(output.articles)
    for sourced in SOURCED_DATASETS:
        output = outputs.get(sourced.source_key)
        setattr(dataset, sourced.attr, list(output.records) if output else [])
    maintenance = outputs.get("maintenance")
    if maintenance is not None and maintenance.state in PUBLISHED_STATES:
        dataset.quality.extend(
            assign_maintenance_geos(dataset.regions, dataset.maintenance_windows)
        )


def _run_sources(
    sources: dict[str, dict[str, Any]],
    previous_identity: dict[str, tuple[Any, Any]],
    messages: dict[str, str],
) -> dict[str, dict[str, Any]]:
    """Per-source state of this check, for run health."""
    entries: dict[str, dict[str, Any]] = {}
    for key, entry in sources.items():
        source = entry.get("source") or {}
        state = entry["state"]
        if state == "current":
            unchanged = previous_identity.get(key) == (source.get("sha256"), "current")
            state = "unchanged" if unchanged else "updated"
        item: dict[str, Any] = {
            "state": state,
            "commit": source.get("commit"),
            "sha256": source.get("sha256"),
            "markdown_date": source.get("markdown_date"),
        }
        if key in messages:
            item["message"] = messages[key][:500]
        entries[key] = item
    return entries


def _sync(
    paths: Paths,
    *,
    source: SourceDocument | None,
    bundle: SourceBundle | None,
    moment: datetime,
    write: bool,
    attempt: _Attempt,
) -> SyncResult:
    pqu, previous_metadata, previous_health = load_previous(paths)
    previous_learn = load_json(paths.data_dir / "learn.json")
    previous_sourced = {
        sourced.source_key: _records_of(load_json(paths.data_dir / sourced.document))
        for sourced in SOURCED_DATASETS
    }
    if bundle is None:
        bundle = bundle_from_document(source) if source is not None else fetch_bundle(now=moment)
    attempt.stage = "parse"
    attempt.checked_commit = bundle.commit
    published_source = _published_source(pqu)
    schedule = _sticky_schedule(bundle.schedule, published_source)
    parsed = parse_source(schedule.markdown)
    dataset = normalize_source(
        parsed, schedule, previous=pqu, observed_at=moment, previous_learn=previous_learn
    )
    outputs = process_optional_sources(
        bundle,
        previous_metadata=previous_metadata,
        previous_records=previous_sourced,
        previous_learn=previous_learn,
        quality=dataset.quality,
    )
    _apply_outputs(dataset, outputs)
    attempt.stage = "validate"
    validate_quality(dataset)
    validate_records(dataset)
    for sourced in SOURCED_DATASETS:
        sourced.validate(sourced.records(dataset))
    validate_region_geos(dataset.regions, dataset.maintenance_windows)

    # Identity is each source article's content and publication state plus the generator
    # revision. A new upstream commit that leaves the articles unchanged is not a data change,
    # so provenance stays pinned to the commit where the published content was retrieved.
    published_sources = previous_sources(previous_metadata)
    previous_identity = source_identity(published_sources)
    identity_unchanged = bool(
        pqu
        and published_source
        and (previous_metadata or {}).get("pipeline_revision") == PIPELINE_REVISION
        and previous_identity == source_identity(dataset.sources)
    )
    messages = {key: output.message for key, output in outputs.items() if output.message}
    run_sources = _run_sources(dataset.sources, previous_identity, messages)
    source_states = {key: entry["state"] for key, entry in run_sources.items()}
    heartbeat = heartbeat_due(previous_health, moment)
    if identity_unchanged and published_source is not None:
        attempt.stage = "publish"
        if heartbeat and write:
            _refresh_health_only(
                paths,
                dataset=dataset,
                published_source=published_source,
                previous_health=previous_health,
                now=moment,
            )
        result = _unchanged_result(
            paths,
            source_hash=schedule.sha256,
            source_commit=str(published_source.get("commit")),
            checked_commit=bundle.commit,
            previous_metadata=previous_metadata,
            heartbeat=heartbeat,
            source_states=source_states,
        )
        if write:
            write_run_health(
                paths,
                checked_at=moment,
                checked_commit=bundle.commit,
                run_status=result.status,
                sources=run_sources,
            )
        return result

    previous_change_document = load_json(paths.data_dir / "pqu-changes.json")
    prior_changes = (
        previous_change_document.get("records", [])
        if previous_change_document and isinstance(previous_change_document.get("records"), list)
        else []
    )
    previous_station_document = load_json(paths.data_dir / "pqu-stations.json")
    previous_region_document = load_json(paths.data_dir / "pqu-regions.json")
    previous_stations = (
        previous_station_document.get("records", [])
        if previous_station_document and isinstance(previous_station_document.get("records"), list)
        else []
    )
    previous_regions = (
        previous_region_document.get("records", [])
        if previous_region_document and isinstance(previous_region_document.get("records"), list)
        else []
    )
    previous_articles = (
        previous_learn.get("articles")
        if previous_learn and isinstance(previous_learn.get("articles"), list)
        else None
    )
    keyed = []
    for sourced in SOURCED_DATASETS:
        previous_entry = published_sources.get(sourced.source_key) or {}
        entry = dataset.sources[sourced.source_key]
        keyed.append(
            KeyedRecords(
                entity=sourced.entity,
                key=sourced.key,
                fields=sourced.fields,
                previous=(
                    previous_sourced[sourced.source_key]
                    if previous_entry.get("state") in PUBLISHED_STATES
                    else None
                ),
                current=(sourced.records(dataset) if entry["state"] in PUBLISHED_STATES else None),
                source_commit=(entry.get("source") or {}).get("commit"),
            )
        )
    new_changes = compute_changes(
        previous_records(pqu),
        [dict(record) for record in dataset.records],
        source_commit=schedule.source_commit,
        changed_at=moment,
        previous_stations=previous_stations,
        current_stations=[dict(record) for record in dataset.stations],
        previous_regions=previous_regions,
        current_regions=[dict(record) for record in dataset.regions],
        previous_articles=previous_articles,
        current_articles=[dict(article) for article in dataset.articles],
        keyed=keyed,
    )
    changed_station_ids = {
        change["pqu_id"] for change in new_changes if change["entity"] == "station"
    }
    if changed_station_ids:
        changed_at = moment.isoformat().replace("+00:00", "Z")
        for record in dataset.records:
            if record["pqu_id"] in changed_station_ids:
                record["last_changed_at"] = changed_at
    dataset.changes = [*prior_changes, *new_changes]
    validate_quality(dataset)
    validate_records(dataset)

    documents = build_documents(dataset, previous_metadata, previous_health, True)
    validate_documents(paths, documents)

    attempt.stage = "publish"
    if write:
        _write_artifacts(
            paths,
            dataset=dataset,
            documents=documents,
            metadata=documents["metadata.json"],
            health=documents["health.json"],
            quality=documents["quality-report.json"],
        )
        write_run_health(
            paths,
            checked_at=moment,
            checked_commit=bundle.commit,
            run_status="updated",
            sources=run_sources,
        )

    return SyncResult(
        changed=True,
        status="updated",
        source_hash=schedule.sha256,
        source_commit=schedule.source_commit,
        record_count=len(dataset.records),
        current_count=sum(1 for record in dataset.records if record["status"] == "In-Progress"),
        upcoming_count=sum(1 for record in dataset.records if record["status"] == "Not Started"),
        warning_count=sum(1 for item in dataset.quality if item["severity"] == "warning"),
        error_count=0,
        data_dir=str(paths.data_dir),
        workbook_path=str(paths.workbook_path),
        site_dir=str(paths.site_dir),
        checked_commit=bundle.commit,
        source_states=source_states,
    )


def run_fixture_sync(paths: Paths, source: Path, *, commit: str, now: datetime) -> SyncResult:
    """Synchronize from a local schedule file or a directory of source articles (tests, demos)."""
    bundle = (
        bundle_from_directory(source, commit=commit, now=now)
        if source.is_dir()
        else bundle_from_file(source, commit=commit, now=now)
    )
    return run_sync(paths, bundle=bundle, now=now)


def _refresh_health_only(
    paths: Paths,
    *,
    dataset: NormalizedDataset,
    published_source: dict[str, Any],
    previous_health: dict[str, Any] | None,
    now: datetime,
) -> None:
    health = health_document(
        dataset,
        previous_health=previous_health,
        checked_at=now,
        changed=False,
        source=published_source,
    )
    validate_document(health, paths.schema_dir / "health.schema.json")
    _atomic_write_json(paths.health_path, health)


def write_run_health(
    paths: Paths,
    *,
    checked_at: datetime,
    checked_commit: str,
    run_status: str,
    sources: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Record this check in the untracked run-health file that the site publishes."""
    data_health = load_json(paths.health_path)
    if not data_health:
        raise PublishError(f"{paths.health_path} is missing; cannot record run health")
    document = run_health_document(
        data_health,
        checked_at=checked_at,
        checked_commit=checked_commit,
        run_status=run_status,
        sources=sources,
    )
    validate_document(document, paths.schema_dir / "health.schema.json")
    _atomic_write_json(paths.run_health_path, document)
    return document


def _failure_message(error: BaseException) -> str:
    text = " ".join(f"{type(error).__name__}: {error}".split())
    return text if len(text) <= 500 else text[:497] + "..."


def write_failed_run_health(
    paths: Paths, *, moment: datetime, attempt: _Attempt, error: BaseException
) -> None:
    """Best effort record of a failed check. Published data is never touched."""
    try:
        data_health = load_json(paths.health_path)
        if not data_health:
            return
        try:
            previous_run = load_json(paths.run_health_path)
        except ValidationError:
            previous_run = None
        stage = attempt.stage
        message = _failure_message(error)
        failure = {
            "source_reachable": stage != "fetch",
            "parser_success": stage not in ("fetch", "parse"),
            "validation_passed": stage not in ("fetch", "parse", "validate"),
            "error": message,
        }
        sources = {
            "schedule": {
                "state": "failed",
                "commit": data_health.get("source_commit"),
                "sha256": data_health.get("source_sha256"),
                "message": message,
            }
        }
        document = run_health_document(
            data_health,
            checked_at=moment,
            checked_commit=attempt.checked_commit,
            run_status="failed",
            sources=sources,
            previous_run_health=previous_run,
            failure=failure,
        )
        validate_document(document, paths.schema_dir / "health.schema.json")
        _atomic_write_json(paths.run_health_path, document)
    except Exception:
        # Never mask the original failure with a secondary error while recording it.
        return


def _instant(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def published_health_path(paths: Paths, metadata: dict[str, Any]) -> tuple[Path, str]:
    """Prefer this run's health when it describes the dataset being published."""
    run_health: dict[str, Any] | None
    try:
        run_health = load_json(paths.run_health_path)
        if run_health:
            validate_document(run_health, paths.schema_dir / "health.schema.json")
    except ValidationError:
        return paths.health_path, "data"
    if not run_health:
        return paths.health_path, "data"
    raw_source = metadata.get("source")
    source: dict[str, Any] = raw_source if isinstance(raw_source, dict) else {}
    data_health = load_json(paths.health_path) or {}
    run_checked = _instant(run_health.get("checked_at"))
    data_checked = _instant(data_health.get("checked_at"))
    consistent = (
        run_health.get("content_commit") == source.get("commit")
        and run_health.get("source_sha256") == source.get("sha256")
        and run_checked is not None
        and (data_checked is None or run_checked >= data_checked)
    )
    return (paths.run_health_path, "run") if consistent else (paths.health_path, "data")


def build_site(paths: Paths) -> dict[str, str]:
    from d365_pqu.site import generate_site

    metadata = load_json(paths.metadata_path)
    if not metadata:
        raise PublishError("metadata.json is missing; run sync before building the site")
    health_path, health_source = published_health_path(paths, metadata)
    generate_site(
        site_dir=paths.site_dir,
        data_dir=paths.data_dir,
        schema_dir=paths.schema_dir,
        workbook_path=paths.workbook_path,
        metadata=metadata,
        static_dir=Path(__file__).parent / "static",
        health_path=health_path,
    )
    return {"site_dir": str(paths.site_dir), "health_source": health_source}


def _document_records(document: dict[str, Any], name: str) -> list[dict[str, Any]]:
    records = document.get("records")
    if not isinstance(records, list) or not all(isinstance(record, dict) for record in records):
        raise ValidationError(f"{name} has an invalid records collection")
    return records


def _verify_csv(
    path: Path,
    *,
    fieldnames: tuple[str, ...],
    expected_count: int,
) -> None:
    import csv

    if not path.exists():
        raise ValidationError(f"Missing generated CSV {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != fieldnames:
            raise ValidationError(
                f"{path.name} headers do not match the generated schema: {reader.fieldnames}"
            )
        rows = list(reader)
    if len(rows) != expected_count:
        raise ValidationError(f"{path.name} has {len(rows)} rows; expected {expected_count}")


def verify_artifacts(paths: Paths) -> dict[str, Any]:
    documents: dict[str, dict[str, Any]] = {}
    for name, schema_name in SCHEMA_FOR_DOCUMENT.items():
        document = load_json(paths.data_dir / name)
        if document is None:
            raise ValidationError(f"Missing required artifact {paths.data_dir / name}")
        validate_document(document, paths.schema_dir / schema_name)
        documents[name] = document

    pqu_records = _document_records(documents["pqu.json"], "pqu.json")
    pqu_ids = [record["pqu_id"] for record in pqu_records]
    if len(pqu_ids) != len(set(pqu_ids)):
        raise ValidationError("pqu.json contains duplicate identifiers")
    pqu_by_id = {record["pqu_id"]: record for record in pqu_records}
    current_records = _document_records(documents["pqu-current.json"], "pqu-current.json")
    upcoming_records = _document_records(documents["pqu-upcoming.json"], "pqu-upcoming.json")
    expected_current = [record for record in pqu_records if record["status"] == "In-Progress"]
    expected_upcoming = [record for record in pqu_records if record["status"] == "Not Started"]
    if [record["pqu_id"] for record in current_records] != [
        record["pqu_id"] for record in expected_current
    ]:
        raise ValidationError("pqu-current.json does not contain the In-Progress records")
    if [record["pqu_id"] for record in upcoming_records] != [
        record["pqu_id"] for record in expected_upcoming
    ]:
        raise ValidationError("pqu-upcoming.json does not contain the Not Started records")
    if documents["pqu-current.json"].get("latest_pqu_id") != documents["metadata.json"].get(
        "latest_pqu_id"
    ):
        raise ValidationError("Current latest_pqu_id does not match metadata.json")

    source = documents["pqu.json"]["source"]
    metadata = documents["metadata.json"]
    for name, document in documents.items():
        if name == "health.json" or name in SOURCE_DOCUMENTS:
            continue
        if document["source"] != source:
            raise ValidationError(f"Source provenance differs in {name}")
    _verify_sources(metadata, documents)
    if metadata.get("pipeline_revision") != PIPELINE_REVISION:
        raise ValidationError("metadata.json pipeline revision is stale")
    if metadata.get("record_count") != len(pqu_records):
        raise ValidationError("metadata record_count does not match pqu.json")
    if metadata.get("current_count") != len(current_records):
        raise ValidationError("metadata current_count does not match pqu-current.json")
    if metadata.get("upcoming_count") != len(upcoming_records):
        raise ValidationError("metadata upcoming_count does not match pqu-upcoming.json")

    station_records = _document_records(documents["pqu-stations.json"], "pqu-stations.json")
    region_records = _document_records(documents["pqu-regions.json"], "pqu-regions.json")
    version_records = _document_records(documents["pqu-versions.json"], "pqu-versions.json")
    change_records = _document_records(documents["pqu-changes.json"], "pqu-changes.json")
    quality_records = _document_records(documents["quality-report.json"], "quality-report.json")
    sourced_records: dict[str, list[dict[str, Any]]] = {}
    for sourced in SOURCED_DATASETS:
        rows = _document_records(documents[sourced.document], sourced.document)
        if len(rows) != metadata.get(sourced.count_key):
            raise ValidationError(f"metadata {sourced.count_key} does not match {sourced.document}")
        if documents[sourced.document].get("count") != len(rows):
            raise ValidationError(f"{sourced.document} count does not match records")
        try:
            sourced.validate(rows)
        except ValidationError as exc:
            raise ValidationError(f"{sourced.document}: {exc}") from exc
        sourced_records[sourced.document] = rows
    try:
        validate_region_geos(region_records, sourced_records["maintenance-windows.json"])
    except ValidationError as exc:
        raise ValidationError(f"pqu-regions.json: {exc}") from exc
    if len(station_records) != metadata.get("station_schedule_count"):
        raise ValidationError("metadata station_schedule_count does not match stations")
    if len(region_records) != metadata.get("region_count"):
        raise ValidationError("metadata region_count does not match regions")
    if len(quality_records) != documents["quality-report.json"].get("count"):
        raise ValidationError("quality-report count does not match records")
    if any(record["pqu_id"] not in pqu_by_id for record in station_records):
        raise ValidationError("Station schedule references an unknown PQU")
    if any(record["pqu_id"] not in pqu_by_id for record in version_records):
        raise ValidationError("Version record references an unknown PQU")
    if any(change.get("entity") not in CHANGE_ENTITIES for change in change_records):
        raise ValidationError("Change history contains an unknown entity")
    _verify_learn(documents["learn.json"])
    insight_records = _verify_insights(documents["insights.json"])
    event_records = _verify_events(
        documents["events.json"], pqu_by_id=pqu_by_id, stations=station_records
    )
    for record in station_records:
        if not pqu_by_id[record["pqu_id"]].get("station_schedule_available"):
            raise ValidationError(
                f"Station schedule is not marked available for {record['pqu_id']}"
            )

    expected_csvs = {
        "pqu.csv": (PQU_CSV_FIELDS, len(pqu_records)),
        "pqu-current.csv": (PQU_CSV_FIELDS, len(current_records)),
        "pqu-upcoming.csv": (PQU_CSV_FIELDS, len(upcoming_records)),
        "pqu-stations.csv": (STATION_CSV_FIELDS, len(station_records)),
        "pqu-regions.csv": (REGION_CSV_FIELDS, len(region_records)),
        "pqu-versions.csv": (VERSION_CSV_FIELDS, len(version_records)),
        "pqu-changes.csv": (CHANGE_CSV_FIELDS, len(change_records)),
        "quality-report.csv": (QUALITY_CSV_FIELDS, len(quality_records)),
        "insights.csv": (INSIGHT_CSV_FIELDS, len(insight_records)),
        "events.csv": (EVENT_CSV_FIELDS, len(event_records)),
        **{
            sourced.csv: (sourced.csv_fields, len(sourced_records[sourced.document]))
            for sourced in SOURCED_DATASETS
        },
    }
    for name, (fields, count) in expected_csvs.items():
        _verify_csv(paths.data_dir / name, fieldnames=fields, expected_count=count)

    workbook = paths.workbook_path
    if not workbook.exists():
        raise ValidationError(f"Missing workbook {workbook}")
    from openpyxl import load_workbook

    wb = load_workbook(workbook, read_only=True)
    missing = [sheet for sheet in EXPECTED_SHEETS if sheet not in wb.sheetnames]
    if missing:
        raise ValidationError(f"Workbook is missing sheets: {missing}")
    expected_sheet_rows = {
        "01_PQU_MASTER": len(pqu_records),
        "02_CURRENT_PQU": len(current_records),
        "03_UPCOMING_PQU": len(upcoming_records),
        "04_STATION_SCHEDULE": len(station_records),
        "05_REGION_MAPPING": len(region_records),
        "06_APPLICATION_BUILDS": len(version_records),
        "07_PLATFORM_BUILDS": len(version_records),
        "08_UEP_BUILDS": len(version_records),
        "10_CHANGE_HISTORY": len(change_records),
        "13_DATA_QUALITY": len(quality_records),
        "16_INSIGHTS": len(insight_records),
        "17_KEY_DATES": len(event_records),
        **{sourced.sheet: len(sourced_records[sourced.document]) for sourced in SOURCED_DATASETS},
    }
    for sheet, expected in expected_sheet_rows.items():
        actual = wb[sheet].max_row - 1
        if actual != expected:
            raise ValidationError(
                f"Workbook sheet {sheet} has {actual} data rows; expected {expected}"
            )
    wb.close()
    return {
        "status": "verified",
        "record_count": len(pqu_records),
        "latest_pqu_id": metadata.get("latest_pqu_id"),
        "semantic_hash": semantic_hash_from_document({"records": pqu_records}),
    }


def _verify_learn(document: dict[str, Any]) -> None:
    articles = document.get("articles")
    if not isinstance(articles, list) or document.get("count") != len(articles):
        raise ValidationError("learn.json count does not match its articles")
    keys = [article.get("key") for article in articles]
    if len(keys) != len(set(keys)):
        raise ValidationError("learn.json contains duplicate article keys")
    known = {spec.key for spec in SOURCE_SPECS}
    for article in articles:
        if article.get("key") not in known:
            raise ValidationError(f"learn.json article {article.get('key')} has no source")
        ids = [section.get("id") for section in article.get("sections", [])]
        if len(ids) != len(set(ids)):
            raise ValidationError(f"learn.json article {article.get('key')} repeats a section id")


def _verify_events(
    document: dict[str, Any],
    *,
    pqu_by_id: dict[str, dict[str, Any]],
    stations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Key dates must be unique, ordered, and agree with the trains and station rows."""
    records = _document_records(document, "events.json")
    if document.get("count") != len(records):
        raise ValidationError("events.json count does not match records")
    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        raise ValidationError("events.json repeats an event id")
    starts = [record["start_date"] for record in records]
    if starts != sorted(starts):
        raise ValidationError("events.json is not in date order")
    station_keys = {(row["pqu_id"], int(row["station"])) for row in stations}
    for record in records:
        if record["end_date"] < record["start_date"]:
            raise ValidationError(f"events.json event {record['id']} ends before it starts")
        pqu_id = record.get("pqu_id")
        if pqu_id is not None and pqu_id not in pqu_by_id:
            raise ValidationError(f"events.json event {record['id']} refers to an unknown PQU")
        if record["category"] == "station" and (pqu_id, record["station"]) not in station_keys:
            raise ValidationError(f"events.json event {record['id']} has no station row")
    return records


def _verify_insights(document: dict[str, Any]) -> list[dict[str, Any]]:
    """Cross-checks the calculated figures; returns their records."""
    records = _document_records(document, "insights.json")
    if document.get("count") != len(records):
        raise ValidationError("insights.json count does not match records")
    categories = {category.get("id") for category in document.get("categories", [])}
    metrics = {metric.get("id"): metric for metric in document.get("metrics", [])}
    if len(metrics) != len(document.get("metrics", [])):
        raise ValidationError("insights.json repeats a metric id")
    known_sources = {spec.key for spec in SOURCE_SPECS}
    for metric in metrics.values():
        if metric.get("category") not in categories:
            raise ValidationError(f"insights.json metric {metric.get('id')} has no category")
        if not set(metric.get("sources", [])) <= known_sources:
            raise ValidationError(f"insights.json metric {metric.get('id')} has an unknown source")
    ids = [record.get("id") for record in records]
    if len(ids) != len(set(ids)):
        raise ValidationError("insights.json repeats a record id")
    for record in records:
        metric = metrics.get(record.get("metric"))
        if metric is None:
            raise ValidationError(f"insights.json record {record.get('id')} has no metric")
        if record.get("statistic") != metric.get("statistic") or record.get("unit") != metric.get(
            "unit"
        ):
            raise ValidationError(
                f"insights.json record {record.get('id')} does not match its metric"
            )
    if not set(document.get("highlights", [])) <= set(ids):
        raise ValidationError("insights.json highlights an unknown record")
    return records


def _verify_sources(metadata: dict[str, Any], documents: dict[str, dict[str, Any]]) -> None:
    """Every source document must carry exactly the provenance recorded for its article."""
    sources = metadata.get("sources")
    if not isinstance(sources, dict) or "schedule" not in sources:
        raise ValidationError("metadata.json does not list its sources")
    schedule = sources["schedule"]
    if schedule.get("state") != "current" or schedule.get("source") != metadata.get("source"):
        raise ValidationError("metadata.json schedule source does not match its provenance")
    known = {spec.key for spec in SOURCE_SPECS}
    for key, entry in sources.items():
        if key not in known:
            raise ValidationError(f"metadata.json lists an unknown source {key!r}")
        has_source = isinstance(entry.get("source"), dict)
        if has_source != (entry.get("state") in ("current", "stale")):
            raise ValidationError(f"metadata.json source {key!r} state and provenance disagree")
    for name, key in SOURCE_DOCUMENTS.items():
        document = documents[name]
        entry = sources.get(key)
        if entry is None:
            raise ValidationError(f"{name} has no source entry in metadata.json")
        if document.get("state") != entry.get("state") or document.get("source") != entry.get(
            "source"
        ):
            raise ValidationError(f"Source provenance differs in {name}")


def semantic_hash_from_document(document: dict[str, Any]) -> str:
    import hashlib

    payload = json.dumps(
        document.get("records", []), sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def remove_site(paths: Paths) -> None:
    if paths.site_dir.exists():
        shutil.rmtree(paths.site_dir)
