# Architecture

## Trust boundary

```text
MicrosoftDocs GitHub
        │ exact commit + Markdown
        ▼
GitHub Actions (Python)
        │ parse → normalize → validate → diff
        ▼
Canonical JSON/CSV ──► XLSX generator
        │                    │
        ├────────────────────┴──────────────► GitHub Pages API/dashboard
        │
        └──────────────────────────────────► versioned repository history
```

The public repository is the canonical published dataset. JSON is the canonical normalized representation. CSV, XLSX, and the dashboard are generated views.

## Update flow

1. Resolve the source branch head with `git ls-remote`.
2. Fetch Markdown from the resolved commit, not from a moving `main` URL.
3. Parse required table headings and rows.
4. Normalize dates, builds, statuses, source provenance, and station schedules.
5. Validate fatal errors and non-fatal quality warnings.
6. Compare the source identity, pipeline revision, and canonical records.
7. Generate the complete output set in a staging directory.
8. Verify schemas, cross-document relationships, CSV headers/counts, and workbook sheets/rows.
9. Atomically replace `data/` and `excel/` only after all checks pass.
10. Build the static site in another staging directory and deploy it with GitHub Pages.

A parser or validation failure leaves the previous published output untouched.

## Source identity

The published provenance includes:

- Microsoft repository and branch.
- Exact source commit.
- Raw Markdown URL pinned to the commit.
- Article URL and Markdown front-matter date.
- Retrieval timestamp.
- SHA-256 hash of the downloaded Markdown.

The pipeline revision is stored in metadata so a generator or parser revision can force a rebuild even when the source bytes are unchanged.

## Station matching

Detailed station sections are matched to high-level trains by the PQU ID parsed from the section heading. The application and platform builds in the section must also agree with the master record. A mismatched or duplicate section is fatal.

## No-op behavior

When the source commit, source hash, and pipeline revision are unchanged, the normalized data is not rewritten. A health-only heartbeat is committed at most once every 30 days. This keeps GitHub's public-repository scheduled workflow active without creating a commit every six hours.

## Pages deployment

GitHub Pages serves a static artifact produced from the verified repository data. There is no server-side API and no write path exposed to the public. The Pages deployment is retried on the next scheduled run if it fails.
