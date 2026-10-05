---
status: accepted
owner: project
updated: 2026-10-05
tags: [adr, loans, interest, calendar, rounding]
related: [2026-10-05-unified-loan-admission-and-continuation.md, ../plans/unified-loan-domain-correction.md]
---

# Shared monthly calendar and captured economic policy

The owner confirmed that direct, paper and imported loans have the same monthly
boundary: a 5 April loan with its first month paid upfront has no additional charge
through 5 May; the next monthly charge starts on 6 May. Rounding follows the
standing economic policy captured for the agreement. LD-01A implements that rule.

Use a small database-free helper for the original anniversary and inclusive
periods. Period one starts on the original date and ends on its first anniversary.
Each later period starts the next day and ends on the next original anniversary.
Clamp short months independently; a 31 January anchor returns to 31 March.
The first monthly principal basis remains original. A later charge uses balances
through the preceding covered day; payment on the new charge day affects the
following charge. Keep the existing actual item allocations and product-specific
partial-period conventions.

The supported economic rounding method is PER_ACCRUAL_PERIOD and uses HALF_UP.
The corrected itemized contract rounds each item in each period at the saved
policy quantum, then sums. Paper and reviewed opening profiles support paise and
whole rupees. Currency amount precision remains paise independently of interest
rounding. Neither current setup nor entry channel changes a saved agreement.

Version corrected evidence explicitly: direct disbursal policy version 2,
recorded-anniversary/3, loan-opening-review/3 and loan-history/3. Published old
history schemas and accepted old calculation profiles retain their original
interpretation. Opening version 3 must match its reviewed setup policy version,
quantum and supported simple/full-month terms. It retains recognized and unpaid
cutover amounts separately, never replays earlier history, and still requires one
financial origin. Wider reduced-principal checkpoint admission remains LD-04.

Native simple/full-month charges become eligible for finalization when a period
starts, using an actual effective date and a frozen partial-period record with a
full contractual charge. Subsequent periods advance by original period number,
preventing repeated charging of an already recognized month. Native ordinary
repayment previews eligible charges and recognizes them atomically before allocating
the receipt. Failed submissions roll back both steps; retries create neither extra
charges nor receipts. Reversing a receipt restores its allocation; the independently
owed monthly charge remains recognized. Risk projection uses the same period previews.
Active supported native bullet forecasts use the same calculation with transaction
knowledge capped at the reporting date, excluding already-paid advance coverage
and respecting principal reductions. Full settlement retains its existing review
and recognition purpose. Native reversed monthly rows require reviewed correction;
never silently skip an owed month or overwrite a retained row.

New itemized approvals freeze policy version 2, including origination advance
rounding. Old pending approvals without this version retain version 1 when disbursed;
reapproval is required to replace their frozen economics. New origination preserves
paise principal, fees and cash even when interest is rounded to whole rupees.

Existing accepted events, snapshots and issued files are immutable. A read-only
inventory marks legacy contracts for review. Supported paper term correction can
explicitly adopt the shared rule, compensate and replay dependent financial events
after fresh review, retaining the originals. No background or migration converts
existing loans. Native and opening cohorts requiring wider term/baseline correction
remain held for their supported review path during rollout; their old evidence
must not acquire an invented policy mapping. This is a correction programme, not
a claim that entry channel represents a separate borrower product.

Portability migration 0018 only extends existing batch profile choices and the
immutable profile/result guard. No new table or ownership boundary is introduced.
Old binaries are unsafe rollback targets after corrected profiles have been written;
keep compatible readers and stop new writes rather than downgrading evidence.
