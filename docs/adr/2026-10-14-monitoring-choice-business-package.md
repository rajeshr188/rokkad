---
status: accepted
owner: project
updated: 2026-10-14
tags: [portability, monitoring, contracts]
related: [2026-10-10-fresh-business-package.md, 2026-10-12-current-monitoring-valuation-policy.md]
---

# Preserve monitoring choices in business package version 3

The owner requests closing MR-05's explicit monitoring-choice portability gap.
Published business packages 1/2 and their setup schemas remain unchanged. Add
`rokkad-business-package/3` with a fixed setup-v3 schema extending setup-v2 only
by `LoanMonitoringPolicy.valuation_basis`, with the four permitted enum values.
The package keeps version 2's graph adapters, exclusions and bounds.

Export automatically selects version 3 when any retained monitoring policy has an
explicit valuation choice, including a superseded or future version. Default-only
businesses keep their existing version-selection behavior. Explicit exports through
older setup versions still refuse the unrepresentable choice. Version 3 validates
and remaps original dates, scope, predecessor links and all other policy fields
through the existing bounded atomic package path. Missing/unknown fields and
downgraded manifests are refused. No source users, authority, commercial access,
financial history or fresh assessment projections are imported with the setting.

Restore still requires an empty unactivated business, current local authority,
rollback preview and exact reviewed confirmation. Licence source claims remain
inactive until destination review; an imported monitoring choice does not imply
original approval, physical appraisal or complete paper books. Actual current
assessments are rebuilt from destination data, prices and book coverage.

Migration 0026 extends only the immutable receipt guard's allowed package profiles.
Its ownership/RLS/source/result checks stay unchanged. Reversal is refused when
version-3 receipts remain, rather than strand accepted evidence. This migration
depends on the existing portability and monitoring merge; it is not a standalone
production-only overlay. Older readers intentionally refuse unknown version 3.
Deployment and production policy selection remain separate from this local fix.
