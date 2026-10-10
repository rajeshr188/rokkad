---
status: accepted
owner: project
updated: 2026-10-10
tags: [onboarding, billing, workspace, authorization]
related: [2026-10-10-guided-business-setup.md, 2026-09-29-selected-public-trial.md]
---

# Configure a business before activating commercial access

Following the approved guided setup work, the Owner reported that creating a
Workspace immediately redirected to billing instead of allowing configuration.
Creation already returned the setup URL; subscription middleware redirected its
next request because no Subscription existed.

Permit the canonical owner of an active recovery-only Workspace to use an
explicit reviewed list of configuration routes before subscription activation.
This includes the setup journey, business identity, licence/numbering, products,
calculation policies, Rates and document/print configuration. GET, HEAD and POST
are the supported methods; normal CSRF, view/service permissions and matching
Workspace/RLS context still apply. Use exact route names, not path prefixes:
the Loans setup namespace also contains funding, notices and financial actions.

The activity remains recovery-only. Do not start a trial, grant full access,
create payment evidence, alter trial allowance or bypass required owner consent.
Loan/customer entry, imports, funding, portfolio operations, borrower messaging
and team expansion remain subject to their existing commercial checks.
The setup review presents an explicit activation link before lending.

The exception applies only while the activity policy returns recovery with no
subscription. Read-only restrictions, expired/cancelled/past-due subscriptions,
access-decision restrictions and operational lifecycle boundaries remain stronger.
Staff, administrative members and nonmembers do not acquire initial-setup access
through this exception. After normal activation, their existing roles apply.

The previous public-trial decision's statement that Workspace creation grants no
access continues to mean no commercial lending access. Configuration now forms
part of its recovery surface; public trial consent and one-owner allowance are
unchanged. There is no new stored activity mode, entitlement, table or migration.

See the [business setup flow](../flows/business-setup.md) and
[implementation record](../implementation/guided-business-setup.md).
