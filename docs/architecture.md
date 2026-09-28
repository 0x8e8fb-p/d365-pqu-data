# Architecture

## Trust boundary

```text
MicrosoftDocs GitHub (five Learn articles)
        │ one resolved commit + Markdown
        ▼
GitHub Actions (Python)
        │ parse → normalize → validate → diff
        ▼
Canonical JSON (data/) ──► CSV, XLSX (excel/)
        │
        ├──► build-site: dashboard, api/, schemas/, feed.xml, calendar/*.ics, llms.txt ──► GitHub Pages
        │
        └──► versioned repository history
```

The public repository is the canonical published dataset. JSON is the canonical normalized representation. CSV, the workbook, the feed, the calendars, `llms.txt`, and the dashboard are generated from it.

## Sources

`config.SOURCE_SPECS` lists the articles. Every run resolves the MicrosoftDocs branch head once with `git ls-remote` and downloads every article at that commit.

| Key | Article | Required | Produces |
|---|---|---|---|
| `schedule` | Release schedule for proactive quality updates | yes | trains, station schedules, regions, schedule guidance |
| `service_updates` | Service update availability | no | service update lifecycle dates |
| `maintenance` | Maintenance in self-service environments FAQ | no | maintenance windows, maintenance Q&A |
| `pqu_overview` | Proactive quality updates overview | no | Learn text |
| `pqu_faq` | Proactive quality updates FAQ | no | Learn text |

If the schedule cannot be read or parsed, the run fails and nothing is published. An optional article is fail-soft: when it cannot be read or parsed, the last published copy is kept with state `stale` (or the article's data is left out with state `unavailable` when there is no earlier copy), and a `source-stale` or `source-unavailable` warning explains it. Each source's state is published in `metadata.json` and `health.json`.

## Update flow

1. Resolve the source commit, then download each article from the raw URL pinned to it.
2. Parse the Markdown into tokens (`mdtext.py`) and read the tables and sections each processor needs.
3. Normalize dates, builds, statuses, station schedules, maintenance windows, service update dates and guidance text, with provenance per article.
4. Validate. Structural problems are fatal; questionable values become quality findings (`warning`, or `info` for expected gaps such as sovereign clouds without a maintenance window).
5. Compare the content identity (SHA-256 and state of each source, plus the pipeline revision) with the published dataset.
6. Build every derived document from the validated records: change history, key dates (`events.py`), and calculated figures (`insights.py`).
7. Generate the complete output set in a staging directory and verify schemas, cross-document relationships, CSV headers and counts, and workbook sheets and rows.
8. Replace `data/` and `excel/` only after every check passes.
9. Build the site in another staging directory and deploy it with GitHub Pages.

A parser or validation failure leaves the previous published output untouched.

## Identity and provenance

Each article's published provenance records the Microsoft repository and branch, the commit, the raw Markdown URL pinned to that commit, the article URL, Microsoft's `ms.date`, the retrieval time, and the SHA-256 of the downloaded Markdown.

Identity is content, not commit. When a new upstream commit leaves an article's bytes unchanged, the run is a no-op and that article's provenance stays pinned to the commit where the content was first seen. The run health still records the commit that was examined (`checked_commit`). The pipeline revision is part of the identity, so a parser or generator change republishes even when the sources are unchanged.

## Derived documents

- `changes.json`: field-level differences between the previous and the new published copy for trains, station schedules, regions, guidance sections, service updates, and maintenance windows. A field introduced by a newer pipeline revision is a baseline, not a change.
- `events.json`: one event per change cutoff, train, station window, and service update milestone. Identifiers name what an event is (`production_window:10.0.48-PQU-6:station-4`), not when it happens, so a moved date updates the event instead of adding one.
- `insights.json`: medians and counts calculated from the published dates, each with its sample size, range, method, and the items left out and why. Dates questioned by a source warning are left out.

## Station and region matching

Detailed station sections are matched to high-level trains by the PQU ID parsed from the section heading. The application and platform builds in the section must also agree with the master record. A mismatched or duplicate section is fatal.

Azure region names are matched to maintenance-window geographies by name tokens (`maintenance.py`). Sovereign clouds only match geographies that carry the same sovereign token, and an unmatched or ambiguous name is reported rather than guessed. Microsoft does not publish this link; it is labeled as calculated wherever it is shown.

## No-op behavior

When every source's content and state and the pipeline revision are unchanged, the normalized data is not rewritten. A health-only heartbeat is committed at most once every 30 days, which keeps GitHub's scheduled workflow active in a quiet repository without an hourly commit.

## The site

`build-site` writes a static artifact from the committed data:

- `index.html` and a hashed `assets/app.<hash>.js`, concatenated from the modules listed in `site.JS_BUNDLE`. `js/core/` holds pure logic (dates, phases, lifecycles, windows, timeline and rollout geometry, build lookup, change wording) and runs unchanged in Node for unit tests; `js/ui/` renders views with DOM APIs only (no `innerHTML`).
- `api/`: every JSON and CSV document, plus `index.json`, which lists each file with its CSV and JSON Schema.
- `schemas/`, `downloads/D365-PQU-Tracker.xlsx`, `feed.xml`, `calendar/station-1.ics` to `station-6.ics` and `calendar/milestones.ics`, and `llms.txt`.
- `404.html`, which GitHub Pages serves for any missing path, so its links and assets use absolute paths from the site root.

`feed.py` and `ics.py` word changes and events the same way the dashboard does; a test runs the Python and JavaScript wording on the same changes and compares them.

Both pages carry a Content-Security-Policy meta tag: scripts only from the site plus the build-time SHA-256 of the inline theme script, styles only from the site, `connect-src 'self'`, and no `base`, forms, or plugins. The site loads nothing from third parties.

## Keeping an open page current

The dashboard works out "today" in the viewer's time zone. While a page is open, a timer aligned to each minute refreshes relative times, recalculates when the date changes or when a maintenance window shown on the page starts or ends, and, while the page is visible, fetches `metadata.json` at the check interval. When `generated_at` changes, every loaded document is fetched again. The new data is used only if `pqu.json` belongs to the same build, which avoids mixing documents during a deployment. The view is then redrawn in place, keeping scroll position, open sections, focus, and text selection, and the update is announced to screen readers.

## Pages deployment

GitHub Pages serves the static artifact produced from the verified repository data. There is no server-side API and no write path exposed to the public. If a deployment fails, the next scheduled run deploys again.
