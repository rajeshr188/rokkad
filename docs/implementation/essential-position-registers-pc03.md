---
status: active
owner: project
updated: 2026-10-10
tags: [implementation, portability, loans, opening]
---

# PC-03 essential-position register imports

The existing **Import existing loans** screen offers three values-only XLSX
templates, also accepted as UTF-8 CSV with the exact same headers. One batch
uses one source profile and destination series, at most 20 loans and 200 source
rows, within the unchanged 5 MiB parser bound. Detection uses the exact template
headers rather than a vendor's status flag or filename.

| Template | Source meaning | Existing Loans admission |
| --- | --- | --- |
| outstanding-register/1 | Unchanged principal, first month paid upfront, aggregate whole-rupee half-even charges | loan-opening-review/2; unchanged |
| outstanding-register/2 | Explicit original/remaining item principal, current-period base and recognized/unpaid interest checkpoint | loan-opening-review/4 |
| closed-register/1 | Explicit zero debt and all collateral returned; unknown original terms remain unknown | loan-closed-position/1 through owner-reviewed closed-position admission |

## Reduced-principal facts

Account for every item still in custody; never drop a fully repaid retained item.
The existing opening writer requires positive initial item allocations, so this
template explicitly holds loans containing a retained item with zero remaining
principal for assisted position review. Later ordinary servicing may reduce an
item to zero; that is a different supported case. Supporting zero initial
allocations requires a separate narrow domain change, not invented principal.
Enter the original principal, remaining principal and `period_principal_base`
separately. The last is the actual principal used for the monthly period containing
the position date; a midperiod reduction does not rewrite that month's base.
The canonical calculator supplies the original-anniversary boundaries and rounded
period charge, which must reconcile to the supplied facts.

Whole-loan `recognized_interest` includes paid and unpaid recognized charges,
excluding separately recorded advance. `current_period_recognized_interest` and
`current_period_unpaid_interest` separate that month from prior unpaid interest.
`unpaid_interest` is the complete opening debt, repeated once per item but counted
once per loan. Blank essential amounts are unknown and rejected rather than zero.

`current_period_advance_interest` explicitly identifies current coverage;
`future_advance_interest` must be known zero for this spreadsheet. Use the existing
explicit per-period opening review when future advance exists. The source
`interest_quantum` is `1` or `0.01`; supported charges are simple full-month,
period-start principal, per-item HALF_UP. Freeze that source agreement in the
existing policy snapshot and retired servicing product, without applying today's
prices or standing agreement to a historical position. Unsupported capitalization,
instalments and principal increases remain held.

For a fictional 1 January loan of 10,000 at 2%, a 20 January checkpoint can retain
9,000 principal, a first-period base of 10,000 and a 200 advance covering that
period. With explicit zero recognized/unpaid interest, the next charge is 180 on
2 February, not 1 February. This is a calculation example, not actual book evidence.

## Closed positions

Use one row per loan with its stable loan/customer references, original number,
explicit zero principal/interest/fees and `collateral_returned=yes`. A reviewed
position date and reference identify the owner's attestation. No meaning is inferred
from “released” or from an absent release row. The one-time JCL exception is unused.

Original/closure dates, original principal, monthly rate and tenure may be absent
when unknown; known values are preserved and date/amount contradictions are held.
Customer matching, destination series, position date and source confirmation are
the only setup inputs. No servicing product, monitoring policy or original price
approval is created. Existing series number claims prevent duplicates and advance
a matching sequence only at successful confirmation. Closed customers may be
matched while inactive, but archived identities are excluded.

## Review, guards and rollout

Reuse GuidedOpeningBatch's immutable private source rows/hash, exact source Party
bindings, explicit customer preparation, owner/platform financial review, one-hour
signed confirmation, all-or-nothing batch commit and exact retries. Preview rolls
back temporary customer/product/loan writes. The existing Loans commands remain
responsible for accepted positions, origin uniqueness and subsequent servicing.
No pre-cutover receipts, payout, accrual, settlement or physical handover is invented.

Migration `data_portability/0021_position_register_profiles` replaces the existing
batch trigger function's supported source/result allowlist. It accepts only the
two named additional profiles and matches opening results to active batches and
closed-position admission results to closed batches, with the existing Workspace,
identity, source and finished-evidence guards intact. Reversal refuses to remove
support while new-profile batches are retained. There is no new table or Loans
financial schema change. Apply migrations with owner-only settings before serving
this code; runtime access remains restricted. No live data or production is changed
by local implementation.

Verification passes 123 broader adapter/checkpoint/closed-position/file-restore
checks, followed by 29 final adapter checks after tightening the review-version
guard. The latter include 16 new cases and 13 legacy register regressions. They
exercise actual confirmed imports, non-persistent preview, original-anniversary
charges, receipts/reversal, item rounding, source conflicts, retained unknown
closed terms, number claims, atomic failure, browser steps, spreadsheet formulas,
restricted-role isolation and immutable profile/result guards. The discovered
zero-initial-allocation limit now has an explicit held-case regression.

Verification uses frozen baseline `6dc71e4a` plus PC-01 through PC-03 files,
excluding unrelated concurrent Party/dashboard edits. Model/migration consistency,
app boundaries and documentation links pass. Fixtures are fictional and the
disposable database is removed. Staff acceptance with representative source
records remains necessary before a real cohort import. PC-04 volume/resumable
exchange is next; no deployment or live import is performed.

See the [accepted decision](../adr/2026-10-10-essential-position-registers.md),
[staff guide](../flows/guided-outstanding-register-import.md) and
[ordered plan](../plans/data-portability-completion-20261010.md).
