---
status: active
owner: party
updated: 2026-10-08
tags: [party, search, defaults, operations]
---

# Repair missing customer search defaults

Borrower search displays the Party primary phone and a default address. Existing
nonprimary contact methods and nondefault addresses are retained but not displayed
as the selected contact details. The explicit repair fills missing selections
without replacing existing choices, editing contact/address text or inventing
missing facts. It does not verify identity, phone reachability or current residence.

Run under the restricted application role, with one explicit Workspace and an
authorized Party-edit actor. Preview first:

```text
python manage.py repair_party_display_defaults --workspace-id WORKSPACE_ID --actor-id ACTOR_ID
```

The aggregate-only JSON includes a source digest and candidate/missing-data counts.
No customer names, phone values or address text are printed. Apply that exact
preview using `--apply --expected-digest DIGEST`. Changed sources require a fresh
preview. Each customer commits independently, so an interrupted repair reports
how many completed; preview again before resuming. Repeating against a fresh
preview is safe and preserves choices made by staff in the meantime.

The Party service locks and rereads each customer, promotes only missing choices
and synchronizes an empty primary-phone summary. Every change records the
authorized actor and object in AuditLog without duplicating contact/address text.
An audit failure rolls back that customer's changes. Existing default/primary
constraints, source aliases and issued documents remain intact.

For production, verify a current database backup and rehearse in the approved
isolated copy. Keep source snapshots and per-object repair evidence in the approved
private server location. Verify stored values/verification fields and preexisting
selections remain unchanged, plus actual borrower-search labels. Do not copy real
customer records into the local checkout or OneDrive.

Customers with no saved address or phone require the actual details to be entered.
This command does not introduce automatic default selection for future creation,
deletion or imports, and does not change customer status or search eligibility.
