---
status: accepted
owner: project
updated: 2026-10-17
tags: [loans, origination, corrections, policy, scope, review]
related: [../adr/2026-10-14-origination-consolidation.md, ../adr/2026-10-15-shared-loan-fact-corrections.md, ../adr/2026-10-15-shared-agreement-financial-corrections.md]
---

# Origination and correction friction review

## Scope and conclusion

Owner-requested source review on 17 October, against maintained `main` at
`ed585f33`, existing accepted decisions and the documented production boundary.
The separate uncommitted unified-closing worktree remains separate. This review
does not query production, change setup/agreements, or approve implementation.
Findings below describe observed code boundaries and inferred operator friction;
they are not claims of newly reproduced production incidents.

Keep PawnLoan, saved agreement evidence, canonical calculations and immutable
financial events. Improve prevention, agreement explanation and recovery within
the existing editor/review/Correct actions. Do not add another loan type,
correction chooser, configurable workflow framework or generic history rewriter.

## Current behavior worth retaining

- Direct entry saves a numbered DRAFT. SIMPLE owner review confirms approval and
  payout atomically; EXTENDED retains separate approval/disbursal permissions.
  Signed reviews already bind inputs/economics, actor/date and quote/photo rules;
  confirmation rechecks changes. An approved loan must return to draft before
  ordinary edits. Posted financial evidence is not edited in place.
- Completed paper entry shares the ordinary editor/review presentation but uses
  source admission, actual original date/number, per-item terms and source facts.
  It does not invent original digital approval or confirmed physical cash.
  Opening imports retain their cutover balances and unavailable earlier history.
- Borrower, collateral facts and financial agreement corrections have distinct
  evidence/impact checks. Current projections and revised documents can change
  while old approvals, snapshots, issued bytes and transactions remain retained.
  A real subsequent payment, refund, top-up or handover is a business action.
- New economic setup versions do not rewrite saved approved/active agreements.
  Monitoring policy remains separate; changed financial/measurement facts make
  affected assessments stale and require the normal refresh.

## Findings

### O1: final review explains amounts better than complete agreement semantics

`templates/loans/pawn/_agreement_review.html:2` shows customer, series/number,
date, tenure, item principals/rates and proceeds. It does not consistently expose
the calculation method, partial-period/anniversary rule, rounding and each term's
resolved scope/version/date. `services/loan_workflow.py:45` already fingerprints
full economics and policy identities: stale-confirmation protection exists.
The gap is a common operator explanation and an intelligible before/after change
summary, not a missing signature/check mechanism.

Extend the current shared agreement summary and existing readers. Show the
important business terms before confirmation, with provenance in a disclosure.
If series, date, product or applicable setup changes, show the changed terms and
recalculated proceeds and require the existing fresh review. Show borrower code
plus useful distinguishing identity without adding another confirmation screen.

### O2: configuration precedence and override units are easy to misread

`services/economic_policies.py:248` resolves economics and metal rates independently
by series, licence, Workspace, applicable date and revision. Fees at line 306
resolve separately by code at licence/Workspace scope. Entry preference uses
today's scoped preference in `services/entry_purpose.py:7`; paper agreement
defaults use the original date in `services/paper_entry_terms.py:14`.

A series economic policy is a complete policy override, not per-field INHERIT.
Metal rates, fees and entry preference have their own resolution. Updating a
broader default can leave a narrower rate unchanged. Reusing a configuration to
change one field can also retain other copied values intentionally. Existing
setup does prefill current settings and offer explicit source-copy behavior;
do not describe it as always resetting to starter values.

Expose an effective setup preview for the chosen series/date: value, source,
scope, date, version and override. Prefer a narrow rate amendment for a rate-only
change; do not create a complete series override merely to change an entry
preference. No new operational preference table is proposed without concrete
need and a separate design review.

### O3: supported origination and supported correction are not the same set

`services/recorded_history.py:351` saves the routine recorded contract as SIMPLE /
FULL_MONTH. `services/paper_entry_terms.py:21` warns that dated setup outside its
monthly profile must not be substituted. Actual-term exceptions do not add a
started-week calculation field/profile to that admission path.

Direct configuration can offer other rules, including STARTED_WEEKS, while native
financial correction at `services/agreement_corrections.py:185` requires a saved
supported monthly contract. Legacy native correction is further bounded to an
unserviced history. The separate local completed-release fix does not extend
paper origination or financial-correction support.

Maintain an explicit tested capability matrix for the actual saved agreement:
admission, current/completed servicing, correction, connected history and recovery.
Show limitations early in administrator setup and before unsupported source
admission. Do not silently convert an actual weekly agreement into monthly
terms, or block every valid current advance merely because a later correction
capability is not yet implemented. Extend the concrete required contract next,
reusing existing calculators, with compensation/replay/recovery tests.

### O4: scope/product identity becomes fixed on the first saved direct draft

`services/pawn_drafts.py:183` allocates the official number at creation.
`forms.py:157` disables series/product on an existing draft, and
`services/pawn_drafts.py:253` preserves scope/product/number on update. Wrong
borrower, date, amounts and items remain ordinarily editable in a DRAFT; wrong
register/product is a different recovery case even before payout.

Show Workspace, licence/register, product and expected number before the first
save/review. Offer a guided same-Workspace corrected-draft replacement when
identity is already reserved: review/copy appropriate entered facts, allocate the
correct register's number and explicitly cancel/retain the old draft. Do not
silently move an official number, recycle it, move posted loans between scopes,
or cross Workspace isolation. A confirmed scope mistake needs a supported
administrative reconciliation with numbering/financial/custody dependencies.
Deferring number allocation is a separate design tradeoff, not required here.

### O5: corrections are protected but still leave operators to interpret holds

The existing Correct menu already separates borrower, collateral and agreement
facts. `services/borrower_corrections.py:63`,
`services/collateral_corrections.py:65` and
`services/agreement_corrections.py:154` enforce different dependency boundaries.
Renewal, funding, auction, custody and unsupported history can hold independent
corrections. These holds protect connected evidence; removing them would not
simplify the underlying business facts.

Improve the existing contextual actions: identify the mistaken field, show the
original/current/proposed facts, affected receipts/settlement/valuation/documents,
and whether it is supported. A hold should name the dependency and the supported
next action. Keep simple fact corrections out of financial replay. For an
original financial mistake reconcile the original proceeds and actual later
receipts; never infer a new payment/refund from a corrected difference.

### O6: economic setup lacks the monitoring setup's reviewed impact step

`web/economic_setup.py:140` saves valid calculation configuration directly;
monitoring at line 183 already has a reviewed amendment flow. Setup currently
prefills saved values and retains revisions/audit, but there is no equivalent
calculation-policy before/after impact confirmation in this handler.

Reuse that review pattern for significant rate/calculation/scope/date changes:
show intended fields, full resolved result, shadowing overrides and affected
draft/backfill date ranges. Explain that saved agreements remain unchanged.
An owner fixing a standing policy should be offered a separate scoped review of
potentially affected saved agreements, never an automatic mass correction.

### O7: linked correction guidance predates the shared agreement correction

At review start, `docs/flows/correct-a-disbursed-loan.md` described reversal,
reopening and re-disbursal as the sole path, although newer accepted decisions and
services support reviewed agreement correction. AGENT_MEMORY links that guide.
The guide is corrected during this review to explain existing by-impact rules
and support boundaries; its prior reversal/re-entry procedure is retained for
the applicable bounded case. It is not the default instruction for every
principal mistake. This documentation correction adds no command capability.

## Recommended delivery order (approved)

The owner approved this order and confirmed all current paper agreements use full
monthly interest. The [implementation](origination-simplification-20261017.md)
records the resulting scope and verification; weekly financial/source extensions
remain conditional on a concrete business need.

1. Keep the corrected operator guide aligned and complete the existing final agreement
   summary: identity, full calculation terms and scoped provenance. Add meaningful
   changed-term review using the existing stale-review safeguards.
2. Add reviewed effective-configuration amendments and explicit inheritance/impact
   explanations. Keep saved agreement corrections a separate authorized action.
3. Make existing correction actions explain field impact and exact holds; add
   guided recovery for a mistaken reserved draft scope/product.
4. Close the business-required capability gaps, starting with explicit monthly /
   started-week origination and correction parity where needed. Test each actual
   saved rule, source/history boundary, retries, dependency locks, compensation,
   documents, portability and unchanged monitoring-policy meanings.

Do not postpone the first three improvements for a wholesale contract rewrite.
Reuse the existing editor, summary, ServicingContract and concrete posting/correction
adapters. Financial truth and explicit unknown history remain the boundary.

## Verification boundary

This is source/document analysis, not a new live walkthrough or production audit.
No financial tests are claimed to have been rerun for this review. Documentation
links/preservation checks validate only the added review record and status entry;
future implementation needs its own targeted lifecycle and financial tests.
