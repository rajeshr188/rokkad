---
status: accepted
owner: project
updated: 2026-09-12
tags: [loans, portability, continuation, obligations]
---

# Continue the reviewed collection baseline across migration cutover

The owner instructed continuation and remaining-obligation integration after the
opening read foundation. The ordinary period descriptor in `loan-opening-review/1`
does not implement the inclusive anniversary agreement. Preserve that version;
add an explicit [version 2 checkpoint](../contracts/loan-opening-review-v2.md)
for `original-anniversary-upfront-inclusive/2` only. This follows the
[collection baseline decision](2026-09-12-legacy-collection-estimates-and-concessions.md).

For unchanged item principal, sum original item principal times monthly rate,
multiply by additional months using original anniversaries, then HALF_EVEN-round
once. Recognize the reviewed cumulative baseline through cutover independently
of opening unpaid interest. Additional unposted collection interest at date D is
the cumulative baseline at D minus the cumulative baseline through cutover.
Rounding each new month independently would change the total across migrations.
First-month payment requires explicit reviewed coverage. The difference between
recognized baseline and unpaid interest does not identify historical receipts or
concessions, so no such events are manufactured.

The exposure selector uses this projection for compatible openings and keeps it
separate from recorded debt. Native daily exposure calculations remain unchanged.
Unsupported review versions, absent opening obligations and subsequent financial
events fail explicitly; no partial-principal payment effect is guessed. Financial
posting and native accrual previews remain blocked until their specific servicing
and reversal paths are implemented. This is not activation of the legacy cohort.

Persist remaining reviewed obligations in the existing immutable, forced-RLS
schedule and obligation tables, linked directly to the migration opening. Preserve
original maturity and every supplied due date. The existing `disbursed_on` schedule
field stores the original contract date; it does not create a disbursal. Original
unpaid amounts are the new schedule's starting amounts, with no fake allocations
for prior payments. Recognized unpaid interest and projected contractual interest
remain distinct. The original source obligation IDs remain in frozen review
evidence; materialized rows have deterministic due-date/source-ID ordering.

The schedule service reuses owner-only historical setup authorization, rechecks it
before retry, locks the scoped loan and requires a sole opening before servicing.
It compares fingerprint, schedule fields and all obligation rows on retry; conflicts
raise an error. Schedule and rows are one transaction. Delinquency uses the reviewed
grace period instead of the destination product's current default. No schema change
or new public importer is introduced. Source authentication, balances, mappings,
unknown legacy facts, actual opening commit, servicing and export remain required
under the [first-import plan](../plans/first-legacy-import.md).

The authorized [full-release servicing follow-up](2026-09-12-opening-full-release-servicing.md)
now supports dedicated collection catch-up posting, full release and coupled
reversal. It extends the projection's supported event set accordingly; native
periodic accrual and partial-principal servicing remain blocked.
