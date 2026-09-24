# Operations and recovery

## Normal schedule

The `Update D365 PQU dataset` workflow runs at minute 17 every six hours and can be started manually with **Run workflow**. The minute is intentionally off the top of the hour to reduce scheduler contention.

A normal run checks Microsoft's source, validates it, and deploys the static site. It creates a data commit only when the source identity or normalized dataset changes. A health-only commit is allowed once every 30 days.

## Failure behavior

If source retrieval, parsing, schema validation, cross-document checks, workbook generation, or Pages deployment fails:

- The last valid `data/` and `excel/` directories remain intact.
- The workflow run is marked failed.
- A sanitized diagnostic appears in the run log.
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

## Local verification

```bash
.venv/bin/python -m d365_pqu verify
.venv/bin/python -m d365_pqu build-site
```

`verify` checks every published JSON document, CSV header and row count, cross-document record relationships, source provenance, and workbook sheet row counts.

## Operational limits

- GitHub Actions schedules are best-effort and can be delayed during GitHub incidents.
- The workflow checks every six hours; it is not a real-time SLA.
- Microsoft can change or temporarily restructure its documentation. Fatal structural changes require a reviewed parser update.
- Environment-specific rollout timing still comes from Microsoft Lifecycle Services notifications.
