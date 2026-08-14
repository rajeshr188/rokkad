---
status: active
owner: project
updated: 2026-08-07
tags: [accounting, mvp, k7, production-readiness]
related:
  - standalone-accounting-mvp-readiness.md
  - ../adr/2026-08-07-standalone-accounting-pilot-policy.md
  - ../implementation/standalone-accounting-acceptance-pilot.md
---

# Standalone Accounting K7 Production Boundary

## Objective

Turn the proved accounting kernel into the smallest operable production MVP
without expanding into tax, bank feeds, inventory integration, legacy migration,
or other deferred modules. Starting K7 does not make the successor production
authority; DEA remains authoritative until every exit gate passes.

## Sequence

1. **K7.1 Authenticated facade — complete:** tenant-bound actor, permissions for
   create, authorize, post, reverse, trusted server time, and persisted
   maker-checker enforcement. Policy is recorded in
   `../adr/2026-08-07-standalone-accounting-production-authorization-policy.md`.
2. **K7.2 Audit and numbering — complete:** immutable creator, authorizer, and
   poster identity snapshots plus atomic `BOOK-YEAR-NNNNNN` allocation per book
   and accounting-period start year, preserving separate source identity.
3. **K7.3 Operations setup — complete:** controlled audited period lifecycle
   and deterministic, idempotent minimal organization/book/period/chart
   bootstrap. Customer classifications remain event-specific setup.
4. **K7.4 Narrow runtime path — complete:** schema-v1 cash-sale, credit-sale,
   and customer-receipt adapter with exact replay, changed-payload rejection,
   explicit failure evidence, and no caller model imports.
5. **K7.5 Assurance — complete:** read-only integrity command, real
   separate-connection replay/changed-payload/reversal/allocation races, clean
   tenant migration, isolated schema dump/restore rehearsal, and incident runbook.
6. **K7.6 Production candidate — complete with recorded owner waiver:** the
   minimum accountant evidence command and clean staging-style UAT pass are
   complete. The owner accepted the evidence, recorded that an independent
   accountant is unavailable, knowingly waived that additional review, and
   authorized proceeding only with the tested sales/receipts MVP scope.

Each step must remain deployable and testable on its own. Work stops at a failed
gate instead of compensating with broader features.

## Minimum Evidence Pack

- voucher register and conventional journal;
- trial balance, profit and loss, and balance sheet;
- customer statement, open-item outstanding, and unapplied receipts;
- reversal/correction lineage and classification reconciliation;
- operator-visible posting failures and integrity diagnostics.

## Production-Ready Definition

Production readiness is achieved only when all nine K6 production-entry gates
are evidenced, K7.1-K7.6 pass in staging, independent acceptance or an explicit
owner risk waiver is recorded, and a separate go/no-go decision authorizes a
narrow caller. It is not defined by a calendar date or by completion of the
accounting model alone.

## Explicitly Outside K7 MVP

Tax/statutory engines, bank feeds, configurable workflows, broad UI/admin CRUD,
inventory and loan adapters, reporting caches, legacy DEA migration, and DEA
cutover remain deferred. They require later scoped plans after the first narrow
production path is stable.

## Current Position

K7.1 through K7.5 are complete. K7.6 engineering evidence passed on the fresh
`accounting_pilot_k7_uat` tenant: four source deliveries produced five posted
vouchers including a reversal/corrected version; trial balance and balance
sheet differences were zero; the INR 1,000 invoice showed INR 600 outstanding;
the INR 600 receipt showed INR 400 allocated and INR 200 unapplied; and the
integrity command returned no findings. Source vouchers retain separate maker,
authorizer, and poster snapshots.

The production-boundary decision is **CONDITIONAL GO for preparing one narrow
sales/receipts caller**. The owner accepted the evidence on 2026-08-07 and
knowingly waived independent professional review because that resource is not
available. This increases residual accounting/compliance risk and is recorded
as an owner decision rather than an accountant endorsement.

The decision does not authorize tax/statutory behavior, additional adapters,
legacy migration, or DEA replacement. DEA remains production authority until
the narrow caller is implemented behind an off-by-default control, verified in
the target tenant, and explicitly enabled. A failed readiness check keeps the
caller off.

## Post-K7 MVP Activation Sequence

1. **K8.1 activation safety — complete:** tenant preference
   `accounting__successor_enabled` defaults off. Only an accounting
   administrator in the matching active tenant may change it. Enablement fails
   closed unless the tenant-bound PRIMARY book, Cash/Receivables/Sales ledgers,
   an open period, and clean integrity diagnostics are present. Preference
   changes are audited. The accepted UAT tenant is ready with zero blockers but
   remains deliberately disabled.
2. **K8.2 first visual workspace — complete:** K8.2a provides an
   authenticated tenant-scoped dashboard at `/accounting/`, financial reports
   at `/accounting/reports/`, and posted-voucher/journal detail. It shows
   activation readiness while disabled and reads only through canonical
   selectors/evidence. K8.2b adds activation-gated cash sale, credit sale, and
   customer receipt draft entry, separate authorize and post actions, and
   explicit receipt allocation. The maker cannot authorize the same voucher and
   the authorizer cannot post it. Credit-sale posting and open-item creation are
   one atomic facade operation. Templates never impersonate actors.
3. **K8.3 controlled target enablement:** exercise the UI in the pilot tenant,
   rerun readiness/evidence, then explicitly enable only the selected target.

The owner can now inspect and operate the tested workflow visually. K8.3 is the
next gate: conduct the visual workflow in the pilot tenant, rerun evidence and
diagnostics, then decide whether to enable a selected real target. No broad
accounting administration UI is implied.
