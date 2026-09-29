---
status: preparation
owner: project
updated: 2026-09-29
tags: [onboarding, trial, invitations, billing]
related: [monthly-billing-pilot.md, ../flows/workspace-onboarding.md, ../architecture/control-plane-contracts.md]
---

# Public Workspace trial preparation

The owner selected preparation of a public free-trial offer on 29 September and
confirmed **30 days**, owner plus five staff, no card and no automatic charge.
Production Plan 3 is prepared and the local browser journey passed. The selection
and consent implementation is not deployed; public trial activation remains off.
Invitation-only email sending is now enabled independently of subscription billing.

## Selected offer and customer copy

| Item | Prepared terms |
| --- | --- |
| Duration | 30 days from the owner's explicit trial-start action |
| Capacity | One Workspace, owner plus five staff (six members total) |
| Payment details | No card or Razorpay mandate required |
| Automatic conversion | None; trial expiry cannot initiate a payment |
| Following offer | INR 1,499/month, only after explicit subscription consent and billing launch acceptance |
| Existing Workspaces | Their plans, dates, entitlements and access remain unchanged |
| Expiry | Existing seven-day grace/read-only policy applies; retain records and show the exact dates |

Proposed public copy:

> Try Rokkad free for 30 days with your team. Includes one Workspace for you and
> up to five staff. No card required and no automatic charge. Continuing on the
> monthly plan is INR 1,499/month and requires your explicit subscription consent.

Until paid subscriptions launch, do not present a working purchase promise: explain
that continuation is subject to availability and contact support for access review.
Show the actual trial end and grace dates in billing; no deletion or implied charge.
Seller remains Rajesh Rathod H under the confirmed unregistered GST treatment.

## Implemented selection and consent (2026-09-29)

`BILLING_PUBLIC_TRIAL_PLAN_ID` defaults to zero. Together with the trial switch, it
selects exactly one active, unbound, zero-price, 30-day, six-member Plan. Both the
page and direct start endpoint use this boundary. The owner must verify their
sign-in email and accept the versioned terms. Company locking prevents repeated
or concurrent starts; existing billing/access history is refused. New trials have
`auto_renew=False`, frozen entitlement rows and accepted terms in `trial.started`.
No payment provider is called. New-owner onboarding routes to consent, then team
invitations; billing shows trial end and read-only start timestamps.

The real seat test found and fixed the old installed-app short-name check that
bypassed capacity. Member creation and invitation reservation/acceptance now
serialize on Company; direct additions count pending reservations. Existing
members are retained, even if their Workspace already exceeds its limit.
See the [decision](../adr/2026-09-29-selected-public-trial.md).

## Catalog and browser acceptance checkpoint (2026-09-29)

Production **Plan 3** has the approved name, 30 days, six members and zero monthly,
annual and extra-member prices. Unsupported commercial flags are false; retired
inventory/transaction quota fields are zero and confer no extra capability. Core
Party/Loans/Notify v2/Rates remain governed by their existing module, role and
business-setup requirements; no unsupported reporting/API/warehouse promises are
published. The currently supported business services do not consume those retired
quota fields. Reassess the projection before introducing new quota enforcement.

Use `prepare_public_trial --actor-id 9 --reason "<reviewed reason>"` to preview;
`--apply` saves the separate Plan plus a BILLING_UPDATE audit. All creation flags
must be paused. It refuses different stored terms and reuses an identical Plan
without updating it. Production preparation used the reviewed command body against
the existing runtime image (only the terms-version import was supplied inline);
no application image or setting was replaced. Existing plans, memberships,
Workspaces and non-Plan billing tables were fingerprinted before/after unchanged.
Server-private evidence: `public-trial-preparation-20260929` under the cutover folder.

A fresh local database, `rokkad_baseline_rehearsal_public_trial_20260929`, used the
restricted runtime role for the browser. The actual password signup and ordinary
New Workspace screens led to the trial offer through commercial recovery. Owner
verification, explicit acceptance, six-seat display, queued invitation, refusal of
unverified teammate acceptance, then verified link acceptance all passed. Final
state is two members, one active trial/event, six-seat limit and no financial or
provider evidence. Account email used a local file backend; invitation rendering
used capture mode. **No real email was sent.** The generic rehearsal banner says
legacy copy, but this database was empty/migrated with fictional fixtures only.
The browser and server have been closed. Ignored local evidence includes
`outputs/public-trial-rehearsal-20260929/verified.json`, `plan.json`,
`production-applied.json`, `production-account-mail.json` and `teammate-accepted.png`.
**23 focused tests passed** for preparation and trial/catalog regressions.

Production account mail inventory found **locmem**, with verification optional.
That backend does not send account-verification or password-reset email. Team
invitations use their separate enabled SES worker. The local journey establishes
application behavior, not production account-mail delivery. Implement and accept
that transport before advertising general password-based trial signup.

Account verification/reset queuing is now implemented and tested locally in the
existing monitored mail worker. `ACCOUNT_EMAIL_ENABLED` defaults to false; the
schema, matched web/worker deployment and real delivery acceptance are still
pending. See the [rollout procedure](../implementation/platform-mail.md#account-mail-prepared-not-deployed-2026-09-29).

The free offer and paid offer describe different consent and lifecycle terms,
not separate products or permanent customer classes. The trial is INR 0 for
30 days with no card or automatic charge. The private paid offer is INR 1,499
per month with six total members and separately accepted recurring terms. Both
can eventually be presented publicly after their respective acceptance gates;
publication does not automatically convert a trial to a paid subscription or
rewrite existing accepted terms. Annual billing remains separate and pending.

## Remaining publication work

The previously deployed trial flag exposes every active plan in the generic catalog. Plan 1
is the **Production transition trial**, 14 days and five total members; Plan 2
is the private monthly offer, six members and zero trial days. Neither is the
public 30-day offer. Do not change either plan to implement this draft, or simply
turn on `BILLING_ALLOW_TRIAL_START` with the existing catalog query.

Plan 3 is prepared. Deploy the selection/consent code and select Plan 3 in the
deployment settings after account-mail acceptance. Only the selected eligible trial can appear or be accepted
by its start endpoint. A hidden/private plan ID must not activate a trial through
direct POST. Reuse the existing locked `start_trial` service and durable subscription,
account, entitlement and event records; Workspace creation itself grants no trial.
Review trial feature limits with the actual supported product before saving a plan.
Keep recurring/one-off charging disabled and annual pricing unpublished.

The intended new-owner flow is: sign in with a verified identity, create a
Workspace, review/start the trial, invite staff, then complete business setup.
Invitation acceptance requires the invited email's verified identity and ordinary
role/seat/lifecycle checks. A pending invite reserves a seat. Workspace membership
does not grant commercial access without the trial or an administrator decision.
Google sign-in and platform SES invitations are established paths; account
verification/password-reset mail has a separate transport and needs its own review
before promising every email/password signup path is ready.

## Acceptance before activation

- New owner starts exactly one 30-day trial, with six-member capacity and frozen
  entitlements; a repeat/concurrent request cannot restart or extend it.
- Private plan IDs and another Workspace's owner are rejected at the trial endpoint.
- Existing trial dates, private monthly/annual catalogs and billing evidence stay
  unchanged. Starting/expiring a trial creates no provider mandate or charge.
- Owner plus five staff fits; a sixth staff invitation is refused, including pending
  invites. Expired/revoked invitations do not restore access.
- Verify sign-in, Workspace creation, trial consent, invitation delivery and verified
  acceptance through the user-facing flow, then exercise expiry/grace/read-only.
- Review public onboarding eligibility/abuse controls and publish the exact terms
  before enabling the public trial. Operator support must remain available while
  paid continuation is paused.

Current boundary evidence: 34 focused invitation/mail/onboarding tests and one new
restricted-role database journey test passed. The latter uses real Workspace,
invitation, queue, attempt and membership services, mocks only provider sending and
the dispatch sleep, and confirms no subscription/payment is created by inviting.
It is not a browser signup test or a new real-mail delivery rehearsal.

**82 focused tests passed.** Automated acceptance covers the restricted-role HTTP onboarding/consent flow,
private/stale offer rejection, verified canonical ownership, existing-history
preservation, frozen seats and dates, expiry/grace/read-only, six-seat enforcement,
and simultaneous trial/last-seat requests. Production plan creation and the local browser journey are now complete; deployment,
production account-mail acceptance and public activation remain outstanding.
Before publication, review owner-created Workspace abuse controls (the current
limit is one trial per Workspace, not one trial per person) and support capacity.
