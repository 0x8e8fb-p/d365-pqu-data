# Data dictionary

## Dataset envelope

All JSON endpoints use the same envelope where applicable:

| Field | Meaning |
|---|---|
| `dataset` | `d365-finops-pqu` |
| `schema_version` | Version of the JSON data contract |
| `pipeline_revision` | Version of the normalization and generation logic, present in metadata |
| `generated_at` | UTC timestamp for the generated snapshot |
| `source` | Microsoft source provenance object |
| `count` | Number of records in the endpoint |
| `records` | Normalized records |

## PQU record

| Field | Type | Meaning |
|---|---|---|
| `pqu_id` | string | Stable ID such as `10.0.48-PQU-6` |
| `application_version` | string | Application train version, such as `10.0.48` |
| `pqu_train` | string | Train label, such as `PQU-6` |
| `release_number` | integer | Numeric train number |
| `change_cutoff_date` | date or null | Microsoft change cutoff date |
| `train_start_date` | date or null | Train start date |
| `train_end_date` | date or null | Train end date |
| `status` | enum | `Completed`, `In-Progress`, `Not Started`, or `Canceled` |
| `application_build` | string or null | Application build when published |
| `platform_build` | string or null | Platform build when published |
| `uep_version` | string or null | Unified Environment Provisioning version when published |
| `station_schedule_available` | boolean | Whether a detailed station section was published |
| `first_seen_at` | timestamp | First publication time for the PQU ID |
| `last_changed_at` | timestamp | Last detected normalized change |
| `source` | object | Per-record source commit and URLs |

## Station record

Station records are one row per PQU and station. They contain separate sandbox and production start/end dates. `N/A` is represented as `null`. Each detailed schedule must contain stations 1 through 6.

## Region record

Region records are one row per station and region. `is_region` is `true` for ordinary regions and `false` for the Station 1 opt-in description.

## Change record

Change records identify the entity (`pqu`, `station`, or `region`) and field changed. `pqu_id` is the affected PQU ID for PQU/station changes and `dataset` for region changes. A change stores old and new values plus the source commit.

## Quality and health

`quality-report.json` contains non-fatal source observations and validation findings. Fatal findings are never published. `health.json` reports the last successful check, source identity, validation state, counts, and current warning count. A non-empty warning list is represented as `degraded` health while the last valid dataset remains available.

## Endpoints

| Path | Contents |
|---|---|
| `/api/pqu.json` | All normalized PQU records |
| `/api/pqu.csv` | All normalized PQU records |
| `/api/current.json` | All `In-Progress` records |
| `/api/upcoming.json` | All `Not Started` records |
| `/api/stations.json` | Station schedule windows |
| `/api/regions.json` | Station-to-region mapping |
| `/api/versions.json` | Application, platform, and UEP versions |
| `/api/changes.json` | Field-level change history |
| `/api/quality-report.json` | Quality findings |
| `/api/metadata.json` | Dataset counts and public links |
| `/api/health.json` | Last successful synchronization state |
| `/schemas/` | JSON Schema documents |
| `/downloads/D365-PQU-Tracker.xlsx` | Generated Excel workbook |
