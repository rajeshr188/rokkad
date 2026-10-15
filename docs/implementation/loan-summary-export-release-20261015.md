---
status: in-progress
owner: project
updated: 2026-10-15
tags: [loans, party, export, release, production]
related: [../adr/2026-10-15-filtered-loan-excel-summary.md, reviewed-production-release-20261015.md]
---

# Loan summary export production release

The owner explicitly requests safe production deployment of the filtered Excel
export and Party balance breakdown. This release includes only that feature and
its tests/documentation; unrelated WhatsApp sender-onboarding notes remain outside
the candidate. No model/schema migration, financial action, customer edit or
provider activation is required.

The candidate must pass exact-source CI, a restricted read-only rehearsal on a
fresh production copy, real filtered XLSX/Party checks, financial row preservation,
static assets, and recoverable image/backup checks. Web, monitoring and scheduled
application readers must use the same candidate. Preserve runtime configuration,
the three grace extensions and disabled WhatsApp activation. Capture a fresh
checkpoint before switching; retain the current compatible image for recovery.

Production acceptance requires healthy HTTPS, matching source, restricted database
roles, unchanged financial evidence, working exports/totals, restored timers and
a successful post-release encrypted backup verification. Raw customer rows and
downloaded workbooks stay on the private server; only verification metadata is
published here. Deployment results will be recorded after these gates pass.

The first full CI run finds one stale isolation assertion among 2,487 Loans
cases: the new export link preserves the user's search query, while the test
rejects that text anywhere in the response. The loan results are correctly empty.
The assertion now checks visible result text and absence of result cards, and
also inspects the actual Excel rows and rejects foreign licence/series filters.
The existing unknown/cross-Workspace detail and document checks remain intact.
Production has not switched; the corrected exact-source release gates must pass.
