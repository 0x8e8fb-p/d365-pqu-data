from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DATASET_NAME = "d365-finops-pqu"
SCHEMA_VERSION = "1.0.0"
PIPELINE_REVISION = "1.0.0"
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

UPDATE_CRON = "17 */6 * * *"
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
