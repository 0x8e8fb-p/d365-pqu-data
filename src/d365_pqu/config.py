from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DATASET_NAME = "d365-finops-pqu"
SCHEMA_VERSION = "1.1.0"
PIPELINE_REVISION = "2.0.0"
DEFAULT_REPO_SLUG = "0x8e8fb-p/d365-pqu-data"
DEFAULT_BRANCH = "main"
SOURCE_BRANCH = "main"
SOURCE_REPO = "MicrosoftDocs/dynamics-365-unified-operations-public"
SOURCE_FILE_PATH = "articles/fin-ops-core/dev-itpro/get-started/quality-updates-schedule.md"
SOURCE_ARTICLE_URL = (
    "https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/"
    "get-started/quality-updates-schedule"
)
SOURCE_REPO_URL = f"https://github.com/{SOURCE_REPO}"
SOURCE_BRANCH_URL = f"{SOURCE_REPO_URL}/blob/{SOURCE_BRANCH}/{SOURCE_FILE_PATH}"
SOURCE_RAW_URL = (
    f"https://raw.githubusercontent.com/{SOURCE_REPO}/{SOURCE_BRANCH}/{SOURCE_FILE_PATH}"
)
SOURCE_RAW_TEMPLATE = (
    f"https://raw.githubusercontent.com/{SOURCE_REPO}/{{commit}}/{SOURCE_FILE_PATH}"
)
LEARN_ARTICLE_BASE = "https://learn.microsoft.com/en-us/dynamics365/"


@dataclass(frozen=True)
class SourceSpec:
    """One Microsoft Learn article read from the MicrosoftDocs repository at a pinned commit."""

    key: str
    file_path: str
    label: str
    required: bool = False

    @property
    def article_url(self) -> str:
        path = self.file_path.removeprefix("articles/").removesuffix(".md")
        return LEARN_ARTICLE_BASE + path

    @property
    def file_name(self) -> str:
        return self.file_path.rsplit("/", 1)[-1]


SCHEDULE_SPEC = SourceSpec(
    key="schedule",
    file_path=SOURCE_FILE_PATH,
    label="Release schedule for proactive quality updates",
    required=True,
)
SERVICE_UPDATES_SPEC = SourceSpec(
    key="service_updates",
    file_path="articles/fin-ops-core/dev-itpro/get-started/public-preview-releases.md",
    label="Service update availability",
)
MAINTENANCE_SPEC = SourceSpec(
    key="maintenance",
    file_path="articles/fin-ops-core/dev-itpro/deployment/plannedmaintenance-selfservice.md",
    label="Maintenance in self-service environments FAQ",
)
PQU_OVERVIEW_SPEC = SourceSpec(
    key="pqu_overview",
    file_path="articles/fin-ops-core/dev-itpro/get-started/quality-updates.md",
    label="Proactive quality updates overview",
)
PQU_FAQ_SPEC = SourceSpec(
    key="pqu_faq",
    file_path="articles/fin-ops-core/dev-itpro/get-started/quality-updates-faq.md",
    label="Proactive quality updates FAQ",
)
SOURCE_SPECS = (
    SCHEDULE_SPEC,
    SERVICE_UPDATES_SPEC,
    MAINTENANCE_SPEC,
    PQU_OVERVIEW_SPEC,
    PQU_FAQ_SPEC,
)
SOURCE_SPECS_BY_KEY = {spec.key: spec for spec in SOURCE_SPECS}

# Hourly at minute 17 (off the top of the hour to reduce scheduler contention). The interval must
# match the cron schedule in .github/workflows/update-pqu.yml; a test enforces both. GitHub skips
# most of these scheduled runs, so update-timer.yml keeps the hour (see docs/operations.md).
UPDATE_CRON = "17 * * * *"
CHECK_INTERVAL_MINUTES = 60
HEARTBEAT_DAYS = 30
ALLOWED_STATUSES = ("Completed", "In-Progress", "Not Started", "Canceled")
ALLOWED_STATIONS = tuple(range(1, 7))
MAX_SOURCE_BYTES = 5 * 1024 * 1024

PAGES_BASE_URL = (
    f"https://{DEFAULT_REPO_SLUG.split('/')[0]}.github.io/{DEFAULT_REPO_SLUG.split('/')[1]}"
)
RAW_BASE_URL = f"https://raw.githubusercontent.com/{DEFAULT_REPO_SLUG}/{DEFAULT_BRANCH}"


@dataclass(frozen=True)
class Paths:
    root: Path
    data_dir: Path
    excel_dir: Path
    schema_dir: Path
    site_dir: Path
    tests_dir: Path

    @property
    def workbook_path(self) -> Path:
        return self.excel_dir / "D365-PQU-Tracker.xlsx"

    @property
    def pqu_path(self) -> Path:
        return self.data_dir / "pqu.json"

    @property
    def metadata_path(self) -> Path:
        return self.data_dir / "metadata.json"

    @property
    def health_path(self) -> Path:
        return self.data_dir / "health.json"

    @property
    def run_health_path(self) -> Path:
        """Untracked health of the latest check, published by build-site as api/health.json."""
        return self.site_dir.parent / "run-health.json"

    @classmethod
    def from_root(cls, root: Path) -> Paths:
        root = root.resolve()
        return cls(
            root=root,
            data_dir=root / "data",
            excel_dir=root / "excel",
            schema_dir=root / "schema",
            site_dir=root / "build" / "site",
            tests_dir=root / "tests",
        )
