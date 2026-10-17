---
status: active
owner: project
updated: 2026-10-16
tags: [loans, contract, corrections]
related: [../adr/2026-10-15-shared-agreement-financial-corrections.md, loan-servicing-bundle-v7.md]
---

# Original agreement correction contract, version 1

The shared `preview_agreement_correction` and `record_agreement_correction`
services select the financial-history treatment from retained canonical evidence.
They do not grant permission to overwrite completed events or perform a new payout,
repayment, refund, amendment or physical movement.

## Known timeline from origination

Inputs retain the existing bounded date/principal/monthly-rate/proceeds contract,
supporting reference, reason and request key. Multiple items require explicit
principal/rate rows whose totals reconcile. Known paper receipt splits require
review when the new principal allocation cannot retain them. Original proceeds
equal principal less captured advance interest and retained deducted fees.

Saved direct policy/2 simple/full-month bullet or flexible agreements retain native
monthly recognition. Unserviced active policy/1 simple/full-month bullet or flexible
agreements also retain their saved legacy period calendar/calculator and require
explicit reviewed original proceeds; later charges/payments remain blocked for
independent policy-1 correction. Their export requires servicing bundle 8.
`CORRECTED` disbursal snapshots point to the preceding
snapshot and genuine original approval. That approval is provenance, not approval
of the revised terms. The frozen policy is copied exactly. `agreement_revision`
on retained monthly calculation headers distinguishes replacement calculations
of the same contractual period; published old rows default to revision 1.
Advance consumption and period continuation use the current revision, while all
prior rows and lines remain immutable. Unsupported ordinary reversed monthly
charges remain held; a new revision is not a general bypass for manual reversal.

Recorded anniversary agreements retain their established compensation and replay
algorithm. The shared boundary wraps its signed review with the current loan and
collateral fingerprint. Existing lower-level paper commands keep their published
contract. A known timeline does not certify that every actual paper receipt was
entered; transaction completeness remains independent.

## Verified checkpoint

Inputs are the complete corrected `checkpoint` review, supporting reference,
reason and request key. Retained aggregate review/2 and shared monthly review/4
and review/5 checkpoints are supported. Aggregate checkpoints retain their
original-principal anniversary calendar, first-month-paid coverage and cumulative
HALF_EVEN whole-rupee rounding; they do not gain monthly-period carry fields.
Their corrected export requires [servicing bundle 8](loan-servicing-bundle-v8.md).
Source identities, mappings, original dates, cutover,
physical evidence and captured calculation rule remain unchanged. Original item
principal, remaining principal, rates, current-period bases, cumulative/current
recognized and unpaid interest, advance coverage and remaining obligations must
reconcile through the ordinary opening validator. Unknown history is not zero.

An append-only `OPENING_CORRECTION` event retains its original opening ID,
preceding checkpoint ID, preceding opening hash and values, corrected review,
actor and correction identity. Its balance effect is the difference between the
reviewed before/after checkpoint amounts. It is not another financial origin.
Readers retain exactly one `MIGRATION_OPENING`, resolve the correction chain and
link remaining obligations to its latest explicit correction source. Original
accepted import documents remain unchanged. Later ordinary servicing continues
from the corrected checkpoint. A checkpoint already containing financial servicing
or settlement requires a separately supported connected review.

## Impact, confirmation and dependent facts

Reviews expose current principal, interest, fees and total before/after, agreement
facts, per-item changes and affected receipt allocations where applicable. Actual
receipt amounts/dates are retained. Recalculation that overpays or contradicts
retained allocations fails atomically; it does not infer a refund or concession.

Signed reviews expire after one hour and bind the Workspace, loan, actor, normalized
request and relevant source/dependency facts. Confirmation rechecks authorization,
locks and evidence. Identical confirmed retries return the original correction;
changed facts under the same request key fail. Different concurrent candidates
cannot both apply to the same retained source.

Supported full native closure correction additionally reviews exact actual
settlement cash without changing the original release document, recipient, date
or custody events. Current release reads resolve its explicit settlement revision.
The existing supported paper closure and paired recorded renewal reviews remain.
Native linked renewals, funding, auctions, shared-batch closure, concessions and
unavailable financial profiles are not independently restated by this contract.

Existing issued bytes remain addressable. Current document copies disclose the
correction and receive a new source identity. Corrected financial facts invalidate
risk; policies, thresholds and current-valuation meanings remain unchanged.
New reminders bind a separate agreement identity. Delivery holds a former queued
notice after correction, including native loans without a paper transaction review.
Freshly reviewed risk reminders retain once-only identity and existing consent.
Compatible readers and the ordinary schema migrations must precede new writes.
