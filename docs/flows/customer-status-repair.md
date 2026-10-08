---
status: active
owner: project
updated: 2026-10-08
tags: [party, loans, operations]
---

# Existing customer status repair

The owner requested ACTIVE customers when any loan was created against them, and
INACTIVE customers when none exists, across JCL, JSK and Lakshmi. This counts all
ordinary loan states, including closed loans and drafts: customer activity is not
a statement of outstanding debt.

Retained closed-loan evidence counts only through an exact Workspace source alias.
For the accepted legacy import, use its bound installation UUID and source schema
to transform `contact_customer:<source-id>` with the same UUID5 algorithm as Party
admission. Never match borrower names or equate old database IDs with local Party
IDs. Other sources require their exact accepted source-system/external-ID alias.
No loan is admitted or financial history reconstructed by this repair.

Run `repair_customer_statuses` with the restricted runtime settings, explicit
`--workspace-id` and authorized `--actor-id`. Without `--apply`, it emits aggregate
counts and a digest, without customer names, numbers or contact details. Applying
requires `--apply --expected-digest <preview-digest>`. Changed loan relationships,
aliases, historical borrower references or customer statuses invalidate the preview.
Unresolved historical borrowers or blocked/archived/merged customers prevent apply
and require review. The actual three-Workspace inventory has neither exception.

The Loans service uses ordinary Django transactions, Party edit permission and
matching Workspace context. Apply locks the Workspace's customers and changes only
`status`, `updated_by` and `updated_at`; each change records `PARTY_STATUS_CHANGE`
with actor, object, before/after and recorded-loan-history reason. Audit failure
rolls back the entire Workspace repair. No financial writer, schema, loan, event,
document, source alias or media change is involved. Repeating a fresh preview
after success should show zero candidates.

Before production, rehearse against the approved isolated actual-source stage,
retain private before/after evidence on the server, verify nonstatus Party fields
and loan/source fingerprints, and validate a recent operational backup. Run the
audited repair in an ephemeral derivative of the current web image; the web
container and background readers do not need replacement for a data-only repair.

This is an explicit correction of existing customers, not a new automatic status
policy or a restriction on registering new customers before their first loan.
Normal staff status controls and credit holds remain separate.

The 8 October production repair completed at 10:31 IST after the actual-source
stage rehearsal and checksum/catalogue validation of the current backup. It
activated 393 customers and deactivated 214, with 607 status audits. Final
ACTIVE/INACTIVE counts: JCL 4,428/1,463, JSK 640/13, Lakshmi 2,104/3. All 4,689
historical-only customers count as having loans. Search membership and second
previews pass in all three Workspaces, with exact preserved contact, loan and
source fingerprints. The private server evidence child is `party-status-feecbb58/`;
the production web container was not replaced or restarted.
