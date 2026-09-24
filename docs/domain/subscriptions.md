---
status: active
owner: project
updated: 2026-09-24
tags: [domain, subscriptions, monetization]
related: [../flows/workspace-onboarding.md, ../plans/backlog.md]
---

# Subscriptions

The subscriptions domain manages company subscription plans, access checks, monetization flows, and navigation visibility.

## Direction

- Subscription access should be company/workspace aware.
- Navigation should reflect subscription entitlements consistently.
- Onboarding should guide users into required subscription/setup states without hidden blockers.

Archived subscription sources are preserved in [archive/subscriptions](../archive/subscriptions/).

Current paid flow: [Workspace checkout](../flows/subscription-checkout.md). This
records one-off paid terms; remaining recovery/provider acceptance is tracked
in [project hardening](../plans/project-hardening.md).

## Access after expiry

Natural trial or paid-term expiry now enters seven days of normal-access grace,
measured from the original expiry timestamp. After that, existing records, reports,
saved documents and permitted exports remain accessible in read-only mode. New
lending, repayments, releases, imports, configuration changes, new document issuance
and notification dispatch are unavailable. Cancelled/past-due/explicitly expired
stored states enter read-only directly. A trial ending is not labelled payment debt.
Membership and normal role permissions still apply to every permitted read/export.

Expiry warnings, grace deadlines, temporary access and read-only status appear in
the Workspace. Staff are told to contact their owner, rather than being redirected
into owner-only Billing. Owners retain billing recovery access. Suspension and
archive are separate deliberate lifecycle decisions; expiry never sets them.

## Platform administrator extensions

Open **Workspace settings > Billing > Platform access controls** as a platform
administrator. Select temporary normal access, temporary read-only restriction,
or return to the normal subscription policy. Record a reason and a future expiry
for temporary decisions. The form displays its time zone. Ordinary owners and staff
cannot grant access; Django staff status alone is insufficient.

The latest decision replaces earlier decisions. Its expiry returns to the current
subscription policy without additional grace. An older, longer grant never returns.
A restriction continues across renewal until lifted or expired. Use a new decision
to correct/revoke an earlier one; saved history cannot be edited or deleted.

The operator equivalent, under runtime settings, is:

```text
python manage.py set_workspace_access --workspace-id ID --actor-id PLATFORM_ADMIN_ID --mode full --until YYYY-MM-DDTHH:MM:SS+05:30 --reason "Approved interim access"
python manage.py set_workspace_access --workspace-id ID --actor-id PLATFORM_ADMIN_ID --mode default --reason "Return to subscription policy"
```

For a Workspace with no Subscription, normal access additionally requires an active
`--plan-id ID`; its entitlement projection is captured. Existing subscriptions keep
their stored entitlements and override expiry. No decision fabricates a subscription,
invoice or payment or changes purchased dates. A grant never overrides suspension,
archive, membership, actor permissions or RLS. Expired no-subscription grants leave
existing records readable; a brand-new Workspace without a grant remains recovery-only.

## Interim payment readiness

`BILLING_CHECKOUT_ENABLED` defaults to false. New checkout/order routes are disabled
and owners are directed to the platform administrator for interim access. Existing
payment confirmation, reconciliation, webhook and invoice routes remain available
with their existing verification and permissions. Enable new purchases only after
deployment-specific provider acceptance, not merely because API settings are present.

Servicing-only restrictions (allow collections/releases while blocking new lending)
remain future work. This release implements full/grace/read-only, not that extra tier.
