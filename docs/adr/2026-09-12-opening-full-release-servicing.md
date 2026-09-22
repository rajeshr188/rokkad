---
status: accepted
owner: project
updated: 2026-09-12
tags: [loans, portability, release, reversal]
---

# Settle opening loans through the existing full-release workflow

The [September 23 payment extension](2026-09-23-opening-partial-payments.md)
supersedes the partial-repayment restriction below. This original release evidence
contract remains supported and unchanged for histories without payments.

The owner instructed financial posting and full-release/reversal integration after
the [continuation and obligations slice](2026-09-12-opening-collection-continuation.md).
For the supported unchanged-principal v2 collection rule, reuse the ordinary full
release service, form, numbering, valuation/physical-verification checks, custody
return, immutable receipt, explicit concession and newest-first reversal workflow.
No source loan is imported or activated by this change.

The quote is opening principal + unpaid opening interest + fees + the cumulative
additional collection baseline after cutover. Preserve inclusive original billing
anniversaries and first-month coverage. At full release, record a catch-up interest
event and immutable accrual row immediately before the release receipt, in the same
transaction as allocation, schedule termination, collateral return and closure.
Zero catch-up creates no accrual. Existing `loan.release` authorizes this coupled
operation, as it does native release-day catch-up. A concession still requires
Workspace administration as well. There is no new standalone accrual command.

The catch-up payload names `OPENING_COLLECTION_CATCH_UP` and carries an
`opening_collection` group with profile `opening-release/1`, opening event ID,
release request key, rule, cumulative baseline at cutover and at collection, and
calculation `CUMULATIVE_BASELINE_LESS_CUTOVER`. Its interval is C+1 through collection;
the accrual ordinal identifies the recorded attempt, not a fabricated original
monthly period. Fraction 1 describes the complete catch-up interval. The unrounded
amount is the additional months times the unrounded monthly charge; the recognized
amount is the difference of cumulative rounded baselines. These can differ from
rounding the new interval alone. Original per-item bases remain in opening evidence;
no artificial per-item rounding allocations are added. The loan page labels these
rows as collection catch-up rather than ordinary periods.

Full release settles all actual recorded interest, including the catch-up. Allocate
cash interest against the remaining reviewed schedule up to its available interest;
record any excess separately as `release.unscheduled_interest_paid` in the same
receipt. The event's interest value still records **all** cash interest collected.
This handles collection interest beyond the original schedule without inventing
new due dates or historical obligations. Principal remains fully allocated, fees
remain recorded balance components, and the release terminates the original
remaining schedule. A concession reduces only interest and is separate from cash.

Only the dedicated release and reversal paths may store these migration servicing
events. The ordinary event writer stays closed to opening loans. Partial repayments,
native monthly accrual/capitalization, renewal and auction remain blocked for this
origin. A generic event helper is internal storage, never an authorization boundary.
The full workflow owns permissions, the Workspace-scoped loan lock and validation.

Reverse the full release to reverse its catch-up as well, atomically restoring
receipt amounts, concession, original schedule and custody. Independent catch-up
reversal and ordinary opening reversal are rejected. New attempts use new request
keys and accrual ordinals; the former reversed evidence remains immutable. Readers
validate paired catch-up/release/reversal evidence, stop projecting interest while
the release is effective, and respect as-of dates across later reversal. Item
principal reads consume full-release closing lines and restore them on reversal.

Service/UI tests cover settlement, pre-cutover interest and fees, zero catch-up,
cumulative rounding, concessions, release-only staff, cross-Workspace rejection,
retry and reversal, historical reads and rollback of posting, numbering, schedule
and custody changes. No new table or migration is needed. Actual source approval,
legacy evidence gaps, destination mapping, import commit/rehearsal and truthful
opening export remain pending under the [first-import plan](../plans/first-legacy-import.md).
