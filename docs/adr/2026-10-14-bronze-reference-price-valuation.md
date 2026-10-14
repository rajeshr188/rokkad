---
status: accepted
owner: project
updated: 2026-10-14
tags: [rates, monitoring, collateral]
related: [2026-09-11-rate-quote-evidence.md, 2026-10-12-current-monitoring-valuation-policy.md]
---

# Bronze uses the shared reference-price calculation

The owner selected current calculated metal monitoring for suitable JCL loans and
requested bronze price/calculation support for the nine remaining bronze pledges.
BRONZE collateral and Bronze quotes already exist in the model enums; no new
commodity subsystem or tenant table is needed.

Extend the existing Rates facade and dated origination eligibility to BRONZE.
The unchanged calculation is buying price per gram times recorded net grams times
the recorded percentage / 100, with existing rounding. A bronze reference quote
prices the quoted bronze material at the 100% reference grade. It is not a pure
copper quote, karat purity or an inferred alloy composition. The existing `24k`
storage key remains the compatible 100% reference key; UI explains the bronze
meaning. No existing prices, recorded percentages or original valuation evidence
are converted or rewritten. Actual live prices require a real reviewed source.

Bronze uses ordinary quote creation, dated selection, correction, withdrawal,
actor-attributed unchanged-price confirmation, source provenance and forced RLS.
Freshness, custody, loan exposure and lower-of/appraisal evidence requirements
remain. Missing/stale bronze quotes yield unknown coverage. Add bronze to paper
collateral validation and optional standing interest setup; do not substitute a
gold/silver interest rate or create an unrequested bronze policy.

Current monitoring retains its existing Workspace/licence scope and four methods.
The selected metal-only choice also replaces current lower-of monitoring within
its scope; it does not alter original agreements, principal, interest or postings.
Supporting bronze removes the need for a special non-precious exception workflow
for this cohort. Unusable records still need genuine corrections/evidence, and
paper transaction completeness remains independent.

Testing also exposed stored currency quantum trailing zeros being treated as
extra valuation precision. Normalize the saved quantum before quantizing current
metal value: a stored 0.0100 means paise, not four decimal places. This retains
the intended policy rounding and original evidence; it changes no financial entry.

V9 identifies the expanded current calculation and corrected precision contract so earlier snapshots are
outdated even if dated today. Matching web/worker deployment and ordinary bounded
reassessment are required; no risk result is marked usable merely by upgrading.
No schema migration is introduced by this support. Business package v3 retains
the existing explicit monitoring choice and already-supported metal enums.
