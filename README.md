# D365 Finance & Operations PQU Dataset

A public, version-controlled dataset and dashboard for Microsoft Dynamics 365 Finance and Operations proactive quality updates (PQUs).

The project reads five Microsoft Learn articles at one pinned commit of Microsoft's documentation repository, normalizes them into stable machine-readable records, and publishes everything from the same validated data:

- A static dashboard: today's trains, your region's update windows, a timeline, service update lifecycles, short explanations, and a change log.
- JSON and CSV for AI agents, Python, Power BI, and other tools, each JSON file with a JSON Schema.
- An Excel workbook for D365 teams.
- An Atom feed of detected changes, iCalendar subscriptions for station windows and key dates, and `llms.txt`.

## Public links

- Dashboard: <https://0x8e8fb-p.github.io/d365-pqu-data/>
- Data & API page (every file, its schema, and its Microsoft source): <https://0x8e8fb-p.github.io/d365-pqu-data/#/data>
- API index: <https://0x8e8fb-p.github.io/d365-pqu-data/api/index.json>
- Trains: [pqu.json](https://0x8e8fb-p.github.io/d365-pqu-data/api/pqu.json), [pqu.csv](https://0x8e8fb-p.github.io/d365-pqu-data/api/pqu.csv), [current.json](https://0x8e8fb-p.github.io/d365-pqu-data/api/current.json), [upcoming.json](https://0x8e8fb-p.github.io/d365-pqu-data/api/upcoming.json)
- Station schedules and regions: [stations.json](https://0x8e8fb-p.github.io/d365-pqu-data/api/stations.json), [regions.json](https://0x8e8fb-p.github.io/d365-pqu-data/api/regions.json)
- Service updates and maintenance windows: [service-updates.json](https://0x8e8fb-p.github.io/d365-pqu-data/api/service-updates.json), [maintenance-windows.json](https://0x8e8fb-p.github.io/d365-pqu-data/api/maintenance-windows.json)
- Key dates and calculated figures: [events.json](https://0x8e8fb-p.github.io/d365-pqu-data/api/events.json), [insights.json](https://0x8e8fb-p.github.io/d365-pqu-data/api/insights.json)
- Microsoft's guidance text: [learn.json](https://0x8e8fb-p.github.io/d365-pqu-data/api/learn.json)
- Changes: [changes.json](https://0x8e8fb-p.github.io/d365-pqu-data/api/changes.json), [Atom feed](https://0x8e8fb-p.github.io/d365-pqu-data/feed.xml)
- Calendars: `https://0x8e8fb-p.github.io/d365-pqu-data/calendar/station-1.ics` to `station-6.ics`, and [milestones.ics](https://0x8e8fb-p.github.io/d365-pqu-data/calendar/milestones.ics) (change cutoffs and service update dates)
- Summary for language-model tools: [llms.txt](https://0x8e8fb-p.github.io/d365-pqu-data/llms.txt)
- Excel tracker: <https://0x8e8fb-p.github.io/d365-pqu-data/downloads/D365-PQU-Tracker.xlsx>
- Source repository: <https://github.com/0x8e8fb-p/d365-pqu-data>

Raw GitHub URLs are also available for integrations that prefer the committed copy:

- <https://raw.githubusercontent.com/0x8e8fb-p/d365-pqu-data/main/data/pqu.json>
- <https://raw.githubusercontent.com/0x8e8fb-p/d365-pqu-data/main/data/pqu.csv>
- <https://raw.githubusercontent.com/0x8e8fb-p/d365-pqu-data/main/excel/D365-PQU-Tracker.xlsx>

## The dashboard

- **Overview** (landing page): trains Microsoft lists as In-Progress with their calculated phase, your region's next production weekend and dark hours, the next change cutoffs, the versions in service, and the next 14 days.
- **My region**: your station, the other regions on it, Microsoft's planned maintenance window for your geography, and each sandbox and production window paired with the dark hours of that weekend, with calendar subscriptions.
- **Trains**: a filterable table or a timeline. Each train has its own page (`#/train/10.0.48-PQU-6`) with its builds, a station rollout chart, its recorded changes, and links to the Microsoft source.
- **Versions**: each service update's lifecycle phase today, and *Find my build*, which shows which train published an application or platform build and how many newer builds exist.
- **Learn**: Microsoft's PQU overview, how a rollout moves through the stations, maintenance windows in your time zone, the PQU FAQ with search, and figures calculated from the published dates.
- **Changes**: every change detected in Microsoft's articles, grouped by day, with an Atom feed.
- **Data & API** (footer): every published file with its schema and the Microsoft commit each article was read at.

Every page has a shareable address, works in dark and light themes, and is built from the same published files, with no third-party scripts or services.

## Published values and calculated values

Dates, statuses, builds, schedules, maintenance windows, and guidance text are Microsoft's, shown as published. When Microsoft's article contradicts itself, the value is still shown as published, with a source warning.

Some values are calculated from Microsoft's data, and the dashboard labels them as calculated: phases and countdowns, day counts, build positions, the geography each Azure region's maintenance window is matched to, the dark hours paired with a production weekend, and the figures in `insights.json`. Calculations about "today" use the viewer's date and time zone, which can be changed in the header. Calendar dates are never shifted between time zones; times such as checks and maintenance windows are shown in the chosen zone.

An open dashboard checks for newly published data at the check interval, recalculates at midnight and when a maintenance window starts or ends, and keeps the reader's place when it redraws.

## What is normalized

- **Trains** (`pqu.json`): stable identifiers such as `10.0.48-PQU-6`; application version, train, release number, status, change cutoff, train start and end dates; application build, platform build, and UEP version when Microsoft has published them; whether a detailed station schedule is published and whether Microsoft marks it new; Microsoft's status footnote; first-seen and last-changed times; and the source commit, raw URL, and SHA-256 hash.
- **Station schedules** (`stations.json`): sandbox and production windows per train and station.
- **Regions** (`regions.json`): the station of each Azure region and the maintenance-window geography matched from its name.
- **Service updates** (`service-updates.json`): preview, general availability, autoupdate, and end-of-service dates per version.
- **Maintenance windows** (`maintenance-windows.json`): each geography's weekly dark-hours window in UTC.
- **Guidance** (`learn.json`): the articles' text as structured sections, with anchors and change hashes.
- **Key dates** (`events.json`) and **calculated figures** (`insights.json`), built from the records above.
- **Change history** (`changes.json`): every field-level change between published copies.

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
15. `14_SERVICE_UPDATES`
16. `15_MAINTENANCE_WINDOWS`
17. `16_INSIGHTS`
18. `17_KEY_DATES`

The workbook has filters, frozen headers, real Excel date values, hyperlinks, status formatting, and a status-distribution chart. It contains no macros or external links.

## Automation

`update-pqu.yml` runs every hour at minute 17 and can also be started manually from the GitHub Actions tab. The workflow:

1. Resolves the current Microsoft source commit once with `git ls-remote`.
2. Downloads the five articles at that exact commit. The release schedule is required; if another article cannot be read, the last published copy is kept and marked stale, and a source warning says so.
3. Parses and validates the sources.
4. Compares each article's content (SHA-256) and the pipeline revision with the published data. A new upstream commit that leaves the articles unchanged is not a data change.
5. Generates JSON, CSV, the workbook, history, and quality data in staging directories and verifies the complete set before committing anything.
6. Commits only when the data or the monthly health heartbeat changes.
7. Builds the site (dashboard, API, feed, calendars, `llms.txt`) from the committed data and deploys it to GitHub Pages.

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
.venv/bin/python -m playwright install chromium
```

The JavaScript unit tests need Node.js, and the browser tests need Playwright's Chromium. Without them those tests are skipped; CI sets `REQUIRE_NODE=1` and `REQUIRE_E2E=1` so they always run there.

Run the complete local quality suite:

```bash
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/mypy
.venv/bin/python -m pytest
.venv/bin/python -m d365_pqu verify
```

Fetch and generate the current dataset, then preview the site at `http://127.0.0.1:8000/`:

```bash
.venv/bin/python -m d365_pqu sync --build-site
.venv/bin/python -m d365_pqu serve
```

The generated `data/`, `excel/`, and `build/` content is machine-generated. Do not edit it manually; update the parser, schemas, or generator instead.

## Sources and limitations

The inputs are these Microsoft Learn articles, maintained in the [MicrosoftDocs GitHub repository](https://github.com/MicrosoftDocs/dynamics-365-unified-operations-public):

- [Release schedule for proactive quality updates](https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/quality-updates-schedule) (required)
- [Service update availability](https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/public-preview-releases)
- [Maintenance in self-service environments FAQ](https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/deployment/plannedmaintenance-selfservice)
- [Proactive quality updates overview](https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/quality-updates)
- [Proactive quality updates FAQ](https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/quality-updates-faq)

Microsoft publishes detailed train and station information shortly before a train starts. Schedules, builds, and status can change. A published dataset is not a guarantee for a particular Dynamics 365 environment; use Microsoft Lifecycle Services notifications and environment-specific information for rollout decisions.

Microsoft's text is reused under CC BY 4.0 with attribution. This project is independent and is not affiliated with or endorsed by Microsoft. See [NOTICE.md](NOTICE.md) and [LICENSE](LICENSE).

## Documentation

- [Architecture](docs/architecture.md)
- [Data dictionary](docs/data-dictionary.md)
- [Operations and recovery](docs/operations.md)
- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
