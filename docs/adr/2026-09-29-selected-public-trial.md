---
status: accepted
owner: project
updated: 2026-09-29
tags: [billing, onboarding, trial, entitlements]
related: [2026-09-28-private-operator-billing-catalog.md, ../plans/public-workspace-trial.md]
---

# Select one public trial independently of the paid catalog

The approved offer is 30 days for one owner and five staff, without a card or
automatic charge. Enabling the previous trial flag published every active plan,
including the private transition trial and monthly pilot. Those plans must remain
unchanged and unavailable through direct trial-start requests.

Use `BILLING_PUBLIC_TRIAL_PLAN_ID` (default zero) with the existing trial switch.
Only that active, unbound, zero-price/zero-annual-price, 30-day, six-member Plan is
eligible for public trial presentation and acceptance. Missing or changed terms
fail closed. There is one offer, so no new publication table or plan-state system
is needed. The paid catalog still requires its separate checkout switch and lists
positive-price plans. Recurring agreement consent remains independent.

The owner must have a verified sign-in email and explicitly submit the current
terms version. The service requires matching Workspace context and active canonical
ownership, including after locking the Company row. Platform authority cannot
accept another owner's trial. Existing subscription, recurring-agreement or access
decision history excludes the Workspace; a trial is not an access-reset mechanism.
Existing members and pending invitations must fit six seats before acceptance.

Reuse the locked `start_trial` service, BillingAccount, entitlement projection and
SubscriptionEvent. New trials set `auto_renew=False`. The event records the actor,
exact trial end and accepted version/terms. No provider call, mandate, invoice or
payment is created. Workspace creation grants no access; eligible onboarding moves
to consent, then back to the selected Workspace's team step. Repeated or concurrent
acceptance cannot extend access. Existing seven-day grace/read-only policy applies.

Seat resolution uses Django's installed-app registry for `apps.subscriptions`;
the old short-name check incorrectly bypassed capacity. Invitation reservation,
membership creation and acceptance serialize on Company before checking capacity.
Direct member additions count reserved invitations; an existing member retry adds
no seat. The trial and invitation paths share Company-first lock ordering.

This implementation is prepared locally. Publication still needs a separate Plan,
deployment and browser acceptance with both payment switches off. Existing plans,
customers and production activation flags are not changed by this decision.
