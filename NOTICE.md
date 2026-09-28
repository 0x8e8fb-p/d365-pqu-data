# Source and data notice

This repository contains an automatically generated, machine-readable dataset derived from
Microsoft's public documentation in the
[MicrosoftDocs/dynamics-365-unified-operations-public](https://github.com/MicrosoftDocs/dynamics-365-unified-operations-public)
repository. Every source article is read at one pinned commit:

| Article | Repository file | Used for |
|---|---|---|
| [Release schedule for proactive quality updates](https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/quality-updates-schedule) | `articles/fin-ops-core/dev-itpro/get-started/quality-updates-schedule.md` | PQU trains, station schedules, station-to-region mapping, rollout notes (required) |
| [Service update availability](https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/public-preview-releases) | `articles/fin-ops-core/dev-itpro/get-started/public-preview-releases.md` | Service update lifecycle dates |
| [Maintenance in self-service environments FAQ](https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/deployment/plannedmaintenance-selfservice) | `articles/fin-ops-core/dev-itpro/deployment/plannedmaintenance-selfservice.md` | Planned maintenance windows by geography, maintenance Q&A |
| [Proactive quality updates overview](https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/quality-updates) | `articles/fin-ops-core/dev-itpro/get-started/quality-updates.md` | Learn content |
| [Proactive quality updates FAQ](https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/quality-updates-faq) | `articles/fin-ops-core/dev-itpro/get-started/quality-updates-faq.md` | Learn content |

Publisher: Microsoft. Every published snapshot records, per article, the source commit, file
path, raw URL, Microsoft's article date (`ms.date`), retrieval time, and SHA-256 hash.

## Microsoft documentation (CC BY 4.0)

Microsoft's documentation repository licenses its documentation under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/).
This project reproduces and adapts that text in `learn.json`, in the dashboard, and in the
workbook, with attribution to Microsoft and a link to each source article. The change feed and
the calendars restate Microsoft's dates and statuses with links to the source sections.

Changes made to the text: it is converted to structured text (paragraphs, lists, notes, and
tables); images, includes, embedded HTML, and tables that are published as datasets are
removed; and links are resolved to Microsoft Learn URLs. The text is otherwise reproduced as
published. Schedules, dates, builds, and statuses are published as data with the same
attribution.

The live test fixtures in `tests/fixtures/live/` are unmodified copies of the source articles,
used only for tests.

## What the MIT license covers

The MIT license in this repository covers the original automation code, templates, schemas,
and documentation written for this project. It does not cover Microsoft documentation,
product names, trademarks, or other Microsoft content, which remain subject to their own
licenses and terms.

## Derived values

Some values are calculated from Microsoft's published data rather than published by Microsoft,
and are labeled as calculated wherever they are shown:

- Phases, countdowns, and lifecycle states for the viewer's current date and time zone.
- The match between Azure region names and maintenance-window geographies
  (`maintenance_geo`), and the dark-hours windows paired with each production weekend.
  Microsoft does not publish this link or which window updates a given environment.
- Build positions ("N newer builds published") found by comparing build numbers.
- Figures in `insights.json`, such as release cadence, which record their sample size and
  what was left out.
- Key dates in `events.json`, the change feed, and the calendars, which restate Microsoft's
  dates and statuses in another format.

## No affiliation

This project is independent and is not affiliated with, endorsed by, or sponsored by
Microsoft. Microsoft, Microsoft Dynamics 365, Dynamics 365 Finance, and Dynamics 365 Supply
Chain Management are trademarks of the Microsoft group of companies.

## No warranty

The dataset is provided for informational and engineering convenience only. Microsoft can
change schedules, builds, statuses, and rollout windows at any time. The authoritative source
for an environment-specific update remains the notification and schedule shown in Microsoft
Dynamics Lifecycle Services and the Power Platform admin center.
