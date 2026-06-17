---
status: active
owner: project
updated: 2026-06-17
tags: [domain, contact]
related: [../implementation/contact-model-migration.md, ../domain/girvi.md]
---

# Contact

The contact app manages customers, suppliers, lenders, borrowers, addresses, contact methods, documents, pictures, and account-related identity data.

## Boundary

- Contact owns party profile data.
- Contact should not directly query Girvi internals for loan summaries.
- Loan exposure and borrowing summaries should come from selectors/facades such as `CustomerLoanSummary`.
- DEA account provisioning should remain behind DEA facade helpers.

## Data Integrity Direction

- Named database constraints are preferred over legacy `unique_together`.
- Default address/contact/picture uniqueness should be enforced at the database level where possible.
- Aadhaar/PAN validation, masking, and duplicate proof detection should live in dedicated value services.

Archived contact sources are preserved in [archive/contact](../archive/contact/).
