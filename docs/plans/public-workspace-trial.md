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
These are approved draft terms; public trial activation is not deployed or enabled.
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

## Required implementation before publication

The current trial flag exposes every active plan in the generic catalog. Plan 1
is the **Production transition trial**, 14 days and five total members; Plan 2
is the private monthly offer, six members and zero trial days. Neither is the
public 30-day offer. Do not change either plan to implement this draft, or simply
turn on `BILLING_ALLOW_TRIAL_START` with the existing catalog query.

Prepare a separate six-member, 30-day trial plan and an explicit public-trial
selection boundary. Only the selected eligible trial should appear or be accepted
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
