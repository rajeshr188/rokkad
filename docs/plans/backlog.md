---
status: historical
owner: project
updated: 2026-06-17
tags: [plans, backlog]
related: [../ROADMAP.md, ../STATUS.md]
---

# Legacy backlog

New shelved ideas belong in [Future work](future-work.md). This older list is
preserved as historical input and has not been revalidated against the current
application. Several entries refer to retired Girvi/DEA/inventory modules; do not
resume them from this list alone. Review current status and accepted ADRs first,
then capture any still-relevant idea in Future work with its source link.

- Standardize Girvi lifecycle status language across models, transitions, templates, and tests.
- Audit remaining direct cross-app imports and reads; move them behind facades/selectors.
- Add DEA posting rule registration tests for every seeded voucher type.
- Revisit `Voucher.unique_posted_voucher_per_doc` if multiple event vouchers must post against one operational document.
- Decide whether `Voucher.fingerprint` is draft-nullable or assigned at draft creation.
- Expand tenant seeding and setup checks for rates, voucher types, accounts, and commodity/rate-source prerequisites.
- Revisit inventory stock movement posting to DEA.
- Review normalized catalog attribute design before expanding product variants.
- Continue notification V2 batching and workflow polish.
- Review invitation and allauth hardening plans before reviving them.
- Define and accept the separate-appraiser and dynamic PawnLoan collateral-risk
  workflow in [pawn-collateral-risk-and-appraisal.md](pawn-collateral-risk-and-appraisal.md)
  before implementing margin-breach alerts or changing overdue authority.

Archived source plans are under [archive](../archive/).
