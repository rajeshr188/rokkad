---
status: accepted
owner: project
updated: 2026-09-24
tags: [billing, workspace, access, cutover]
related: [2026-08-17-workspace-lifecycle-and-billing-boundary.md]
---

# Subscription access continuity before cutover

The owner approved a pre-cutover increment: administrator extensions, seven days
of normal-access grace after natural trial/paid-term expiry, then read-only access.
Servicing-only access and provider acceptance remain later work. Repayments and
releases are writes and are not permitted in this increment's read-only mode.

`effective_billing_state` remains the truthful commercial decision. The separate
`workspace_activity` policy combines lifecycle, the latest platform access decision
and billing dates. Natural expiry receives seven calendar days from the original
end timestamp. Cancelled/past-due/explicitly expired stored states do not receive
automatic grace. No scheduler or status rewrite is needed. Missing subscription
remains recovery-only unless there is a platform decision; an expired grant then
leaves read-only access. No deletion/retention automation is introduced.

Platform administrators can append a full-access extension, a temporary read-only
restriction, or a return-to-default decision. Dates are mandatory for extensions
and restrictions, with actor and reason recorded. Only the latest decision applies;
older grants never revive. An expired extension falls back to current subscription
policy, without adding grace to the extension itself. New verified paid terms can
restore access under the normal policy; a current explicit read-only restriction
remains until it expires or is lifted. No grant bypasses suspension/archive/RLS or
ordinary membership and permissions.

`WorkspaceAccessDecision` is global billing control-plane evidence, like
Subscription/Invoice, linked explicitly to Company. It is not a tenant business
table. Access is restricted by explicit Workspace/platform authorization, and a
database trigger prevents updates/deletes. Existing-subscription grants retain the
stored entitlements, including explicit overrides and their expiry. A grant without
a subscription requires an active Plan and captures its entitlement projection;
it does not invent a trial, subscription, invoice or payment. Read-only mode retains
the advanced-reporting read entitlement but removes write capacities/features.

HTTP read-only access uses an explicit reviewed route set, not GET alone. Core
lists/details/reports, saved document retrieval and supported exports remain
available. The existing loan/archive export POST+CSRF contracts remain intact.
Document issuance guards distinguish existing artifacts from new writes. Business
service gates cover Loans/Party/Rates mutations, portability admission, new document
issues, risk refresh and notification dispatch; trusted operator context checks
the same restriction. No-subscription internal provisioning remains permitted by
its existing explicit authorization; it is not exposed through ordinary HTTP.
Do not treat direct ORM/model access as a supported customer workflow.

RBAC remains independent. User-visible mutation controls and expiry messages use
activity policy separately. Staff are not redirected to owner-only Billing when
restricted. Owners can recover billing; only platform administrators can grant
extensions. An ended trial is labelled "Trial ended", not payment overdue.

New checkout routes are disabled unless `BILLING_CHECKOUT_ENABLED=True`; the default
is false until deployment-specific provider acceptance. Existing captured-payment
confirmation, webhook reconciliation and invoice access remain available, so
disabling new purchases cannot discard an in-flight payment. Platform access grants
are the interim path; they never mark an invoice paid or rewrite purchased dates.
