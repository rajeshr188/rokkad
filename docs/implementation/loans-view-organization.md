---
status: active
owner: project
updated: 2026-09-11
tags: [loans, architecture, maintenance]
---

# Loans view organization

The Loans views portion of R12 is complete. `apps/tenant_apps/loans/views.py`
contains compatibility imports, rather than request-handler implementations.
Existing URLs and Python callers still receive the same decorated handlers.
Business rules remain in existing services, selectors, forms and domain code.

## Where to make changes

All paths below are relative to `apps/tenant_apps/loans/web/`.

| Responsibility | Module |
| --- | --- |
| Product catalog | `product_setup.py` |
| Economic, interest, fee and monitoring setup | `economic_setup.py` |
| License evidence, renewal and series numbering setup | `license_setup.py` |
| Print-profile creation, publication, assignment and preview | `print_profile_setup.py` |
| Layout setup, flow/overlay editors, assets, packs and preview | `document_layout_setup.py` |
| Shared preview asset loading | `document_assets.py` |
| Issued-document list, detail and stored artifact download | `document_issues.py` |
| Loan, repayment, release, auction and renewal PDF responses | `loan_documents.py` |
| Loan list, detail, primary action and event rows | `pawn_reads.py` |
| Shared loan lookup and display permission checks | `pawn_read_helpers.py` |
| Collateral photos/labels/scans, storage and physical verification pages | `pawn_custody_views.py` |
| Batch/single risk refresh | `risk_refresh.py` |
| Draft transfer to active license/series setup | `pawn_setup_actions.py` |
| Operational-notice retry for both licenses and custody | `operational_notice_actions.py` |

Earlier feature modules still own draft, financial, release, auction, renewal,
custody mutation, communication, funding, reports and operations handlers.
Other specialized endpoints already imported directly by URLs retain their modules.

## Dependency and compatibility rules

- Keep the existing `views.py` public handler imports and URL names stable.
- Feature modules must not import the compatibility file. Shared helpers belong
  in their own small module when more than one family needs them.
- Keep Workspace lookups and permission decorators with their handlers. Moving
  files does not authorize changing role grants, license scope or data isolation.
- Patch service dependencies in tests at the module where the handler uses them.
  Importing a service into the compatibility file does not redirect a handler's
  global lookup.
- Rendering, publication, document evidence and financial rules still belong to
  the existing services; the extraction does not change them.

## Verification and scope

The final extraction moved 56 functions into nine modules with identical function
and decorator ASTs. The compatibility file fell from 1,620 to 224 lines. Existing
route tests check decorated callback identity for all 136 canonical Loans routes.
Regression results are recorded in [Status](../STATUS.md).

This completes the selected Loans view cleanup, not every possible R12 refactor.
The broader [review](../architecture/2026-09-09-project-review.md) also identifies
orgs views and large model/form/renewal-service files. Those require separate
responsibility and dependency reviews; size alone does not justify splitting them.
Razorpay, optional license scoping and physical-device acceptance remain deferred
under the [hardening plan](../plans/project-hardening.md).
