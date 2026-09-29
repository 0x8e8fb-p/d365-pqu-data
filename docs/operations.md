# Operations and recovery

## Normal schedule

The `Update D365 PQU dataset` workflow runs at minute 17 of every hour and can be started manually with **Run workflow**. The minute is intentionally off the top of the hour to reduce scheduler contention. The schedule lives in `.github/workflows/update-pqu.yml` and must match `UPDATE_CRON` and `CHECK_INTERVAL_MINUTES` in `src/d365_pqu/config.py`; `tests/test_workflows.py` fails if they drift apart.

Every run:

1. Resolves the current MicrosoftDocs commit once and downloads the five source articles at that commit.
2. Parses and validates them. The release schedule is required; an optional article that cannot be read or parsed keeps its last published copy (state `stale`) or is left out (state `unavailable`), with a source warning.
3. Compares the **content** (SHA-256 and state of each article) and the pipeline revision with the published dataset. A new upstream commit that leaves the articles unchanged is not a data change.
4. Rewrites `data/` and `excel/` only when the content or pipeline revision changed, or when the monthly heartbeat is due.
5. Records the check in the untracked `build/run-health.json`.
6. Commits changed data, verifies the committed artifacts, rebuilds the site (dashboard, API, feed, calendars, `llms.txt`), and deploys GitHub Pages.

## Two health documents

| File | Written | Describes |
|---|---|---|
| `build/run-health.json` → published as `/api/health.json` | Every successful run (not committed) | This check: `checked_at`, `checked_commit` (commit examined), `content_commit` (commit of the published content), `run_status` (`updated`, `unchanged`, `heartbeat`), and per-source state |
| `data/health.json` (committed) | When the data changes, and by the monthly heartbeat | The last data change |

`build-site` publishes the run health only when it validates against `health.schema.json`, describes the same content commit and hash as the committed metadata, and is not older than the committed health. Otherwise it publishes `data/health.json`, and the command output reports `"health_source": "data"`.

Published provenance is pinned to the commit where the published content was retrieved. When a later commit leaves the content unchanged, `content_commit` stays the same while `checked_commit` moves forward.

The data status in the dashboard header reads `/api/health.json`. It shows **Up to date** after a recent check, **N source warnings** when the source has non-fatal warnings, **Stale** when no check succeeded within three check intervals, **Last check failed** when the published health records a failure, and **Unavailable** when the dataset cannot be loaded.

An open dashboard fetches `/api/metadata.json` again at the check interval while the page is visible. When `generated_at` has changed, it reloads the documents it uses and redraws in place; nothing else is re-downloaded when the data is unchanged.

## Optional sources

If an optional article (service updates, maintenance, PQU overview, or FAQ) cannot be read or parsed, the run still succeeds. The article's data and text stay at the last published copy (state `stale`), or are left out when there is none (state `unavailable`), and a `source-stale` or `source-unavailable` warning appears in the quality report and the dashboard's status panel. The state returns to `current` on the first run that reads the article again. A lasting `stale` state usually means Microsoft moved or restructured the article: check the path in `config.SOURCE_SPECS` and the parser tests.

## Failure behavior

If source retrieval, parsing, schema validation, cross-document checks, workbook generation, or Pages deployment fails:

- The last valid `data/` and `excel/` directories remain intact.
- `build/run-health.json` records the failed check (`status: failed`, the stage that failed, and a short error message) for local diagnosis.
- The workflow run is marked failed and nothing is deployed, so the site keeps its last successful health. After three missed intervals the dashboard shows **Stale**.
- One issue labeled `automation` is created or updated.
- The next scheduled run retries automatically.
- A successful run comments on and closes the managed issue.

Do not manually edit generated files to repair a parser failure. Update the parser or validation code, run the tests, and let the workflow publish a new candidate.

## Manual recovery

1. Open the repository's **Actions** tab.
2. Open the latest `Update D365 PQU dataset` run.
3. Read the first failing step and the issue body.
4. If the source structure changed, update parser tests and code.
5. Run the local quality suite.
6. Use **Run workflow** on `main`.
7. Confirm the new commit, Pages deployment, and endpoint responses.

If scheduled workflows are disabled after a long period of inactivity, re-enable them in **Actions** and run the workflow manually. The monthly health heartbeat normally prevents this GitHub inactivity condition.

## Pages setup

Pages is deployed by the official GitHub Pages Actions from the verified `build/site` artifact. The public site is static and has no database or server-side write path. The source repository remains the canonical copy.

The published site contains the dashboard, `api/`, `schemas/`, `downloads/`, `feed.xml`, `calendar/*.ics`, `llms.txt`, and `404.html`. GitHub Pages serves `404.html` for every missing path, which is why that page uses paths from the site root (`/d365-pqu-data/…`); if the repository or Pages address changes, update `DEFAULT_REPO_SLUG` in `config.py` so these paths, the feed, and the calendars follow.

Both HTML pages carry a Content-Security-Policy that allows only the site's own files and the SHA-256 of the inline theme script, computed at build time. Changing that script needs no manual hash update; adding a script, style, or connection to another origin would be blocked by the policy.

## Local verification

```bash
.venv/bin/python -m d365_pqu sync --build-site
.venv/bin/python -m d365_pqu verify
.venv/bin/python -m d365_pqu serve
```

`verify` checks every published JSON document, CSV header and row count, cross-document record relationships, source provenance, and workbook sheet row counts. `serve` previews `build/site` at `http://127.0.0.1:8000/`; it binds to the loopback interface only and has no authentication, so it is for local use only.

To rebuild the dataset from local copies of the articles (for example to test a parser change against a saved copy), name the files like their repository files and pass the folder:

```bash
.venv/bin/python -m d365_pqu sync --source-dir path/to/articles --build-site
```

`sync --check` fetches and validates the live sources without writing anything.

## Operational limits

- GitHub Actions schedules are best-effort and can be delayed during GitHub incidents.
- The workflow checks every hour; it is not a real-time SLA.
- Microsoft can change or temporarily restructure its documentation. Fatal structural changes require a reviewed parser update.
- Environment-specific rollout timing still comes from Microsoft Lifecycle Services notifications.
