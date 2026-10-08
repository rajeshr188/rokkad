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

## Execution on 8 October 2026

Owner-authorized production repair completes at **10:17 IST** after 13 focused
tests and an actual-source rehearsal in the existing isolated server copy.

| Workspace | Address defaults filled | Primary telephone contacts filled | Empty phone summaries filled | Changed customer labels checked |
| --- | ---: | ---: | ---: | ---: |
| JCL | 3,245 | 1,211 | 1,211 | 3,442 |
| JSK | 407 | 317 | 316 | 409 |
| Lakshmi | 275 | 291 | 291 | 518 |

Production starts and finishes with restricted-role and no-context/cross-Workspace
checks. Existing default/primary choices and nonempty master phones remain intact.
Hashes of all other Party/address/contact columns remain exact. Search labels
are checked for every changed customer; 7,564 actor/object-linked audits correspond
exactly to the three change counts. Each second preview has zero candidates and
a fresh read-only census shows no remaining missing selections where details exist.

The rehearsal also compares full loan, loan-event and issued-document row hashes;
all remain exact. No Loans writer is invoked in production. Web is not restarted,
and no source alias, historical document, schema or media file is changed.

Missing facts remain separate: JCL lacks 1,908 addresses / 4,070 phones, JSK
36 addresses / 142 phones, and Lakshmi 0 addresses / 1,061 phones. Five additional
JCL/JSK customers have a master primary phone without a telephone child row;
their displayed master choice is already present and remains unchanged.

Operator commit is `dc49e1318d266dc3b6194cd5ca36ee43c06f75cd`, image
`rokkad:party-default-repair-dc49e131`, ID
`sha256:1249e5713e18d2bd1510d8bac92dea1efbb109d1e5bd4fe6ea2d370714acb90b`.
Only the Party service and repair command are added to the existing verified image;
the operator is not switched into web or background services. The pre-apply backup
passes checksum/catalogue validation, SHA-256
`420f79977a9bbc77d159add61a95196fce784f9088494cd4ae210727f94c9371`.

Private evidence is in the previously approved server directory
`loan-continuation-20261006-b69df6ab/party-defaults-dc49e131/`: `prepared.json`,
`production-backup-gate.json`, `completed.json` and the `evidence/` source snapshots,
preview digests and per-Workspace completion reports. Customer details stay there;
only aggregate reports are retained locally. Earlier unlogged selections are not
retroactively attributed to an actor, and imported verification is not asserted.
