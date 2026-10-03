---
status: active
owner: project
updated: 2026-09-30
tags: [domain, subscriptions, monetization]
related: [../flows/workspace-onboarding.md, ../plans/backlog.md]
---

# Subscriptions

Owner monthly self-service is implemented locally with publication off by default.
One explicitly selected recurring binding exposes INR 1,499/month for the owner
plus five staff and at most twelve collections, independently of the private
annual/one-off catalog. A verified canonical owner must accept a signed current
offer; active trials must expire first. Consent and the durable provider attempt
commit together before provider creation. Unknown outcomes require recovery, never
a second mandate. Existing billing/access-exception history requires support review.
See the [self-service decision](../adr/2026-09-30-owner-monthly-self-service.md).
Production activation and the first real payment remain pending.

The first current recurring capture may convert an expired trial to its frozen
paid plan when the trial ended before agreement creation and period start, the
Workspace is active and within seats, and there is no legacy mandate or earlier
invoice/cycle history. Trial dates stay unchanged; exact paid dates and prior
terms are audited atomically with payment and receipt intent. Future or conflicting
payments remain under review. This is not early trial conversion or a general
paid-plan replacement. See the [decision](../adr/2026-09-30-expired-trial-first-recurring-payment.md).
This correction was deployed on 30 September with new paid authorization disabled.

Operator catalog preparation is private while checkout and trial signup are both
paused. The owner catalog then links to the Workspace's prepared recurring agreement,
whose frozen terms remain visible independently. Live binding also requires trial
signup paused. The deployed selected-trial code publishes only Plan 3, the
explicitly selected eligible free offer;
paid catalog publication still requires the separate checkout switch.
Legacy feature claims and estimated overage charges are no longer presented as
commercial terms. Stored limits and invoices are unchanged. See the
[catalog publication decision](../adr/2026-09-28-private-operator-billing-catalog.md).

New live offers require an explicit reviewed seller name/address, unregistered
tax status and zero tax rate for the selected pilot. The base rate has no default;
Test Mode explicitly retains its illustrative rate. The issuer is frozen into new
checkout/binding snapshots and inherited by recurring invoices. HTML/PDF/receipt
rendering uses saved evidence only; old invoices do not acquire a new seller or
no-GST claim. Current seller changes block new authorization but preserve existing
payment recovery. Registered-supplier treatment is not implemented. See the
[seller decision](../adr/2026-09-28-frozen-billing-seller.md).

Platform operators can now preview or register a known live provider plan against
the frozen local offer, with matching explicit live credentials, both purchase
switches paused and no conflicting test/unclassified billing evidence. Preview is
read-only; registration saves only the catalog mapping. See the
[catalog preparation decision](../adr/2026-09-28-live-recurring-catalog-preparation.md).

Immediate-start recurring creation, owner authorization, verified paid cycles,
cancellation and explicit held/refund access review now support matching live
configuration through the same services as Test Mode. New live authorizations
require the default-off gate, a webhook secret and clean mode evidence. Pausing
that gate preserves existing mode-matched recovery and cancellation. Scheduled
live starts and live reservation release remain unavailable; no production billing
is activated by this local implementation. See the
[live workflow decision](../adr/2026-09-28-mode-matched-live-recurring-workflows.md).

Billing requires an explicit configured provider mode with matching keys. New
one-off invoices freeze mode; recurring invoices inherit their saved plan binding.
Historical unclassified records cannot be silently processed as live purchases.
Test receipt previews are labelled and normal SES dispatch refuses test/unclassified
payments. Configuration checks never certify launch readiness. See the
[mode decision](../adr/2026-09-28-explicit-billing-provider-mode.md).

Operator Test Mode preparation supports an optional immutable scheduled start.
The owner sees the exact time; authorization/token payment grants no access.
Every provider observation must match the schedule and no paid period may precede
it. A passed start blocks new authorization of a still-Created agreement, while
recovery and cancellation remain available. This is not prepaid/trial conversion.
See the [scheduled-start decision](../adr/2026-09-28-scheduled-recurring-test-start.md).

Fully refunded recurring invoices now use the existing explicit owner billing
review with fresh provider and local refund evidence. Retaining access changes
no dates; ending access requires a verified ended mandate and the exact current
refunded cycle, with no other unreturned future/current paid periods. Neither
decision issues a refund or releases the agreement reservation. See the
[refund-review decision](../adr/2026-09-28-recurring-refund-access-review.md).

A separate operator command can release the reservation after a cancelled
immediate-start Test Mode agreement is fully refunded and reviewed, with access
ended and no unresolved payments. It preserves history and grants no access. A new
agreement still requires a new durable attempt and verified payment; its exact
period can replace a longer refunded historical term after matching release review.
Scheduled tokens and unreturned paid periods remain blocked. See the
[release decision](../adr/2026-09-28-refunded-recurring-reservation-release.md).

The subscriptions domain manages company subscription plans, access checks, monetization flows, and navigation visibility.

## Selected public trial (enabled 2026-09-29)

The public offer is 30 days, owner plus five staff, no card and no automatic
charge. An explicitly selected zero-price Plan and the trial switch are both
required. A verified canonical owner accepts versioned terms; private plan IDs,
existing billing/access history and over-capacity Workspaces are refused. Each owner
account may accept one public trial Workspace. The original acceptance event keeps
that allowance consumed after expiry, ownership transfer or catalog replacement;
an internal transition trial does not consume it. Existing
trials remain unchanged. See [the trial decision](../adr/2026-09-29-selected-public-trial.md)
and [trial operations](../plans/public-workspace-trial.md). Production free trials
are enabled. The planned INR 1,499 monthly continuation needs separate consent
and paid-billing launch acceptance.

## Direction

- Subscription access should be company/workspace aware.
- Navigation should reflect subscription entitlements consistently.
- Onboarding should guide users into required subscription/setup states without hidden blockers.

Archived subscription sources are preserved in [archive/subscriptions](../archive/subscriptions/).

Current paid flow: [Workspace checkout](../flows/subscription-checkout.md). This
records one-off paid terms; remaining recovery/provider acceptance is tracked
in [project hardening](../plans/project-hardening.md).

The owner selected [FW-019's active rollout](../plans/subscription-monetization-rollout.md)
on 2026-09-26. The unpublished working offer is INR 1,499/month or INR 14,990/year
per Workspace, owner plus five staff (six total members). Display actual annual
savings against twelve monthly payments and show trial offers only when enabled
and eligible. Operator-only Test Mode agreement preparation now records frozen
provider plans and durable creation/recovery attempts. It grants no access.
Verified recurring paid cycles now record exact provider-invoice periods once,
with atomic invoices, payments, applicable access changes and receipt intent.
Future periods record the received money with access held for separate review;
existing subscription fields and entitlements stay unchanged. Neither reaching
the start date nor rechecking the invoice automatically applies held access.
The owner page, invoice and receipt explain this, and older agreement review
payments remain visible. Operators can now apply eligible started/unexpired holds
through an explicit owner/platform-authorized review command with reason, current
subscription revision and fresh payment/refund checks. It records an immutable
resolution; original payment evidence stays unchanged. Conflicting/newer terms,
closed agreements, inactive Workspaces and expired holds remain blocked. Owner
pages show the historical resolution and direct users to Billing for current access.
Naturally due provider acceptance remains open. Failures and
mandate cancellation do not revoke already-paid time; expired periods follow the
same grace/read-only policy. Pending/Halted owner notices explain collection trouble
separately from paid access and direct recovery through the existing agreement.
Status recovery alone does not establish payment; only verified paid invoice
evidence records a recovered cycle. Owners can now authorize prepared Test Mode agreements,
refresh status, recover a known paid invoice and request cancellation of future
renewal. The cancellation request commits before delivery; uncertain outcomes
remain pending, and paid dates stay unchanged. Preparation remains operator-only,
new authorization is default-off and real recurring provider acceptance remains
before publication/activation. See the
[agreement runbook](../implementation/recurring-agreements.md).

Annual recurring invoice validation also accepts the exact next-calendar-anniversary
midnight IST boundary for elapsed durations strictly between 364 and 365 days,
as observed in actual Test Mode. Provider start/end timestamps are retained; this
never invents extra access or bypasses the future-period hold. See the
[boundary decision](../adr/2026-09-28-annual-invoice-calendar-boundary.md).

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
