---
status: accepted
owner: loans
updated: 2026-10-16
tags: [loans, origination, completed-payout, evidence]
related: [2026-10-14-origination-consolidation.md, ../plans/loan-boundary-simplification-20261016.md]
---

# Completed payout review follows action purpose

The owner approved LS-02 after the ordered origination/monitoring review. An
unpaid saved draft can have a genuine earlier approval without having a financial
origin. That approval is evidence to retain, not a reason to route completed-fact
recording through a new historical lending decision.

## Decision

Unpaid DRAFT/APPROVED loans share one completed-payout editor and two-step review.
Use saved identity, date, licence mapping, product and collateral. Staff correct
those facts through draft editing before this review. Capture the original
reference, recording explanation and actual deductions/net payout. Supply standing
defaults; retained approved amounts/precision take precedence. Missing setup must
be completed explicitly, never silently replaced with current lending prices.

Reuse recorded-history preview/admission, canonical numbering, one-origin checks,
source fingerprints and immutable recorded disbursal evidence. Concrete completed
payout commands build data under Workspace/loan locks; they do not create a second
posting engine. The same successful submission is idempotent. A recorded payout
does not itself certify completeness of later paper transactions.

Display genuine approvals with retained/missing/corrected/withdrawn quote status.
Require explicit acknowledgement when approvals exist and retain those reviewed
observations in the source proof. A correction or withdrawal does not substitute
today's quote and does not itself invalidate the fact of a completed payout.
Changed evidence between preview and confirmation invalidates the signed review.
Original approvals remain immutable and no retrospective approval is created.

This bounded profile preserves supported simple/full-month item economics,
deductions, net payout and rounding. Different agreed financial facts require
explicit reconciliation. Unsupported fees/calculation profiles remain held.
Use the canonical audited borrower-identity chain for a same-customer Party merge;
do not require a new approval just because the current Party link was consolidated.

## Authority and compatibility

Completed facts use the existing recorded-admission permissions: data.view,
data.create, data.edit and loan.disburse, with Workspace/lifecycle/commercial
checks. Prior approval does not add setup-administration or approval permission to
that factual action. Ordinary approval/disbursal keeps its existing authority and
current quote rules. Correction of posted/reversed history retains its separate
administration and graph guards.

New GETs for unpaid drafts use the common editor. Existing native signed POSTs
continue through their original command and strict evidence checks; existing
recorded-history POSTs retain their signed command. Do not reinterpret tokens or
automatically fall back after a failed confirmation. Fully reversed native
attempts keep their existing audited correction path; LS-02 does not readmit them
as unpaid loans or broaden supported financial graphs.

No schema or published financial exchange profile changes. New source proof is
additive immutable evidence. Verification and deployment remain separate; see the
[implementation record](../implementation/loan-boundary-ls02-20261016.md).
