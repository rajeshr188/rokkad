---
status: reviewed-no-production-changes
owner: loans
updated: 2026-10-16
tags: [monitoring, coverage, jcl, evidence, operations]
related: [../architecture/monitoring-worker-lifecycle-and-scaling.md, ../flows/loan-health-monitoring.md, loan-boundary-release-20261016.md]
---

# JCL coverage diagnosis after the combined Loans release

This is the pre-amendment observation. The owner's subsequent 16 October request
has now changed JCL's Workspace monitoring choice to calculated metal value through
an explicit v2 amendment; see the
[amendment and release record](calculated-monitoring-default-20261016.md).
The later [represented-position implementation](represented-position-coverage-20261016.md)
also supersedes the origin-based coverage recommendation below: optional book
assurance is separate from a usable accepted position. Its local changes require
deployment; the dated counts here are not a new production observation.

The owner requests a durable worker reference and explanation of incomplete JCL
valuation/transaction coverage. A restricted-role, repeatable-read/read-only
production inspection on 16 October 2026 returns only aggregate counts, categorical
settings and quote dates. No loan identifiers, borrower details, balances, prices
or document contents are exported. No assessment, review, quote or policy is
changed. These are dated observations, not a live dashboard or continuing audit.

## Observed position

| Measure | Count |
|---|---:|
| Active ordinary loans | 2,717 |
| Current V11 assessments | 2,717 |
| Stale / failed / unassessed | 0 / 0 / 0 |
| Usable current financial calculations | 2,717 |
| Usable collateral coverage | 341 |
| Current assessments without usable collateral coverage | 2,376 |
| Transaction coverage complete under ordinary capture assumption | 339 |
| Transaction coverage provisional | 2,378 |
| Missing recording-basis result | 0 |

All 2,376 unavailable current coverage results report **MISSING_APPRAISAL**.
Financial calculation and assessment freshness are complete. This is no longer
V11 backlog lag; another unchanged refresh cannot supply an appraisal.

The 2,378 provisional book results consist of **2,377 UNCONFIRMED** and **one
BEHIND**. Only one active loan has any saved transaction review. The 339 complete
results use SYSTEM_CAPTURE_ASSUMPTION, not external verification of paper books.

## Why an appraisal is still required

Both active licence groups (2,153 and 564 loans) resolve the Workspace monitoring
policy. Its current valuation choice is ORIGINAL_AGREEMENT: preserve each loan's
saved method. The policy permits IN_VAULT/WITH_FUNDING_LENDER, with seven-day
rate and ninety-day appraisal freshness limits.

| Saved/effective method | Active loans |
|---|---:|
| Latest appraisal | 2,377 |
| Lower of calculated metal value and appraisal | 340 |

One latest-appraisal result and all 340 lower-of results have usable coverage at
this snapshot. The remaining 2,376 latest-appraisal loans lack the required
appraisal. Supporting calculated metal valuation in application code does not
automatically change an owner's effective monitoring-policy choice. The release
preserves policy and original lending evidence.

## Recorded metal inputs and quotes

All observed active items are in the vault. Aggregate field checks find no null,
non-positive or out-of-range net-weight/purity values. This is structural
validation, not confirmation that the recorded physical measurements are true.

| Metal | Items | Distinct loans containing that metal |
|---|---:|---:|
| Gold | 1,856 | 1,854 |
| Silver | 872 | 872 |
| Bronze | 9 | 9 |

Loans can contain multiple metals, so these loan counts overlap. Usable reference
lookups find gold/silver quotes effective on 16 October 2026 (08:59:06 and 08:59:10
UTC respectively). Bronze returns MISSING_RATE. Application support for bronze is
deployed; a usable live bronze quote remains absent in this snapshot. No quote
amount or source is invented in this review.

## Supported remediation choices

First decide which valuation the business intends to use. Both paths preserve
borrower terms and original approval evidence:

1. Keep appraisal-based monitoring and obtain/record actual approved appraisals
   meeting the effective policy for the missing cohort. Lower-of requires both
   appraisal and metal-price evidence. A refresh alone is not an appraisal.
2. For suitable metal collateral, explicitly amend the current monitoring choice
   to **Current calculated metal value** in **Loans setup -> Calculation, fees and
   monitoring -> Monitoring policy history -> Amend**. Both current licence groups
   use the Workspace default; review the displayed scope, reason and effective
   date. Do not create an overlapping unrelated policy or rewrite frozen loans.

For the second choice, staff should verify retained net weights are grams and the
purity/material basis is appropriate, particularly for imported and bronze items.
Maintain usable dated buying quotes for gold, silver and bronze. The nine loans
with bronze items would still lack calculated coverage without a usable bronze
quote. Mixed-item loans need all required items supported; partial item sums must
not masquerade as full-loan coverage. Then allow normal reassessment and review
any remaining reasons. The aggregate checks make this a plausible route for most
of this portfolio, not certification of physical evidence or a guaranteed final
count without reassessment.

Valuation coverage being complete means the system can assess every active loan's
collateral position. It does not mean every loan is well secured: a measured
shortfall can have complete coverage evidence. Preserve those risk findings.

## Transaction coverage is a different task

An unchanged financial calculation cannot establish whether a paper receipt was
never entered. For each relevant loan, **Check paper transactions** retains a
reviewer, source reference, checked-through date, source fingerprint and choice
about future recording. Staff must actually check the represented position.

For a migrated opening loan, the review starts at its accepted opening checkpoint.
It does not require reconstructing unavailable pre-checkpoint receipts. Check the
accepted position and subsequent activity through the review date; preserve the
earlier-history limitation.

For JCL loans whose future activity is entirely in Rokkad, a complete check through
today can select **Every future transaction entered directly in Rokkad**. Supported
ordinary activity can then continue that review without a new daily paper check.
Later paper entry, historical correction or changed reviewed facts can require
another review. Continuing paper/mixed capture must retain its actual checked-
through date; provisional status between paper entry/review batches is honest.

The current UI establishes these reviews per loan. A future bulk confirmation for
a genuinely checked migration cohort could reduce staff work, but would need a
defined scope, accepted checkpoints, source/cutover attestation, audit/authority,
per-loan fingerprint and successful retry semantics. It must not silently mark all
imported loans complete or infer capture practice solely from entry origin.
No bulk confirmation or automatic review is implemented/authorized here.
The [staff guide](../flows/loan-health-monitoring.md#confirm-the-represented-position-and-future-recording)
now records the exact current navigation and fields, why a review is needed, and a
controlled bulk-confirmation proposal with per-loan source checks, audit and bounded
retry semantics. The owner's later calculated-value choice does not itself confirm
transaction capture; no cohort is marked complete by this documentation.

## Refresh and efficiency conclusion

The current worker selects outdated results, but date-based currentness makes all
continuing active loans due on a new day. It does not fully recalculate already-
current loans on every five-minute poll. The dated snapshot above proves JCL's
catch-up has completed; the two incomplete dimensions need the distinct evidence/
policy and book-review actions above, not more worker containers.

The [worker reference](../architecture/monitoring-worker-lifecycle-and-scaling.md)
documents the complete lifecycle and a proposed small shared pool, indexed due
scheduling and safe source-dependent calculation reuse. These are proposals,
not new deployed behaviour. Source, currentness, RLS, posting and alert correctness
must be preserved before changing daily refresh semantics. The shelved large-scale
test is not resumed and no worker/resource setting is changed by this review.
