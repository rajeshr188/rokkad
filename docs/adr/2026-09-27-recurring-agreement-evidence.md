---
status: accepted
owner: project
updated: 2026-09-27
tags: [billing, subscriptions, razorpay]
related: [2026-08-17-workspace-lifecycle-and-billing-boundary.md, ../plans/subscription-monetization-rollout.md]
---

# Recurring agreements are separate from purchased access

FW-019 requires recurring billing without losing the existing Orders evidence or
paid-through dates. A provider mandate is permission to collect; it is not a paid
term. The legacy Subscription provider-ID/auto-renew fields are insufficient to
retain creation uncertainty and previous mandates.

Add three ordinary Django control-plane models: `RecurringPlanBinding` freezes
the local plan's amount, tax, currency, monthly/yearly cycle and entitlements
against a provider plan and mode; `RecurringAgreement` records a Workspace's
creation attempt and verified provider identity/status; `RecurringAgreementEvent`
retains append-only actor/reason evidence. Like Invoice and WorkspaceAccessDecision,
these are global billing evidence with explicit Workspace authorization, not
tenant business tables. No generic CRUD/default model permissions are exposed.
PostgreSQL guards prevent rewriting commercial/attempt identities or deleting
their history. A partial unique constraint reserves one open agreement per
Workspace, including attempts whose provider outcome is unknown.

Commit the UUID attempt and Workspace reservation **before** a provider POST.
The command owns separate Workspace transactions and refuses an enclosing
transaction (including HTTP Workspace middleware). A timeout, malformed response,
crash or local persistence failure leaves the durable attempt reserved. Repeating
its key never reissues creation. The operator must locate the original provider
ID and reconcile through a provider GET matching the UUID/Workspace notes,
frozen plan, quantity and cycle count. A missing search result is not proof that
creation failed; do not release the reservation automatically. Reads have bounded
timeouts; creation has no retry. No raw credentials or provider body are audited.

The first increment is operator-only and Test Mode only, behind a default-off
flag. A platform administrator binds catalog plans; a canonical Workspace owner
or platform administrator can create/reconcile. Duration is an explicit bounded
command argument, not a selected launch term. No customer notification or Checkout
authorization is sent. New immediate agreements reject live keys, non-active
Workspaces, occupied seats beyond the frozen offer, outstanding manual invoices,
and existing paid/trial time or legacy mandates requiring a scheduled transition.
These exclusions remain visible review requirements, not automatic migrations.

Manual Orders purchases and capture recheck the same Workspace reservation under
the Company lock. Already-paid replay remains available. Reconciliation can record
a terminal provider status but cannot release the reservation until subsequent
cycle/cancellation work proves all financial evidence settled. It changes no
Subscription dates/status/auto-renew, entitlements, invoices, payments or receipts.

Next increments will grant access only from independently verified paid invoice,
payment and cycle evidence; preserve paid time on collection failure/cancellation;
and add customer authorization, renewal recovery and confirmed cancellation.
There is no production migration, offer publication or activation in this decision.

Provider contracts checked 2026-09-27:
[create subscription](https://razorpay.com/docs/api/payments/subscriptions/create-subscription/),
[fetch subscription](https://razorpay.com/docs/api/payments/subscriptions/fetch-subscription-id),
[fetch plan](https://razorpay.com/docs/api/payments/subscriptions/fetch-a-plan).
Razorpay requires a plan and total cycle count; notes carry our attempt identity.
These references establish API shapes, not successful recurring acceptance.
