# Live source snapshot

These files are byte-for-byte copies of Microsoft Learn source articles, downloaded from
[MicrosoftDocs/dynamics-365-unified-operations-public](https://github.com/MicrosoftDocs/dynamics-365-unified-operations-public)
at a single commit. They are used as parser and pipeline test fixtures only.

- Commit: `d21e69eecf3c47e3a74d992d6e2032b6bd570bb4`
- Retrieved: 2026-09-28

| File | Repository path | Article |
|---|---|---|
| `quality-updates-schedule.md` | `articles/fin-ops-core/dev-itpro/get-started/quality-updates-schedule.md` | <https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/quality-updates-schedule> |
| `public-preview-releases.md` | `articles/fin-ops-core/dev-itpro/get-started/public-preview-releases.md` | <https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/public-preview-releases> |
| `plannedmaintenance-selfservice.md` | `articles/fin-ops-core/dev-itpro/deployment/plannedmaintenance-selfservice.md` | <https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/deployment/plannedmaintenance-selfservice> |
| `quality-updates.md` | `articles/fin-ops-core/dev-itpro/get-started/quality-updates.md` | <https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/quality-updates> |
| `quality-updates-faq.md` | `articles/fin-ops-core/dev-itpro/get-started/quality-updates-faq.md` | <https://learn.microsoft.com/en-us/dynamics365/fin-ops-core/dev-itpro/get-started/quality-updates-faq> |

The article text is © Microsoft and licensed under
[Creative Commons Attribution 4.0 International](https://creativecommons.org/licenses/by/4.0/)
by the MicrosoftDocs repository. The files are unmodified.

`expected-*.json` files are characterization snapshots produced by the parser that existed before
the v2 parser changes (pipeline revision 1.0.0). They hold the normalized records, stations, regions,
and quality findings without timestamps or provenance, so parser refactors can prove that
previously published fields are unchanged.
