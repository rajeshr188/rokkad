---
status: active
owner: project
updated: 2026-06-17
tags: [implementation, contact, migration]
related: [../domain/contact.md, ../archive/contact/CONTACT_MODEL_MIGRATION_GUIDE.md]
---

# Contact Model Migration

Contact model work moved toward clearer field naming, database constraints, document validation, and separated loan summary reads.

## Direction

- Use named `UniqueConstraint` declarations.
- Add database-level constraints for one default address/contact/picture per customer where supported.
- Keep document normalization and masking in value services.
- Keep Girvi loan summaries out of `Customer` model methods.

Archived contact migration sources are preserved in [archive/contact](../archive/contact/).
