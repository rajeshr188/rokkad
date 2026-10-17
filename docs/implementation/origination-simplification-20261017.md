---
status: active
owner: project
updated: 2026-10-17
tags: [loans, origination, configuration, corrections, verification]
related: [../plans/origination-simplification-20261017.md, loan-origination-friction-review-20261017.md]
---

# Origination review, configuration and preparation recovery

The independent implementation was prepared on
`work/origination-simplification-20261017`, based on `ed585f33`, following the
owner's recommended order. It is now integrated with closing and deployed as
`a14b5a7f`; original worktrees and unrelated WhatsApp work remain preserved.
Deployment performs no customer correction, setup amendment or messaging activation.

The owner subsequently authorized the [combined closing integration/release](loan-workflow-release-20261017.md).
That record owns the combined candidate and production status; this document
retains the independently verified origination implementation checkpoint.

## Review the agreement and its source

The existing shared final review now explains simple/compound interest, actual
part-month rule, minimum first month, upfront deduction/coverage, captured
rounding, anniversary boundary and compound capitalization interval. Borrower
code, relation and phone distinguish customers. Current direct preparation shows
the actual resolved calculation/rate/fee scope, effective period and revision;
item overrides retain their explanation. Saved approvals show their frozen rules.
Retained historical-native review uses its existing cutoff-bound source resolver.
Actual-paper review shows its source agreement rather than a current setup claim.

New combined-review tokens include a signed presentation snapshot. A failed stale
confirmation can explain changed facts/rules before a fresh review. The existing
fingerprint, actor/date/loan/Workspace binding, proof keys and exactly-once payout
checks remain authoritative. Issued old reviews still follow their original path.
Presentation metadata cannot authorize or change a financial calculation.

## Review standing setup changes

Calculation configuration and series rate-only actions now preview before saving.
The review shows before/after terms, the full proposed calculation, scope/date
range, potentially affected draft/saved-agreement counts and narrower overrides.
Counts describe potential overlap; superseded versions may appear in the bounded
override list, with full policy history still available. A scoped calculation
policy overrides the complete broader policy; rate-only changes use their own
existing writer and retain unselected metals and calculation policy.

Confirmation requires explicit acknowledgment and a 30-minute signed review bound
to the actor, Workspace, exact values, current date and economic/rate/fee state.
Under the existing Workspace lock it revalidates and calls ordinary policy writers.
A PreferenceAuditLog marker records the outcome atomically. An identical authorized
retry returns that outcome; changed values/authority cannot reuse it. Setup changes
do not correct saved agreements or amend monitoring. No table/migration is added.

## Recover a mistaken unposted register/product

Eligible draft detail offers **Replace mistaken draft**. Review the correct running
series, product, date, tenure, expected number and recalculated proceeds. Confirmation
creates an ordinary draft, moves original unposted item/photo identities using the
existing draft movement helper, appends linked history and cancels the original in
one transaction. Both reserved numbers survive; there is no approval, payout,
physical movement, refund or financial correction. The replacement needs ordinary
review before lending. Existing photo bytes, IDs and capture facts remain intact.

Source/input/product/setup/photo/expected-number changes require a fresh review.
Posted history, linked renewals, funding reservations/pledges and custody movement
hold this shortcut. Failed creation/cancellation rolls back number allocation,
item movement and both drafts. Identical retries return the original result.
Borrower/collateral/agreement correction pages also identify supported next steps
for connected renewal, funding, auction, custody and source-contract holds.

Replacement metadata retains an opaque source reference. Exact recovery preserves
both drafts, all retained logs/media and local links. Portable servicing preserves
source-local preparation evidence; it does not pull a cancelled preparation into
the financial graph or treat its source IDs as destination loan IDs. Local links
require matching Workspace and source loan identity. Financial wire profiles and
their published meaning remain unchanged.

## Actual contract capability boundary

The owner confirms all paper agreements in these businesses use full monthly
interest. No weekly paper contract is required for this delivery. A shared concrete
predicate keeps dated paper defaults and setup disclosures aligned. Unsupported
rules do not silently become full-month terms. Direct origination remains available
with its actual supported saved rules; financial correction limits are disclosed
before confirmation instead of being discovered only after a mistake.

| Saved/source agreement | Admission and ordinary servicing | Financial correction | Recovery/limits |
| --- | --- | --- | --- |
| Simple full-month direct policy 2, supported bullet/flexible product | Existing native approval and period recognition | Existing reviewed agreement correction and supported receipt/settlement replay | Existing immutable revisions, documents, risk invalidation and bundle 7/8 |
| Simple full-month recorded-anniversary/3, zero/one upfront month, paise/rupee rounding | Actual paper evidence, existing cumulative recognition | Existing shared agreement correction and recorded replay | Existing source identity, history and portable/recovery contracts |
| Simple started-week direct policy 2 | Existing direct calculator keeps started 7-day blocks and captured first-month rules | Financial replay remains held by the monthly correction boundary; borrower/collateral facts retain independent gates | Saved rules are never converted; a new replay profile needs compensation/document/portability tests |
| Other direct rules or legacy/native policy 1 | Existing saved-rule/product/period prerequisites apply | Concrete supported profile only; legacy native is bounded to an unserviced disbursal | No automatic upgrade or substitution |
| Verified migration opening | Existing supported checkpoint continuation, not invented full history | Existing checkpoint review | Retains unknown earlier transactions and original/cutover distinction |

Completed weekly release compatibility is supplied by the jointly verified,
deployed [closing integration](loan-workflow-release-20261017.md), using the
existing saved-rule full-release calculator. Broader weekly paper
admission or financial replay, if later required, needs explicitly versioned source
and recovery contracts. Removing a monthly guard alone is insufficient.

## Validation

The following retains the independent local verification checkpoint. Joint tests,
exact-source CI and production acceptance now pass in the linked release record.
All tests below use a dedicated localhost `.test` database and synthetic facts:

- **368 regression tests pass** across origination, setup, partial-month rules,
  draft UI, agreement/borrower/collateral correction, completed payouts and paper
  history. These include compensation, documents, unchanged monitoring meanings,
  direct/paper monthly parity, portability and exact recovery.
- **88 final tests pass** on the completed candidate (overlapping that regression
  set): signed/stale/expired/actor-bound review, scoped configuration, concurrent
  confirmations, atomic draft/media/number rollback, actual RLS DML under a
  restricted role, exact replacement recovery/retry and contextual HTTP holds.
- The offline browser test checks **18 page/viewport combinations** at 1440 and
  390 pixels, covering nine actual Django responses. No horizontal page overflow
  or JavaScript errors occur. All browser requests are intercepted; selected
  desktop/mobile captures are also visually inspected. The reusable check is
  `scripts/check_origination_simplification_layouts.py`; fictional captures and
  `checks.json` are in ignored `outputs/origination-simplification-20261017/`.
- Ruff passes across maintained Python; Black passes for all 24 changed Python
  files using Python 3.14 settings. AST comparisons establish formatter-only
  equivalence. Ignored `.tmp/format-review/format-only.patch` compares baseline
  formatting separately from `behavior.patch`, which compares formatted baseline
  with the implementation. Raw Git diffs include substantial existing formatting.
- Current documentation links, all 22 preserved originals/reading copies, supported
  app boundaries, repository hygiene and `git diff --check` pass. Test logs are
  ignored `.tmp/origination-regression.log` and
  `.tmp/origination-final-verified.log`; the latter exits zero with 88 passing tests.

No schema migration, financial wire-profile change, production/customer mutation
or large-scale worker/performance run is part of this work. The original review
and corrected operator guide are retained alongside the implementation.
