---
status: proposed-direction
owner: project
updated: 2026-10-14
tags: [loans, architecture, origination, paper-entry, corrections]
related: [ordinary-loan-domain-review-20261005.md, ../adr/2026-10-05-unified-loan-admission-and-continuation.md, ../plans/loan-continuation-consolidation.md]
---

# Origination review after the active paper borrower correction

The owner asks why a borrower-entry correction touched many components and whether
one business can start direct lending under licence A / series AA at AA05001 while
gradually entering original paper loans AA00001 through AA05000. The desired
business is mixed current lending and historical admission under one register,
with ordinary servicing afterward. This review records current source findings
and a proposed consolidation direction. It does not authorize a model rewrite,
new products/calculations, production rollout or a real loan/numbering change.

## What the current architecture supports

The operational foundation is already shared: PawnLoan, Party, collateral,
financial events, obligations, lifecycle and Workspace isolation. The accepted
5 October admission/continuation decision and later LC/LO work explicitly separate
performing an action now from recording an already completed action. Modern
direct/paper/reviewed-opening monthly agreements share the anniversary helper and
captured rounding policy. Earlier audit findings must not erase these delivered
improvements.

The numbering mechanics support the AA example:

1. Configure AA with prefix AA, width 5 and a maximum covering future lending.
2. Reserve the historical counter through 5000 with a reviewed source reference;
   reserve_sequence_through sets next_number to 5001 without creating loans.
3. Ordinary allocation issues AA05001 and advances next_number to 5002.
4. Completed recording claims an original number such as AA00001 or AA05000.
   claim_number checks existing ordinary/import/archive identities and locks the
   sequence. Its same-series counter adjustment applies only when the entered
   number is at or above next_number. Lower backlog numbers leave it unchanged.
5. Continue current lending and admit earlier loans in any entry order, using
   their actual agreement dates and supported financial history/positions.

This is structural capability verified by source inspection, not an inspection
of any real A/AA configuration or a new end-to-end test of all 5,000 loans. Existing
numbering tests cover reservation, allocation, repeated reservation and refusal
to rewind. Historical admission still needs truthful source/licence mapping and
a supported contract/position; range reservation does not attest book completeness.

There is a setup presentation gap: ordinary LoanSeriesSetupForm and
configure_sequence expose prefix/width/maximum but no starting counter or historical
reservation action. The existing last-used-counter screen is tied to verification
of a legacy licence reference. A business adopting Rokkad should have an ordinary
administered **Existing register used through 5000; next number 5001** action using
the existing reservation service. Creating a false legacy licence or placeholder
loans to advance the counter would be an inappropriate workaround.

## Where complexity remains

### Entry provenance still selects contract/recognition adapters

selectors/servicing_contract.py and selectors/continuation.py provide common
reads, but still select native-monthly-policy/2, recorded-anniversary/1-3 and
opening checkpoint profiles, with NATIVE_PERIODS, RECORDED_CUMULATIVE and
OPENING_CHECKPOINT recognition. Compatibility with immutable earlier records is
necessary. The long-term contract for new equivalent agreements should be chosen
by actual economics and the known financial-history boundary, rather than paper
versus direct entry. Shared arithmetic alone does not consolidate persisted
recognition, correction and export behavior.

### General origination is narrower on the completed-recording path

recorded_history._make_contract accepts non-amortising monthly bullet/flexible
products. validate_input limits advance periods and agreement/evidence shapes.
These are honest supported boundaries; they do not establish that recording an
already completed agreement intrinsically needs different products from current
lending. Wider origin support needs shared supported agreement validation with
purpose-specific approval/evidence requirements. It cannot accept arbitrary source
calculations without enough facts to reproduce their debt.

### Corrections remain separated by origin and operation

Draft update, recorded terms/receipts/settlements and the new paper borrower
correction each have dedicated applicability rules. The borrower correction safely
preserves finances, but deliberately refuses native/opening origins and connected
renewal/funding/auction graphs. It adds an immutable identity revision in
LoanChangeLog; it does not finish general loan correction.

A familiar **Correct loan** flow should classify the fields actually changed and
the dependencies actually affected. Identity transcription, economic restatement
and custody fact correction require different effects. Changing borrower on a
linked renewal can affect both agreements, so a connected review may be necessary;
the original entry channel alone should not decide eligibility. A preparation
draft can be editable even when the business action already happened on paper;
confirmed financial evidence still cannot be edited in place.

### New correction evidence is not a first-class exchange contract

The borrower log retains former/current Party IDs in JSON. Published servicing
profiles map one current borrower per loan and cannot safely remap both. The
bounded fix consequently refuses those exports/imports; exact recovery preserves
both Party prerequisites. This is a concrete integration cost of adding a local
correction shape after existing exchange contracts were defined.

The target should have one supported agreement/correction evidence shape with
explicit mappable Party/source references, consumed by ordinary reads, documents
and exchange. Choose whether existing snapshot/log fields suffice or a small
ordinary Django revision record is justified after inventorying those requirements;
do not preselect a generic revision framework or another financial ledger.

## Proposed target

Keep one operational loan and existing services. Separate these facts explicitly:

| Fact | Meaning |
| --- | --- |
| Agreed contract | Principal per item, interest rule, payment structure, tenure, rounding, deductions and agreed dates |
| Financial admission basis | Known original timeline, verified outstanding checkpoint, or verified closed position |
| Action purpose | Perform now, record a completed action, or correct recorded facts |
| Source evidence | Original number/reference, provenance, original business date/precision, entry actor/time and genuine prior approval if supplied |
| Current evidence/readiness | Transaction coverage, present custody, monitoring valuation and authority for the requested next action |

Current approval enforces today's applicable lending rules for a new advance.
Historical recording validates actual supported facts without fabricating approval
or requiring old destination quotes. Checkpoint admission explicitly limits the
known history. Once admitted, common operations use the saved contract, position
and relevant evidence; the source remains visible for audit.

## Smallest coherent next sequence

1. Add the ordinary existing-register reservation flow using reserve_sequence_through.
   Characterize direct AA05001, interleaved paper AA00001/AA05000, next AA05002,
   duplicate identities and concurrent admission/allocation.
2. Establish a current origin/purpose/contract/operation/correction capability
   matrix from real admission paths. Extend existing four-origin characterization
   tests with the owner's mixed-register and borrower-correction cases.
3. Consolidate the supported modern agreement evidence and correction references.
   Keep old published profiles readable; use an explicit new version where the
   wire meaning changes, with a tested two-Party remapping/recovery contract.
4. Present common preparation/review and **Correct loan** flows backed by concrete
   existing commands. Preserve source-specific validation at admission and
   impact-specific compensation/reconciliation after confirmation.
5. Extend genuinely needed products/calculations individually through the shared
   agreement path, requiring equivalent economic/servicing outcomes across entry
   sources. Do not invent broader business rules from the AA example.

The acceptance scenario must include current repayment on a previously recorded
paper loan, a later completed paper receipt on a direct loan, once-only interest,
truthful checkpoint limits, source/document retention, borrower authority changes,
connected dependencies and safe exchange. Success means equivalent evidenced
agreements yield equivalent supported behavior, while source uncertainty remains
visible. Existing events are preserved rather than bulk converted by migration.

## Scope and evidence

### Monitoring boundary clarified in the follow-up

The owner asks whether consolidation simplifies origination without disturbing
later risk monitoring/assessment. The intended outcome preserves the existing
monitoring engine and effective monitoring policies while consolidating its loan
inputs. Current risk reads already use continuation/obligations for exposure/DPD,
current collateral valuation and independent transaction coverage. Thus an
origination refactor can indirectly affect risk even when risk.py is unchanged.
Preservation must be measured, not assumed from an unchanged classifier.

The acceptance contract is equal semantic outputs for equal agreement, position,
evidence, policy and reporting date: recorded balances, eligible unposted interest,
economic exposure, unpaid obligations, DPD, maturity, collateral value/LTV,
evidence completeness, risk classification and alert/recovery decisions. Source
IDs/timestamps/provenance remain legitimately different. Missing history or
valuation cannot gain confidence simply because entry paths are consolidated.
ORIGINAL_AGREEMENT monitoring must keep its existing saved method/limit meanings,
including recorded choices that are not proof of original valuation.

Use existing four-origin characterization as the baseline, add the mixed-register
and correction journeys, consolidate reads before persistence, and compare old/new
read results without posting money or alerts. Existing events, approvals, schedules
and issued artifacts remain preserved. No automatic economic conversion or
monitoring-policy amendment is part of structural consolidation. Genuine changes
to facts may appropriately change risk through the existing invalidation flow.

If new evidence changes consumed source fingerprints or the assessment contract,
invalidate affected projections and perform the ordinary today-only refresh.
Readers in web and worker must understand the same new evidence before new writes
are enabled. A refresh or new provenance version is distinguishable from changing
the risk rules. Loan position and source coverage remain explicit; checkpoints do
not acquire invented pre-cutover transactions.

Reviewed current source on 14 October: recorded_numbers, number_allocation,
license_series/license_continuation/license_forms, recorded_history and paper
defaults, servicing_contract/continuation/eligibility, four-origin characterization,
the new borrower correction and its exchange boundary, plus current ADRs/domain
and LC/LO plans. The initial review changed documentation only. The owner later
approved [implementation](../implementation/loan-origination-consolidation-20261014.md),
with local code and isolated verification. Production setup and rollout remain
separate.
