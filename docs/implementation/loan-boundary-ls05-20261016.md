---
status: verified-locally
owner: loans
updated: 2026-10-16
tags: [loans, monitoring, presentation, verification]
related: [../adr/2026-10-16-consistent-monitoring-disclosures.md, ../plans/loan-boundary-simplification-20261016.md]
---

# LS-05: consistent risk and evidence presentation

Local work follows the authorized sequence. Preserve prior LS-01 through LS-04,
committed undeployed financial/collateral corrections, deployed Party-merge code
and unrelated WhatsApp setup documentation. No production access or release.

## Implementation

- Extend existing evidence-quality reads and shared disclosure for live versus
  saved basis, advisory cause/severity, recording expectation and independent
  financial / valuation / transaction checks. Reuse current book reviews; their
  fingerprints, signatures and future-capture prerequisites remain unchanged.
- Loan detail passes its actual live results to the disclosure. Failed full
  financial projection can retain the independent collateral observation. Its
  current appraisal display excludes future-effective and correction-invalidated
  versions, using the valuation cutoff where available.
- Loan health rows use the same disclosure and suppress unsafe saved amounts.
  Stale advisory is reference-only; failed assessment does not imply healthy risk.
- Share aggregate evidence guards between dashboard and portfolio. Invalid JSON
  money/reconciliation cannot enter one total while being excluded from the other.
  Four independent dashboard completeness checks distinguish refresh needs,
  financial failures, valuation gaps and incomplete/unknown recording basis.
- Current operations timestamp uses the existing freshness helper. No recalculation
  on aggregate GET, per-portfolio-loan risk read, new worker or posting command.
- Preserve V11 and all published profiles/schema. This slice changes disclosure
  and consistent eligibility for displayed totals, not the saved risk formula.

## Verification

The wider **311-case regression passes** in **330.190 seconds**. After final
presentation refinements, all **203 final affected cases pass** in **136.479
seconds**, including the targeted browser case. The initial 49-case development
selection also passed. These selections overlap and are not a combined unique count.

Checks cover live/saved separation without snapshot writes, independent observation
on financial failure, advisory interpretation, per-loan capture/review suspension,
unknown recording basis, invalid/non-finite/out-of-range JSON money, SQL/per-loan
eligibility agreement, absent reference limit, closed-loan disclosures, future
appraisal exclusion, one-query dashboard, repayment/eligibility screens, notices,
restricted-role boundaries, corrections, original documents and portable/exact
recovery. Financial posting, review signatures, source history, V11 and alerts
retain their contracts.

**Ten desktop/phone states pass** at widths 1365 and 390: live detail, independent
observation, mixed current/failed portfolio, dashboard and transaction review.
Checks use fictional Django responses, intercepted network requests and cached
assets through [the targeted script](../../scripts/check_monitoring_evidence_layouts.py).
The browser activates the real loan tab/disclosure controls. Evidence remains in
Overview and collapsed by default, rather than displacing loan identity. Final
representative captures are visually inspected; layout/visibility/overflow and
UTF-8 currency checks pass. Captures are in ignored `outputs/loan-boundary-ls05`.
No live data or external messaging is involved.

Django system/migration checks, tracked/new-source import boundaries, documentation
links and whitespace checks pass. No model change is detected. The exact isolated
`test_rokkad_ls05_20261016` database is removed after verification and its absence
checked. Ordinary development and production data remain untouched.

This completes LS-05 locally. LS-01 through LS-05 and separate pending corrections
await coordinated release. LS-06 measured invalidation/worker review is next;
performance-mechanism changes still require evidence that they are warranted.
