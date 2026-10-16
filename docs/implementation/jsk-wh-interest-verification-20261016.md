---
status: verified
owner: loans
updated: 2026-10-16
tags: [loans, interest, production, verification]
related: [../domain/loans-regulatory-setup-and-policy.md, linode-production-cutover.md]
---

# JSK WH gold interest verification

The owner requests verification that every WH gold loan uses 1.1% monthly after
the series override replaced the inherited 2% Workspace default. This task
authorizes verification, not a financial correction or retrospective repricing.

## Method and scope

Production check completed at 13:51:56 UTC on 16 October 2026. Run the diagnostic
inside the deployed web image using its restricted runtime role; assert no
superuser/RLS bypass and use a repeatable-read, read-only transaction with explicit
JSK Workspace context and a 30-second statement timeout. Resolve WH by its number
prefix: series 9, code LINODE-2, name Legacy WH. Return only policy metadata,
aggregate counts and bounded exception identifiers; no borrower/contact details,
item descriptions, monetary balances or source documents are returned. The
ignored local helper/report are `.tmp/jsk-wh-rate-audit-20261016.py` and `.json`.

Compare stored collateral rates with current disbursal tranche evidence or the
effective, validated migration-opening evidence. Separately inspect retained
migration source item rates and older closed-position source classifications.
No application code, production settings, loans, postings or policy rows change.

## Results

The standing gold rate resolves correctly to **1.1%**, policy 13 effective
30 September. The original WH override is policy 9, effective 25 September and
created that day at 06:44 UTC. Workspace policies 3 and 11 retain 2%; series
precedence selects the WH override.

| Loans with operational gold items | At 1.1% | At 2% | Total |
| --- | ---: | ---: | ---: |
| Active | 175 | 826 | 1,001 |
| Closed | 15 | 77 | 92 |
| Total | 190 | 903 | 1,093 |

Every gold item rate matches its effective frozen opening/disbursal tranche.
The 915 imported-opening loans comprise 14 active loans at 1.1%, 824 active at
2% and 77 subsequently closed at 2%. **Their retained original source item rates
match these saved rates**; the imported 2% cohort is not established as a new
Workspace-default substitution by this audit.

Two early Rokkad-origin active loans, **WH02145 and WH02146**, retain 2% and item
policy 3. Their drafts were created before the WH override; their current approved
disbursal evidence also retains 2%. The remaining 176 Rokkad-origin gold loans
have item contracts at 1.1% (161 active, 15 closed).

WH02291 has a derived header rate of 1.100001%, matching rounded monthly interest
divided by gross principal. Its item and frozen tranche rates are exactly 1.1%.
This is distinct from the 903 genuine 2% contracts.

There are also **1,227 older imported closed positions** without operational
collateral rows or a loan-level interest rate. Retained source items classify
1,226 as gold and one as silver. Their gold source items contain 57 rows at 1.1%
and 1,176 at 2%; these are **item counts**, not loan counts. They cannot be
certified as uniform 1.1% contracts. Do not fabricate operative agreements for
these already-closed positions merely to populate a rate field. One other active
WH loan has non-gold items and is outside the gold-rate comparison.

## Follow-up boundary

The expectation that all existing WH gold loans are at 1.1% is not met. Standing
setup changes affect subsequent applicable approval/recording; they do not
rewrite admitted agreements. A correction must distinguish erroneous original
terms from a later agreed rate reduction, establish its effective date and review
affected interest, receipts and settlements. Preserve retained source evidence
and previously posted records. No correction or deployment is performed here.

## Active-cohort correction feasibility and owner clarification

The owner subsequently asks whether all 826 active exceptions can safely be
corrected and confirms **1.1% was the correct agreed rate from each original loan
date**, not a prospective rate reduction. Retain this owner clarification
separately from the unchanged legacy source rows, which still contain 2%.

A second restricted-runtime, repeatable-read/read-only production check completes
at 14:03:06 UTC on 16 October. It returns only contract/dependency aggregates and
the two previously identified native loan numbers. No write-capable preview or
correction service is executed. The ignored helper/report are
`.tmp/jsk-wh-correction-feasibility-20261016.py` and `.json`.

- The cohort remains exactly 826 active WH gold loans at 2%.
- All 824 imported loans retain `loan-opening-review/2`. Existing checkpoint
  correction supports review/4 and /5, not this legacy collection contract.
- The two native loans retain calculation-policy version 1. The current native
  agreement correction requires version 2, so they also need compatibility work.
- The imported loans have only their migration-opening event; the native loans
  have only their disbursal event. There are no recorded subsequent repayment,
  accrual, settlement, reversal or other financial events in this cohort at this
  check. This is not proof of absent paper activity before or after migration.
- None of the 824 meets the existing checkpoint-correction contract predicate.
  No imported loan is additionally flagged for connected custody, renewal,
  funding or auction dependencies by the inspected prerequisite predicates.
- 685 imported checkpoints contain nonzero recognized/unpaid opening interest.
  A rate-field replacement alone would leave their accepted positions inconsistent
  with the owner's corrected original-terms instruction.

The deployed image lacks the newer read-only `opening_correction_blockers` helper;
the diagnostic uses explicit equivalent profile/event/dependency predicates for
the imported cohort and the deployed native `correction_dependencies` reader.
Passing those prerequisites alone would not establish successful writer replay.

### Recommended sequence, not yet implemented or applied

1. Freeze the exact active cohort and source fingerprints; preserve the owner's
   original-date instruction as the correction basis. Exclude closed loans,
   silver items and already-correct 1.1% loans.
2. Extend the ordinary audited correction services for the retained opening/2
   and native policy-1 contracts, retaining their existing anniversary, rounding
   and partial-period rules. Do not upgrade economic rules merely to pass a guard.
3. Establish corrected checkpoint interest/continuation/obligations from the
   supported contract and available evidence. Surface any unresolved historical
   payment/advance uncertainty. Do not fabricate pre-cutover receipts or simply
   multiply every saved balance by the rate ratio.
4. For the native loans, preserve actual payout/advance-interest cash facts and
   explicitly review any difference resulting from correcting the original rate.
   A rate correction is not evidence of another payout or a refund.
5. Rehearse on an isolated restored copy, showing old/new collection positions
   and dependency exceptions, and verify retry safety, original-source retention,
   reports/documents, exports and monitoring invalidation. No production preview
   that writes and rolls back is implied by this read-only audit.
6. Once the exact correction is reviewable and authorized, use a verified backup,
   recheck/lock source fingerprints, record bounded audited corrections, verify
   the postconditions and refresh monitoring. Reclassify any loans with new
   activity rather than forcing them through the previously prepared cohort.

Current conclusion: the correction is feasible to prepare, but **the existing
bulk/correction implementation cannot yet safely apply it to these 826 loans**.
No runtime change, production correction, deployment or commit is made by this
feasibility review.
