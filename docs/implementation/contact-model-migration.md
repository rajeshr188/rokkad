---
status: active
owner: project
updated: 2026-06-18
tags: [implementation, contact, migration]
related: [../domain/contact.md, ../domain/party.md, ../adr/2026-06-18-party-domain-model.md, ../archive/contact/CONTACT_MODEL_MIGRATION_GUIDE.md]
---

# Contact Model Migration

Contact model work moved toward clearer field naming, database constraints, document validation, and separated loan summary reads.

The current compatibility bridge links `contact.Customer` to the long-term Party model through a nullable one-to-one field. Existing business workflows still use `Customer`; the bridge lets new Party-aware services resolve the same entity without forcing an immediate operational migration.

## Direction

- Use named `UniqueConstraint` declarations.
- Add database-level constraints for one default address/contact/picture per customer where supported.
- Keep document normalization and masking in value services.
- Keep Girvi loan summaries out of `Customer` model methods.
- Keep `Customer.party` nullable until Girvi, Sales, Purchase, DEA, Approval, and Notify have migrated their references.
- Use `backfill_parties_from_customers --schema <schema> --only-missing` to resume or repair legacy customer links.

## Customer To Party Mapping

- Retail customers map to Party role `CUSTOMER` with segment `RETAIL`.
- Wholesale customers map to Party role `CUSTOMER` with segment `WHOLESALE`.
- Supplier customers map to Party role `SUPPLIER`.
- Customer contact methods, billing address, and proof identifiers are copied where available.

Archived contact migration sources are preserved in [archive/contact](../archive/contact/).
