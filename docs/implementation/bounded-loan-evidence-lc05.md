---
status: locally-complete
owner: project
updated: 2026-10-06
tags: [loans, implementation, evidence]
---

# LC-05 bounded loan evidence extensions

The six selected extensions reuse ordinary loans, source documents, allocation
lines and opening checkpoints. No parallel loan domain or new Workspace table is
introduced. See the [contract](../contracts/bounded-loan-evidence-lc05.md) and
[decision](../adr/2026-10-06-bounded-loan-evidence-extensions.md).

## Delivered behavior

- Opening paper receipts can carry complete staff item principal splits. The
  receipt preview checks totals and item capacity; replay and portability check
  those same facts. Current payments retain their existing allocation priority.
- Paper receipts accept the actual fee component, including zero. Outstanding
  fees require it; the software does not choose a historical fee priority.
- Multi-item archives reconcile each retained source item before ordinary complete
  history admission. Source count/identity/known weights and snapshots must agree.
- Importers can prepare complete-history, outstanding-register and source-verified
  legacy opening imports. Owner financial preview/commit remains separate. Register
  preparation creates no Party, product, identity binding or financial records.
- Precisely timed opening checkpoints support actual later same-day receipts and
  current settlements. Old date-only checkpoints stay end-of-day. Opening export/4
  preserves timestamps and explicit allocations, including same-day closure restore.
- Owner review can admit a verified CLOSED terminal position with incomplete earlier
  receipts. The ordinary detail shows the original agreement and zero closure
  position, with unavailable earlier financial totals and unknown custody disclosed.

## Operator entry points

In **New loan → Record completed payout**, the advanced link **Record a verified
closed position** opens the terminal adapter. Historical
reconciliation passes its selected archive to that screen. The owner supplies and
reviews actual agreement/item/closure evidence before confirming. An unknown
closure date, disputed zero position or unsupported agreement stays in the archive.

In supported import reviews, delegated staff see **Save preparation for owner
review**. The owner generates the financial preview and confirms admission. Legacy
dump candidates remain source-verified operator preparations through the existing
staging command; source verification is retained while financial preview moves to
owner review. All final commands recheck authority inside the transaction.

In paper repayment, optional actual fee and timestamp fields accompany the
existing item principal fields. Timestamp is essential only for checkpoint-day
paper receipts. Review/5 checkpoint preparation is an explicit evidence document,
not an inferred time in the date-only register importer.

## Storage and compatibility

Migration 0061 expands archive source-binding proof to multi-item admission/2.
Migration 0062 adds terminal source-binding proof and immutable terminal event/state
guards. Both retain ordinary forced RLS and existing tables. Migration 0062 was
rolled back/reapplied successfully in the disposable owner-role QA database after
its final SQL change; no production database was migrated.

The original outstanding-register calculation contract explicitly retains policy/1
instead of inheriting today's policy/2 default. Review/1–4, opening exports/1–3,
paper repayment/1 and archive admission/1 retain their meanings and retry shapes.
General servicing bundles preserve nested new evidence profiles, original archives,
source documents and unknown terminal custody across scoped restoration.

## Acceptance

All 475 affected regressions pass (388.162s), followed by 37 final checks
(27.232s). The earlier exact-recovery deadlock passes both in isolation and in
the final complete run. Final checks cover operator command delegation, terminal
inventory/HTTP disclosure, actual fee/split evidence, ordinary native eligibility
and timed cross-Workspace restore. Django checks, no migration drift, nine template
compilations, 81 Python parses, runtime inventories and whitespace checks pass.
See [Status](../STATUS.md). Private logs are under `.tmp/lc05-20261006/`.
Synthetic service, database, HTTP and portability checks do not establish actual
production source-book acceptance. No bulk archive conversion, deployment, commit
or push is included in this slice. LC-06 remains the configurable seven-day
prospective quote-age workflow; LC-07 remains release acceptance.
