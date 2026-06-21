---
status: active
owner: project
updated: 2026-06-18
tags: [domain, contact]
related: [../implementation/contact-model-migration.md, ../domain/girvi.md, party.md, ../adr/2026-06-18-party-domain-model.md]
---

# Contact

The contact app currently manages `Customer` records, addresses, contact methods, documents, pictures, and account-related identity data.

The long-term external entity model is Party. See [Party](party.md) and the accepted ADR [Adopt Party As The Long-Term External Entity Model](../adr/2026-06-18-party-domain-model.md).

## Boundary

- Contact owns the current compatibility `Customer` profile data.
- Party will own the long-term flexible entity model.
- Contact should not directly query Girvi internals for loan summaries.
- Loan exposure and borrowing summaries should come from selectors/facades such as `CustomerLoanSummary`.
- DEA account provisioning should remain behind DEA facade helpers.

## Migration Direction

- Keep `contact.Customer` stable until existing Girvi, Sales, Purchase, DEA, Approval, and Notify references are migrated.
- Add a nullable `Customer.party` bridge during implementation.
- Backfill existing customers into Party records.
- Convert `customer_type` into roles/segments:
  - Retail -> Party role `CUSTOMER`, segment `RETAIL`
  - Wholesale -> Party role `CUSTOMER`, segment `WHOLESALE`
  - Supplier -> Party role `SUPPLIER`
- New accounting-sensitive logic should prefer party-aware account resolution after the bridge exists.

## Data Integrity Direction

- Named database constraints are preferred over legacy `unique_together`.
- Default address/contact/picture uniqueness should be enforced at the database level where possible.
- Aadhaar/PAN validation, masking, and duplicate proof detection should live in dedicated value services.

Archived contact sources are preserved in [archive/contact](../archive/contact/).
