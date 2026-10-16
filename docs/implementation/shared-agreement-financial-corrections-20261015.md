---
status: verified-local
owner: project
updated: 2026-10-16
tags: [loans, corrections, implementation, verification]
related: [../adr/2026-10-15-shared-agreement-financial-corrections.md, ../contracts/loan-agreement-correction-v1.md, ../contracts/loan-servicing-bundle-v7.md, ../plans/shared-agreement-financial-corrections-20261015.md]
---

# Shared agreement financial correction

The owner approved the recommended sequence after asking how principal errors
should be corrected. This local implementation preserves the preceding collateral
work and the unrelated WhatsApp onboarding documentation. This implementation has
changed no production loan, configuration, provider, backup or deployed image.
Separate operational records and the proposed 16 October architecture review
added concurrently in the workspace are preserved.

## Ordered implementation

1. A common signed agreement preview/confirmation service classifies retained
   financial history and the supported saved agreement. It exposes principal,
   interest, fees and total before/after, per-item terms and affected allocations.
   The ordinary detail menu links to **Agreement details** across entry methods;
   the old paper URL remains compatible. The detail history explains retained
   agreement corrections and distinguishes replay from a new payout or collection.
2. Existing recorded anniversary correction remains its concrete financial
   recognition function. The shared boundary additionally binds current collateral
   and loan facts. Direct policy/2 simple/full-month bullet/flexible correction
   retains the genuine approval and creates an explicit `CORRECTED` disbursal
   snapshot. It copies the saved policy exactly, compensates affected events and
   replays retained receipt amounts/dates under the corrected item terms. Monthly
   headers retain `agreement_revision`; old headers default to 1. The current
   revision governs period continuation and advance consumption. Unsupported
   ordinary reversed charges cannot acquire a new revision automatically.
3. Current documents project revised terms and disclose correction provenance;
   original approval/snapshot rows and already issued bytes remain. Version-7
   servicing bundles retain revised native snapshots, monthly headers, checkpoint
   corrections and existing identity/collateral evidence. Old profiles keep their
   row meanings and refuse the new evidence. Exact recovery retains identical rows
   and original artifacts under the existing owner-only recovery contract.
4. Reviewed opening/4 or /5 correction records `OPENING_CORRECTION`, with its
   previous checkpoint hash/values and complete corrected review. Its balance
   effect is the reviewed difference; the original `MIGRATION_OPENING` remains
   the sole origin. Original/remaining principal and current-period bases remain
   separate. Current obligations supersede the previous frozen schedule with the
   explicit correction event as source. Original dates/source/rule and physical
   facts are retained. Ordinary later collection uses the corrected checkpoint.
5. Direct full closure can reconcile corrected agreement and actual original
   settlement cash while retaining the release document and all physical return
   evidence. Original paper full closure and supported paired recorded renewal
   remain supported. Missing connected evidence is held, rather than converted
   into another origin or bypassed through direct updates.

## Reminder and monitoring acceptance

The classifier, thresholds, policy resolution and current valuation meanings stay
unchanged. Actual revised debt appropriately changes risk inputs and makes prior
assessments stale. Equivalent corrected direct/paper agreements with the same
current evidence produce equal tested assessments and alert decisions.

Native notices previously bypassed paper-review delivery checks. A reviewed
financial correction now supplies a separate agreement identity in new notices;
delivery checks it before that native bypass. Former queued notices are held.
Risk previews and request keys distinguish a newly reviewed agreement while keeping
the same-event duplicate guard. The native unique constraint includes agreement
identity, with the prior zero meaning for old rows. New notice inserts must bind
the actual current loan/Workspace correction; their bound payload cannot be
rewritten. Old notices are retained, not patched or automatically resent. Existing
Party identity, consent, template and delivery requirements remain independent.

## Supported boundaries

This release does not independently restate native linked renewals, funding,
auctions, shared-batch closure, concessions, legacy unsupported financial profiles,
or an opening baseline that already has financial servicing/settlement. Existing
supported paper paired reconciliation remains available. The checkpoint review
preserves original dates, cutover, physical source and frozen rule; correcting
those boundaries requires a separately supported review. Financial correction does
not add/remove collateral, assign debt to a new borrower, infer a refund or change
current lending setup. Real later actions remain business actions.

## Verification and release state

The final financial/document acceptance selection passes **45 tests in 82.609
seconds**. It includes the complete new agreement module and complete existing
document/imported-ticket modules: direct/paper/accepted-history financial replay,
checkpoint uncertainty, settlement, repeated revisions, item allocation, later
renewal, signed HTTP review, authorization/RLS, stale requests, exact recovery,
issued bytes, corrected receipts, equivalent risk and agreement-bound reminders.

The final portability selection passes **179 tests in 271.702 seconds**, covering
existing servicing bundles, portable origination correction and both new corrected
native/checkpoint round trips. Test discovery includes imported fixture classes;
these selections overlap and are not a combined unique test count.

An earlier path-validated 567-case regression run completed in 768.525 seconds
with 564 passing and three document-projection errors. Those errors concerned
pure projection stand-ins and the authoritative unchanged-opening reader contract;
they are fixed and the complete affected modules pass in the 45-case follow-up.
The final portability run also covers the subsequent original-date validation
restriction to corrected snapshots. The entire 567-case selection was not rerun.
Earlier exploratory logs retain resolved fixture failures; an interim run with an
incorrect test-module name was stopped and replaced by the path-validated runner.

Synthetic acceptance artifacts are under the ignored task folder
`.tmp/loan-corrections-20261015/`. Ten desktop/mobile agreement form/review checks
passed without JavaScript errors or horizontal overflow; visual review prompted a
clearer narrow comparison table and proper long imported-number wrapping. Final
captures were regenerated from the HTTP tests and representative mobile reviews
were inspected. Django system checks, migration/model consistency and import
boundaries across 1,222 tracked/new Python files pass. No customer content or
provider delivery was used; messages are synthetic
and provider calls are mocked or commit callbacks discarded by test rollback.
Documentation validation passes for 1,445 local links across 46 curated files;
whitespace validation passes. After all test readers exited, the guarded cleanup
removed only the isolated fictional `test_rokkad_corrections_20261015` database and
verified its absence. Ignored acceptance logs and synthetic captures are retained.

New financial migrations are Loans 0079, 0080 and 0081 plus portability 0029,
after the preceding collateral migrations Loans 0078 and portability 0028. Existing
Workspace-owned tables retain direct ownership and forced RLS; no new table or
ownership registry is introduced. Runtime processes remain restricted. Coordinate
compatible web, monitoring and scheduled readers before enabling these writes.
After corrected evidence exists, keep compatible readers and stop writes instead
of downgrading. The owner authorized commit/push on 16 October, preserving the
separately deployed Party-merge implementation and the joining no-op migrations
Loans 0083/0085. Agreement/collateral corrections remain undeployed. The unrelated
WhatsApp onboarding checkpoint stays outside this Git publication.

## 16 October combined Git publication acceptance

Before the requested commit/push, a fresh disposable database applied both pending
correction and deployed Party-merge branches, including Loans 0083/0085. The
combined agreement, collateral, Party-merge, borrower-correction and document
selection passes **100 tests in 196.115 seconds**, including both real PostgreSQL
borrower-admission race orders. These cases overlap earlier selections.
Django/migration consistency and import boundaries across 1,225 Python files pass.
The exact staged tree passes current-document link validation. Publication
candidates pass Python parsing, conflict-marker and credential-pattern checks;
private configuration, artifacts and unrelated onboarding notes are excluded.
