# Data dictionary

Dates are ISO calendar dates (`2026-10-03`) exactly as Microsoft publishes them; they are never shifted between time zones. Timestamps are UTC (`2026-09-28T03:00:00Z`). `null` means Microsoft has not published the value (Microsoft's `N/A` is stored as `null`).

## Dataset envelope

JSON documents share this envelope where it applies:

| Field | Meaning |
|---|---|
| `dataset` | `d365-finops-pqu` |
| `schema_version` | Version of the JSON data contract (`1.1.0`) |
| `generated_at` | UTC time of the snapshot; every document of one build has the same value |
| `source` | Provenance of the article the document is built from |
| `count` | Number of records |
| `records` | The records |

`metadata.json` also carries `pipeline_revision`, the version of the normalization and generation logic.

Documents built from one optional article (`service-updates.json`, `maintenance-windows.json`) add `source_key` and `state`:

| State | Meaning |
|---|---|
| `current` | Read from the article at this run's commit |
| `stale` | The article could not be read or parsed; the last published copy is kept |
| `unavailable` | The article could not be read and there is no earlier copy; `records` is empty |
| `not_configured` | The article is not part of this run |

## Provenance (`source`)

| Field | Meaning |
|---|---|
| `publisher` | `Microsoft` |
| `repository`, `branch` | `MicrosoftDocs/dynamics-365-unified-operations-public`, `main` |
| `file_path` | Article path in that repository |
| `commit` | Commit the content was read at; it stays the same while the content is unchanged |
| `article_url` | The Microsoft Learn page |
| `raw_url` | The Markdown pinned to `commit` |
| `markdown_date` | Microsoft's `ms.date` front matter |
| `sha256` | SHA-256 of the downloaded Markdown |
| `retrieved_at` | When the content was first retrieved |

## PQU record (`pqu.json`, `current.json`, `upcoming.json`)

| Field | Type | Meaning |
|---|---|---|
| `pqu_id` | string | Stable ID such as `10.0.48-PQU-6` |
| `application_version` | string | Application version, such as `10.0.48` |
| `pqu_train` | string | Train label, such as `PQU-6` |
| `release_number` | integer | Numeric train number |
| `change_cutoff_date` | date or null | Microsoft change cutoff date |
| `train_start_date` | date or null | Train start date |
| `train_end_date` | date or null | Train end date |
| `status` | enum | `Completed`, `In-Progress`, `Not Started`, or `Canceled`, as published |
| `status_note` | string or null | Microsoft's footnote for a marked status, such as `Canceled*` |
| `application_build` | string or null | Application build when published |
| `platform_build` | string or null | Platform build when published |
| `uep_version` | string or null | Unified Environment Provisioning version when published |
| `station_schedule_available` | boolean | Whether a detailed station section is published |
| `station_schedule_new` | boolean | Whether Microsoft marks the station section `[NEW]` |
| `first_seen_at` | timestamp | When this dataset first published the train |
| `last_changed_at` | timestamp | Last detected change to the train or its station schedule |
| `source` | object | Provenance of the schedule article |

`metadata.json.latest_pqu_id` is the newest train Microsoft lists as `In-Progress`.

## Station record (`stations.json`)

One row per train and station, with `sandbox_start_date`, `sandbox_end_date`, `production_start_date`, and `production_end_date`. A detailed schedule contains stations 1 to 6; windows Microsoft lists as `N/A` (currently Station 1's production windows) are `null`.

## Region record (`regions.json`)

| Field | Meaning |
|---|---|
| `station`, `station_label` | The station |
| `region` | Azure region name as published, or the Station 1 opt-in description |
| `is_region` | `false` for the Station 1 description |
| `maintenance_geo` | Geography in `maintenance-windows.json` matched from the region name, or `null` |

`maintenance_geo` is calculated, not published by Microsoft: it is matched by name tokens, and sovereign clouds only match geographies with the same sovereign token. Regions left unmatched are reported in `quality-report.json`.

## Service update record (`service-updates.json`)

| Field | Meaning |
|---|---|
| `version` | Service update, such as `10.0.49` |
| `release_label` | Microsoft's release label, such as `CY26Q4`, or null |
| `is_major` | Whether Microsoft marks the release as major |
| `preview_date` | Preview availability |
| `preview_latest_update_date` | Latest update of the preview |
| `general_availability_date` | General availability |
| `first_autoupdate_date`, `second_autoupdate_date` | Autoupdate dates |
| `end_of_service_date` | End of service |

## Maintenance window record (`maintenance-windows.json`)

| Field | Meaning |
|---|---|
| `geo` | Geography as published |
| `start_time_utc` | Start time in UTC (`22:00`) |
| `days` | UTC weekdays, such as `["Friday", "Saturday"]` |
| `duration_hours` | Length in hours when Microsoft states it, else null |
| `duration_text` | Length as published, such as `Six hours` |

## Guidance (`learn.json`)

`articles` holds the text of each article: `key`, `title`, `url`, the provenance fields, and `sections`. Each section has `id`, `anchor`, `aliases`, `title`, `level`, `url` (the Learn section link), `text_sha256` (used to detect edits), and `blocks`. Block types are `paragraph`, `list`, `callout`, `quote`, `table`, and `dataset`, a placeholder where a table is published as data instead of text. Text runs can be `strong`, `em`, or `code` and can link to an https URL. `license` records the CC BY 4.0 terms, the attribution, and the changes made to the text.

## Key date record (`events.json`)

| Field | Meaning |
|---|---|
| `id` | `<kind>:<subject>`, such as `production_window:10.0.48-PQU-6:station-4`; stays the same when the date moves |
| `kind` | `change_cutoff`, `train_window`, `sandbox_window`, `production_window`, `preview`, `preview_latest_update`, `general_availability`, `autoupdate_first`, `autoupdate_second`, or `end_of_service` |
| `category` | `train`, `station`, or `service_update` |
| `title` | Readable title |
| `start_date`, `end_date` | Dates as published; `end_date` equals `start_date` for one-day events |
| `pqu_id`, `application_version`, `station` | What the event belongs to, when it applies |
| `status` | Microsoft's status of the train, for train and station events |
| `source_key`, `url` | The source article and the Learn section that publishes the date |
| `warnings` | Codes of source warnings about the dates behind the event |

## Calculated figure (`insights.json`)

Microsoft does not publish these figures. `metrics` describes each figure (`id`, `category`, `title`, `unit`, `statistic`, `sample_unit`, `sources`, `method`, and figure-wide `excluded`); `categories` and `highlights` group them for display.

| Field | Meaning |
|---|---|
| `id` | `<metric>:<group>`, such as `train-cadence:10.0.48` |
| `metric`, `group`, `label` | Figure and group (a version, a station, or `all`) |
| `value`, `unit`, `statistic` | The value, its unit, and whether it is a `median` or a `count` |
| `sample_size`, `min`, `max` | Size and range of the sample |
| `breakdown` | Counts per category for `count` figures, else null |
| `excluded` | Items left out and why, such as dates questioned by a source warning |
| `summary` | One-sentence description |

## Change record (`changes.json`)

| Field | Meaning |
|---|---|
| `change_id` | Stable identifier (feed entries use `urn:d365-pqu:change:<change_id>`) |
| `changed_at` | Time of the check that found the change |
| `entity` | `pqu`, `station`, `region`, `guidance`, `service_update`, or `maintenance_window` |
| `change_type` | `added`, `removed`, or `modified` |
| `pqu_id` | The train for `pqu` and `station` changes; `dataset` otherwise |
| `field` | What changed: a record field (`platform_build`), `station.<n>` or `station.<n>.<field>`, `region.<name>`, `<article>#<section>` for guidance, or `<version or geography>#<field>` |
| `old_value`, `new_value` | Values before and after (the whole record for additions and removals) |
| `source_commit` | Microsoft commit of the new content |

## Quality and health

`quality-report.json` lists non-fatal findings with `code`, `severity`, `message`, and optionally `pqu_id` and `field`. Severity is `warning` for values that look wrong or sources that could not be refreshed, and `info` for expected gaps, such as a sovereign cloud with no maintenance window in Microsoft's table. Fatal findings are never published; a run with a fatal finding publishes nothing.

`health.json` describes the latest check: `status` (`healthy`, `degraded` when there are warnings, or `failed`), `checked_at`, `checked_commit` (the commit examined), `content_commit` (the commit of the published content), `run_status` (`updated`, `unchanged`, `heartbeat`, or `failed`), `check_interval_minutes`, record counts, warning and error counts, and per-source `sources` state. The site publishes the health of the latest run when it matches the committed data, and otherwise the committed `data/health.json`; see [operations](operations.md).

## Files

| Path | Contents |
|---|---|
| `/api/index.json` | Every published file, with its CSV and JSON Schema |
| `/api/pqu.json`, `/api/pqu.csv` | All trains |
| `/api/current.json`, `/api/upcoming.json` | `In-Progress` and `Not Started` trains |
| `/api/stations.json` | Station windows |
| `/api/regions.json` | Station-to-region mapping with matched maintenance geography |
| `/api/versions.json` | Application, platform, and UEP builds per train |
| `/api/service-updates.json` | Service update lifecycle dates |
| `/api/maintenance-windows.json` | Planned maintenance windows by geography |
| `/api/events.json` | Key dates |
| `/api/insights.json` | Calculated figures |
| `/api/learn.json` | Guidance text |
| `/api/changes.json` | Change history |
| `/api/quality-report.json` | Quality findings |
| `/api/metadata.json` | Counts, source states, and links |
| `/api/health.json` | The latest check |
| `/feed.xml` | Atom feed of the newest 100 changes |
| `/calendar/station-1.ics` … `station-6.ics` | Sandbox and production windows per station, as all-day events |
| `/calendar/milestones.ics` | Change cutoffs and service update milestones |
| `/llms.txt` | Summary of the files for language-model tools |
| `/schemas/` | JSON Schema documents |
| `/downloads/D365-PQU-Tracker.xlsx` | Excel workbook |

Most JSON documents have a CSV with the same records under the same name.
