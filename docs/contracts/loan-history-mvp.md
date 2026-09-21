---
status: active
owner: project
updated: 2026-09-12
tags: [loans, portability, mvp, contract]
---

# Complete-history Loans MVP contract

This is the bounded contract review selected after Party portability closeout.
It specializes the [exchange draft](rokkad-data-v1.md), not a new architecture.
Canonical `loan-history/1` staging, reconciliation, explicit atomic commit and
export are implemented locally. Use the dedicated Loans import endpoint. See the
[wire format](loan-history-jsonl.md) and [operator flow](../flows/loans-history-import.md).
No production deployment or vendor-specific compatibility is implied.

## Selected scope

Use the existing FLEXIBLE_PARTIAL_PAYMENT product structure, NONE amortisation,
FLEXIBLE payment frequency and REDUCE_PRINCIPAL extra-payment rule. This supports
ordinary repayments without introducing installment schedule replacement. The
source must supply a compatible frozen calculation contract; matching a product
name alone does not establish compatibility.

Both ACTIVE and CLOSED loans are supported. CLOSED means one
fully evidenced full release, not auction or renewal closure. Supported histories
contain one original disbursal, zero or more repayments and finalized interest
accruals, and optionally one full release with its catch-up accrual. Principal
capitalization, reversals, renewals, auctions, funding pledges, partial releases,
installments and missing-history openings are outside this first profile. Reject
a whole loan containing unsupported events; never omit an event to make it fit.
Multiple collateral tranches must reconcile using existing Loans calculations.

This choice does not exclude closed loans or make active loans opening balances.
Lifecycle state and source-history completeness are independent.

## Required evidence and reference resolution

| Group | Required meaning | Existing owner |
| --- | --- | --- |
| Source identity | Stable source namespace, loan ID, source loan number, checksum, ordered source event IDs, extraction/cutover date and source actor references | Portability identity/provenance, separate from local actors and primary keys |
| Borrower | Exact source Party reference resolved to one destination Party | Party identity services |
| Setup | Explicit destination licence/revision, series and product-version mapping; compatible frozen terms; no automatic activation of imported setup | Loans licence/series/product services |
| Approval | Original approved terms, approval date and source actor evidence, collateral valuations and economic snapshot | PawnLoanApprovalSnapshot |
| Disbursal | Business date; gross principal, advance interest, deducted fees and net cash; policy and tranche evidence | PawnLoanEvent, LoanPolicySnapshot, PawnLoanDisbursalSnapshot |
| Schedule | Original maturity, dated obligations, frozen product/calculation version and allocations | RepaymentScheduleVersion, RepaymentObligation, obligation allocation evidence |
| Collateral | Stable item references, physical description, weights/metal/purity, frozen valuation and principal/rate tranches, custody lineage | PawnCollateralItem and custody/storage evidence |
| Repayment | Business date and source sequence, received amount, fee/interest/principal split, item and obligation allocations | PawnLoanEvent and repayment allocation lines |
| Accrual | Period boundaries, frozen rate/calculation basis, recognized amounts and tranche detail | PawnLoanInterestAccrual and lines |
| Full release | Source release number/date, payer/collector evidence required by the domain, settlement components, all released items and custody return, schedule termination | PawnLoanRelease, release items, closing lines, custody and obligation termination |
| Reconciliation | Independently supplied expected principal, interest and fees at event checkpoints and cutover; final custody and schedule state | Existing balance, obligation and tranche selectors |

References in nested evidence use portable identities, never blindly copied local
IDs. Missing required historical approval, valuation, allocation or licence facts
block activation. An importer actor does not become the original approving actor.
Unknown source actors remain explicit source provenance; they create no accounts,
memberships or permissions. Local recording time and historical effective time
must remain distinguishable. Same-day source order must be preserved explicitly;
current creation timestamps are not sufficient source chronology.

Binary documents/photos are excluded from this financial profile. Do not fabricate
an official document issue or claim attachment-complete restoration. The manifest
must declare the excluded coverage. Missing evidence required to substantiate a
financial/custody transition is a validation error even if binaries are excluded.

## Numbers and setup

The [setup preparation page](../flows/loans-import-preparation.md) now checks
existing mappings and displays number candidates. It does not persist mappings,
reserve numbers or validate/commit financial history. The separate JSONL upload
workflow now performs those financial checks and explicit commit.

Reuse reviewed destination setup only after an explicit compatibility mapping.
Do not infer historical terms from today's product defaults or Rates quotes.
Keep the exact original loan/release numbers as source aliases. Default local
numbers use a distinct historical namespace, as already specified by the main
portability plan. Check field lengths, destination uniqueness and collision with
future live allocation. No live allocator is called during historical import.
Exact operational-number preservation requires a separately reviewed reservation/
cutover path; it must not silently advance, rewind or consume live counters.

M3 setup/numbering remains a prerequisite. It need not become a general setup
importer before a bounded history profile can use explicitly mapped existing
setup, but historical licence evidence and number isolation must be implemented
and tested before commit is exposed.

## Validation and commit behavior

1. Parse a bounded versioned source graph and reject unsupported structures/events,
   non-finite or overprecision amounts, missing references and impossible chronology.
   Freeze exact byte/graph bounds with the executable schema before releasing it;
   Party row limits do not automatically become a valid Loans graph limit.
2. Resolve all destination references within the explicit Workspace. Validate
   original terms, allocations, schedules and custody using Loans-owned rules.
   Do not recalculate source repayments using today's date or current balances.
3. Preview the complete aggregate with no retained business writes. Display source
   numbers, local number mapping, dates, state, financial reconciliation and exclusions.
4. Bind confirmation to operator, Workspace, source graph and destination mappings.
   Recheck authorization, lifecycle and stale evidence under locks at commit.
5. A Loans-owned historical command writes one complete loan atomically through
   ordinary restricted-role database access, without disabling guards or changing
   native live-entry commands. Failure in the last release/custody row rolls back
   the entire imported loan. No notification, payment or document-issuance side effect.
6. Reconcile event balances and allocation/custody invariants at every source
   checkpoint, end of each effective date and cutover. Same-day intermediate checks
   require the ordered event prefix; an end-of-day selector alone cannot prove them.
   Compare recorded balances, contractual dues/DPD and projected interest separately.
7. Identical source replay returns the existing result after authorization. Changed
   input, changed local state or duplicate source identities fail explicitly.
   Corrections never overwrite completed source evidence.
8. Canonical export and destination re-export preserve supported historical facts,
   with only explicit identity/local-number/operator-recording differences.

ACTIVE requires reconciled obligations and held collateral, and must remain usable
by native repayment/accrual/release commands after cutover. CLOSED requires zero
remaining recorded settlement components, evidenced full return and schedule
termination, and exclusion from live portfolio monitoring. A zero balance alone
does not establish closure. A source snapshot cannot hide intervening events.

## Concrete implementation findings

- Live disbursal invokes `assert_approved_quotes_current`; market-valued historical
  loans cannot safely be replayed through that command.
- Live repayment computes allocation using `timezone.localdate()`. Full release
  also composes current settlement and `allocate_release_number`. Neither is a
  historical replay API. Pure calculations and canonical selectors are reusable.
- Event recording deduplicates a payload fingerprint under a loan lock. Historical
  source event identity/order requires a separate explicit provenance contract;
  equal-valued payments must not be collapsed merely because they look alike.
- Local read-only PostgreSQL inspection on 2026-09-12 found **no non-internal
  triggers** on PawnLoanEvent, PawnLoanApprovalSnapshot, PawnLoanDisbursalSnapshot,
  PawnLoanRelease, RepaymentScheduleVersion or RepaymentObligation. PawnLoan had
  its licence-revision guard. Python immutability methods, FKs and RLS are not
  evidence that same-Workspace raw UPDATE/DELETE is denied. This is a prerequisite
  gap, not a reason to bypass SQL protection for imports. This inspection did not
  attempt destructive DML and does not claim to audit every Loans table.

## Implementation and acceptance

The evidence-protection prerequisite is now implemented by Loans migration 0008
for fifteen append-only tables, including direct and parent-derived loan/Workspace
reference checks. See the [guard decision](../adr/2026-09-12-loans-history-evidence-guards.md).
Mutable loan/collateral state remains available. Updates that clear actor references
are also denied; hard deletion cannot silently remove evidence attribution.
The earlier inspection above records the pre-migration finding, not current coverage.

The mapped-setup historical command, executable schema, staged preview, explicit
commit and canonical export are implemented locally. Acceptance fixtures include an active partially repaid loan
and a fully released loan of the same supported structure, plus missing-evidence,
wrong-Workspace, duplicate/retry, same-day ordering and late-failure cases. A
representative external source must be checked for required evidence before claiming
compatibility with a particular vendor; no vendor sample has been supplied here.

This document does not authorize a production deployment or production data import. The optional Party
history filter remains [FW-006](../plans/future-work.md#fw-006-party-bundle-history-progress-filter).

Validation failures now expose structured categories without changing this wire
contract or any admission predicate. Original exception messages remain available;
upload/review also displays the category. See the
[classification decision](../adr/2026-09-13-portability-validation-classification.md).
