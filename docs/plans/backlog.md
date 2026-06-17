---
status: active
owner: project
updated: 2026-06-17
tags: [plans, backlog]
related: [../ROADMAP.md, ../STATUS.md]
---

# Backlog

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

Archived source plans are under [archive](../archive/).
