---
status: implemented-local
owner: loans
updated: 2026-10-03
tags: [khata, corrections, compensation, verification]
related: [khata-custody-settlement.md, ../adr/2026-10-01-khata-bounded-corrections.md, ../architecture/khata-technical-design.md, ../plans/khata-delivery-design.md]
---


The later [document-navigation checkpoint](khata-document-navigation.md) records the current
local runtime; earlier checkpoint identities/counts below remain dated evidence.
# Khata correction safeguards checkpoint

The later [action-guidance checkpoint](khata-action-guidance.md) records the
guidance runtime and preserves these compensating-command boundaries and original
source evidence. Earlier identities remain dated verification checkpoints.


The original backend checkpoint adds local safeguards under the
[bounded correction ADR](../adr/2026-10-01-khata-bounded-corrections.md), extending
[custody/settlement](khata-custody-settlement.md). Subsequent operator forms and
the exception-guidance follow-up below extend local usability.
Production activation remains separate. The later [searchable servicing checkpoint](khata-collateral-usability.md#searchable-servicing-follow-up-2-october)
was the next local runtime identity and retained this correction behavior. The
[measured read-performance checkpoint](khata-read-performance.md) followed it,
retaining the same correction authority before the current collection/event slice.

## Exception-guidance follow-up (2 October)

Following phased-improvement authorization, exact History sources now expose
read-only type/state/already-corrected/dependency guidance. An authorized writable
administrator can enter review with the exact supported source selected. Blocked
form previews use structured `KhataCorrectionBlocked` IDs, retaining the previous
ValueError/message contract, to show up to ten account-scoped source links and a
total count. Other refusal rules and posting/calculation/SQL guards are unchanged.
The shared scope/support disclosure links no automatic reversal or external send.
The [operator runbook](../flows/khata-servicing-and-recovery.md#exceptions-and-support)
records actual cash/custody evidence, administrator review and escalation.

No new correction kind, migration, tenant table or money/custody effect is added.
Broader correction outcomes remain in the first phase's specification backlog;
see [the delivery sequence](../plans/future-work.md#improvement-delivery-sequence).
Four new integration tests pass in 2.648 seconds; the final image passes
**399 Linux regressions in 184.928 seconds**. Tests cover supported-source
entry, viewer refusal, linked blockers with no correction/balance change,
unsupported/corrected/settled sources, Workspace boundaries and a ten-row display
cap. A pre-freeze test caught and fixed a source-prefill variable shadowing the
form data. Original financial/custody/permission/isolation tests pass unchanged.

Actual Chromium checks prior register/tabs plus exact-source scope/help, blocker
links, prefilled choices, blocked preview without confirmation, account-ID scoping,
viewer refusal, desktop/mobile and native no-JavaScript navigation. No business
mutation occurs; the submitted blocked preview cannot produce a correction.
Screenshots are inspected and no page JavaScript errors occur.

| Current resource | Exception-guidance result |
| --- | --- |
| Candidate | `khata-local-20261002-1cde3312c625` |
| Source inventory SHA-256 | `1cde3312c62510759c97da3d605f05cb3cb5daaf031a98a32a299e298a4d2269` |
| Frozen archive SHA-256 | `3a4de47ea06c0471e0e88e64a155416d3323ac784118ae3bc9dbbe395ffac47e` |
| Image ID | `sha256:e5cd51eb489c7c16d6adc75816b73e75acbf4f5aeae88267893ac9ae97ea3b82` |
| Private checks/recovery evidence | `.tmp/khata-exceptions-candidate-20261002/` |
| Static volume | `khata-exceptions-20261002-static` |
| Current web | `khata-img-20261002-web` |
| Retained previous web | `khata-img-20261002-web-pre-exceptions` |
| Local review | `http://127.0.0.1:8077/w/khata-73081a4c/loans/khata/` |

All 1,402 application/settings files match the frozen source and built image.
Only subsequent delivery documentation differs. Existing fictional records/media
are preserved with private pre-update backups/checksums. Migration/no-drift,
dependency and restricted production-profile/static/owner-refusal checks pass.
Production, remote CI, physical camera/printer and named operator acceptance are
not changed by this local slice.

## Commands and supported outcomes

`services/khata_corrections.py` exposes `preview_correction` and
`record_correction`, targeting an explicit source on the same active account.
Confirm today's review hash with reason, resolution reference and request UUID.
Preview/confirmation require `workspace.settings.manage`; confirmation also needs
the affected money/custody capabilities. Existing Workspace/commercial write
restrictions apply. Commands lock Workspace then account, reject stale evidence,
and preserve UUID identity. Dates cannot precede any recorded operation.

| Source | Actual resolution | Result |
| --- | --- | --- |
| `INTEREST` | Entire receipt `NOT_RECEIVED` or actually `REFUNDED`, with reason/reference; requires `loan.repay` | Append linked CORRECT, retain original allocations and restore unpaid interest. Charges, minimum, principal and entitlement are unchanged. |
| `EXCHANGE` before outgoing handover | Cancellation reason/reference, current prices/photos, hard retained LTV; requires `data.edit` and `loan.release` | Retain original evidence, release original OUT logically and reserve all IN replacements for actual return under CORRECT. |

Corrected interest reinstates current dues and overdue blocks. New ordinary
receipts allocate against restored dues oldest-first, and settlement collects
them. Annual receipts retain every original monthly charge and annual due date.
Partial compensation, advance/credit handling and promised refunds are unsupported.

Exchange cancellation changes reservations, not physical custody. Both item
groups remain held. Old outgoing items resume backing; replacements reserved for
return do not. Old cancelled-source handover is rejected. Return replacements
under CORRECT using actual recipient/reference; while active, check current hard
LTV and clear due interest. Financial settlement retains that source and pending
handover. A compensated original item may be exchanged again, preserving history.

## Dependencies and refusal boundary

Later uncorrected account operations block the source correction with their IDs,
including later deposit/photo/finalization records. Pending later correction
returns also block earlier work. Independent whole receipt corrections can unwind
newest-first; no automatic chain unwind or inferred physical/cash return.

Unsupported kinds and settled/closed accounts fail closed. Wrong payouts/opening,
charges, activated amendments/reductions, settlement, completed returns and
complex dependent histories need separate reviewed workflows. Existing successor
proposals can change valid future terms; never edit posted history as a repair.

## Database and verification

Migration `0038_khata_corrections` adds CORRECT and protected unique
`correction_of` to existing directly owned forced-RLS operations. No new tenant
table or registry count change. Historical item/role uniqueness becomes an
account-locked active-membership guard; operation/item uniqueness and immutable
selection rows remain.

Prefix-bounded SQL ignores compensated receipts in paid/due/allocation and
settlement checks, and compensated reservations in custody eligibility. New
replacement-return reservations remain effective. Deferred checks require exact
source allocations, complete correction children and hard retained LTV. Runtime
DML cannot alter/delete original or correction evidence. Failed writes roll back
reservations and compensation together; concurrent confirmations commit once.

163 focused/regression tests pass: 22 correction cases and the earlier 141 khata,
registry, ordinary partial-month policy and storage cases. Coverage includes
monthly/annual receipt restoration, re-collection/settlement, overdue blocks,
grouped cancellation, actual returns, item reuse, dependency IDs, stale prices,
permissions/write restrictions, retries/rollback/concurrency and restricted-role
bypass attempts. Migration consistency, system, documentation and
syntax/whitespace checks pass.

Only the dedicated local test database was migrated. UI/documents, shared
summaries, native recovery and pilot review of supported/refused correction
outcomes remain release gates; no real-account activation is authorized.
