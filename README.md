# D365 Finance & Operations PQU Dataset

A public, version-controlled dataset for Microsoft Dynamics 365 Finance and Operations proactive quality updates (PQUs).

The project synchronizes the authoritative Microsoft documentation, normalizes it into stable machine-readable records, and publishes three useful views from the same validated source:

- JSON and CSV for AI agents, Python, Power BI, and extractors.
- A detailed Excel workbook for human and D365 team use.
- A static GitHub Pages dashboard and API index for discovery.

## Public links

- Dashboard: <https://0x8e8fb-p.github.io/d365-pqu-data/>
- JSON: <https://0x8e8fb-p.github.io/d365-pqu-data/api/pqu.json>
- CSV: <https://0x8e8fb-p.github.io/d365-pqu-data/api/pqu.csv>
- Current PQU: <https://0x8e8fb-p.github.io/d365-pqu-data/api/current.json>
- Upcoming PQU: <https://0x8e8fb-p.github.io/d365-pqu-data/api/upcoming.json>
- Station schedules: <https://0x8e8fb-p.github.io/d365-pqu-data/api/stations.json>
- Region mapping: <https://0x8e8fb-p.github.io/d365-pqu-data/api/regions.json>
- Versions: <https://0x8e8fb-p.github.io/d365-pqu-data/api/versions.json>
- Change history: <https://0x8e8fb-p.github.io/d365-pqu-data/api/changes.json>
- API index: <https://0x8e8fb-p.github.io/d365-pqu-data/api/index.json>
- Excel tracker: <https://0x8e8fb-p.github.io/d365-pqu-data/downloads/D365-PQU-Tracker.xlsx>
- Source repository: <https://github.com/0x8e8fb-p/d365-pqu-data>

Raw GitHub URLs are also available for integrations that prefer raw content:

- <https://raw.githubusercontent.com/0x8e8fb-p/d365-pqu-data/main/data/pqu.json>
- <https://raw.githubusercontent.com/0x8e8fb-p/d365-pqu-data/main/data/pqu.csv>
- <https://raw.githubusercontent.com/0x8e8fb-p/d365-pqu-data/main/excel/D365-PQU-Tracker.xlsx>

## What is normalized

The canonical `pqu.json` dataset uses stable identifiers such as `10.0.48-PQU-6` and includes:

- Application version, PQU train, release number, status, cutoff, train start, and train end dates.
- Application build, platform build, and UEP version when Microsoft has published them.
- Station-schedule availability and source provenance.
- First-seen, last-changed, Microsoft source revision, raw source URL, retrieval time, and SHA-256 hash.

`current.json` contains every train whose status is `In-Progress`. `metadata.json.latest_pqu_id` identifies the newest active train. `upcoming.json` contains every `Not Started` train.

## Excel workbook

`excel/D365-PQU-Tracker.xlsx` is generated as part of the same update. It contains:

1. `00_README`
2. `01_PQU_MASTER`
3. `02_CURRENT_PQU`
4. `03_UPCOMING_PQU`
5. `04_STATION_SCHEDULE`
6. `05_REGION_MAPPING`
7. `06_APPLICATION_BUILDS`
8. `07_PLATFORM_BUILDS`
9. `08_UEP_BUILDS`
10. `09_STATUS_HISTORY`
11. `10_CHANGE_HISTORY`
12. `11_SOURCE_METADATA`
13. `12_SYNC_HEALTH`
14. `13_DATA_QUALITY`

The workbook has filters, frozen headers, real Excel date values, hyperlinks, status formatting, and a status-distribution chart. It contains no macros or external links.

## Automation

`update-pqu.yml` runs every six hours and can also be started manually from the GitHub Actions tab. The workflow:

1. Resolves the current Microsoft source commit with `git ls-remote`.
2. Downloads the Markdown at that exact commit.
3. Parses and validates the source.
4. Compares source identity and normalized content.
5. Generates JSON, CSV, the workbook, history, quality data, and the Pages site in staging directories.
6. Verifies the complete artifact set before committing anything.
7. Commits only when the dataset or monthly health heartbeat changes.
8. Deploys the verified site to GitHub Pages.

A failed parse or validation never replaces the last good published dataset. The workflow creates or updates one GitHub issue labeled `automation` and closes it after recovery.

The repository has no cloud database, paid API, Microsoft Graph credentials, SharePoint dependency, or secret. The only write credential is the workflow's built-in GitHub token.

## Local development

Python 3.11 or newer is supported. The project is tested with Python 3.12.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements/runtime.lock
.venv/bin/pip install -r requirements/dev.lock
.venv/bin/pip install -e . --no-deps
```

Run the complete local quality suite:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/python -m pytest
.venv/bin/python -m d365_pqu verify
```

Fetch and generate the current dataset:

```bash
.venv/bin/python -m d365_pqu sync --build-site
```

The generated `data/`, `excel/`, and `build/` content is machine-generated. Do not edit it manually; update the parser, schemas, or generator instead.

## Source and limitations

The authoritative input is the Microsoft Learn article [Release schedule for proactive quality updates](https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/quality-updates-schedule), maintained in the [MicrosoftDocs GitHub repository](https://github.com/MicrosoftDocs/dynamics-365-unified-operations-public).

Microsoft publishes detailed train and station information shortly before a train starts. Schedules, builds, and status can change. A published dataset is not a guarantee for a particular Dynamics 365 environment; use Microsoft Lifecycle Services notifications and environment-specific information for rollout decisions.

This project is independent and is not affiliated with or endorsed by Microsoft. See [NOTICE.md](NOTICE.md) and [LICENSE](LICENSE).

## Documentation

- [Architecture](docs/architecture.md)
- [Data dictionary](docs/data-dictionary.md)
- [Operations and recovery](docs/operations.md)
- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
