from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypedDict


class SourceProvenance(TypedDict):
    publisher: str
    repository: str
    branch: str
    file_path: str
    commit: str
    article_url: str
    raw_url: str
    markdown_date: str | None
    sha256: str
    retrieved_at: str


class RecordSource(TypedDict):
    publisher: str
    repository: str
    commit: str
    url: str
    raw_url: str


class PquRecord(TypedDict):
    pqu_id: str
    application_version: str
    pqu_train: str
    release_number: int
    change_cutoff_date: str | None
    train_start_date: str | None
    train_end_date: str | None
    status: str
    application_build: str | None
    platform_build: str | None
    uep_version: str | None
    station_schedule_available: bool
    first_seen_at: str
    last_changed_at: str
    source: RecordSource


class StationRecord(TypedDict):
    pqu_id: str
    application_version: str
    pqu_train: str
    release_number: int
    station: int
    station_label: str
    sandbox_start_date: str | None
    sandbox_end_date: str | None
    production_start_date: str | None
    production_end_date: str | None
    source: RecordSource


class RegionRecord(TypedDict):
    station: int
    station_label: str
    region: str
    is_region: bool


class VersionRecord(TypedDict):
    pqu_id: str
    application_version: str
    pqu_train: str
    release_number: int
    status: str
    application_build: str | None
    platform_build: str | None
    uep_version: str | None
    change_cutoff_date: str | None
    train_start_date: str | None
    train_end_date: str | None


class ChangeRecord(TypedDict):
    change_id: str
    changed_at: str
    pqu_id: str
    entity: str
    change_type: str
    field: str | None
    old_value: Any
    new_value: Any
    source_commit: str


class QualityItem(TypedDict):
    code: str
    severity: str
    message: str
    pqu_id: str | None
    field: str | None


@dataclass(frozen=True)
class SourceDocument:
    markdown: str
    source_commit: str
    article_url: str
    raw_url: str
    markdown_date: str | None
    retrieved_at: datetime
    sha256: str
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedTrainRow:
    release_train: str
    change_cutoff: str
    train_duration: str
    status: str
    application_version: str
    platform_version: str


@dataclass(frozen=True)
class ParsedStationRow:
    station: str
    sandbox_schedule: str
    production_schedule: str


@dataclass(frozen=True)
class ParsedStationSchedule:
    release_train: str
    application_version: str
    application_build: str
    platform_build: str
    uep_version: str | None
    rows: tuple[ParsedStationRow, ...]


@dataclass(frozen=True)
class ParsedRegionRow:
    station: str
    regions: str


@dataclass
class ParsedSource:
    train_rows: list[ParsedTrainRow] = field(default_factory=list)
    region_rows: list[ParsedRegionRow] = field(default_factory=list)
    station_schedules: list[ParsedStationSchedule] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class NormalizedDataset:
    source: SourceProvenance
    records: list[PquRecord]
    stations: list[StationRecord]
    regions: list[RegionRecord]
    versions: list[VersionRecord]
    changes: list[ChangeRecord]
    quality: list[QualityItem]
    observed_at: datetime
    generated_at: datetime
    previous_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class SyncResult:
    changed: bool
    status: str
    source_hash: str
    source_commit: str
    record_count: int
    current_count: int
    upcoming_count: int
    warning_count: int
    error_count: int
    data_dir: str
    workbook_path: str
    site_dir: str
