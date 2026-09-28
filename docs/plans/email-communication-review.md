---
status: proposed
owner: project
updated: 2026-09-26
tags: [email, invitations, notifications, operations]
related: [future-work.md, ../domain/notifications.md, ../architecture/control-plane-contracts.md]
---

# Email communication: current-state review and proposed setup

## Subsequent authorization

On 2026-09-26 the owner selected Amazon SES, approved the focused implementation
and confirmed no Google Workspace or AWS account exists yet. The
[active rollout](platform-email-rollout.md) supersedes the proposal status below;
the original findings remain a review checkpoint. Typed configuration and offline
diagnostics are implemented locally; accounts, DNS, durable delivery and activation
remain pending. No external mail has been sent.

## Outcome

The owner requested analysis of replacing personal-email sending with proper
platform communication. This review covers repository call paths, non-secret
production configuration and public DNS. No mail, provider application, DNS change,
credential update or deployment was performed.

**Immediate finding:** production currently uses Django's non-sending in-memory
backend, not a personal SMTP sender. Reliable invitation/account email delivery
requires deliberate activation and acceptance. Do not mark this as an optional
future enhancement while relying on emailed invitations.

Recommend domain-owned human inboxes plus one transactional provider, initially
Amazon SES for platform invitations/account/billing messages. Keep borrower delivery
separately controlled. Provider choice, mailbox ownership, account approval and
implementation remain proposed; this is not authority to turn on all existing jobs.

## Verified findings, 2026-09-26

| Priority | Evidence | Practical consequence |
| --- | --- | --- |
| High | The deployed `production_settings` explicitly assigns `django.core.mail.backends.locmem.EmailBackend`; the production web processes use that settings module. No alternative MAILERS configuration was present. | Mail through the reviewed Django paths stays in process memory. A successful send call is not external delivery. Do not assume previous invitations/receipts reached recipients. |
| High | `send_team_invitation` calls `form.save()` within `_control_plane_transaction`; the form invokes `CompanyInvitation.send_invitation`. Onboarding also sends inside its transaction. | Real SMTP would block the request/transaction and could send a link before a later rollback. Add committed delivery intent and explicit failure/retry state. |
| Medium | `base.py` reads EMAIL_PORT and EMAIL_USE_TLS with untyped `env()`. Runtime values were a string port and the string `False`; EMAIL_TIMEOUT was null. | Correct integer/boolean parsing before SMTP activation. A nonempty `False` string is truthy; do not assume it disables TLS. Set a finite timeout and mutually exclusive TLS/SSL settings. |
| Medium | Billing uses `on_commit(..., robust=True)` and `send_checkout_receipt`, but no durable receipt-send retry record in that path. | Payment survives a mail failure, correctly; delivery can be lost until explicitly retried. Preserve payment truth while recording retryable delivery intent. |
| Medium | Notify v2 calls `send_mail`, synthesizes an `email:<job>:<time>` ID and marks the job sent. Its authenticated provider receipts cover WhatsApp, not email delivery callbacks. | No actual email-provider message ID or bounce/complaint/delivery reconciliation in the inspected email path. SMTP success means accepted for sending, not inbox receipt. |
| Medium | Default sender is shared. Billing's optional BILLING_EMAIL_SENDER is not defined in deployed settings. The inspected send calls do not set purpose-specific Reply-To. | Platform mail and borrower mail lack a complete sender/reply-routing policy. Adding an unused environment variable alone will not wire a new billing sender. |
| Medium | Public root MX points to Google; root SPF authorizes Google. `_dmarc.rokkad.com` returned NXDOMAIN from the lookup resolver. | Inventory existing Google mailboxes and confirm DNS authoritatively before changes. MX does not establish which inboxes exist or who controls them. DKIM selectors were not exhaustively audited. |

Runtime inspection printed backend names, sender domain, setting types and presence
flags only. Sender domain was `rokkad.com`; SMTP host/port were loopback/test values,
and SERVER_EMAIL was the localhost default. Credentials were neither printed nor
tested. This is a checkpoint, not proof of historical delivery or mailbox ownership.
Django documents the in-memory backend as development/test storage, not delivery.
[Django email backend reference](https://docs.djangoproject.com/en/6.0/topics/email/#in-memory-backend)

## Existing paths to preserve

- Invitations: `apps/orgs/services/control_plane.py`, `apps/orgs/forms.py` and
  `apps/orgs/models.py`; templates are addressed through the invitations adapter.
  The context includes inviter/site/link but no explicit Workspace/role entry in
  the inspected method. Review the effective package template and add clear business,
  role, inviter and expiry information without putting invitation tokens in logs.
- Account verification/reset: allauth through the configured invitations adapter;
  repository reset templates under `templates/account/email/`. Verify the canonical
  HTTPS host and correct branding. Preserve verified-email acceptance checks;
  enabling delivery must not grant membership or change authentication policy.
- Billing: `apps/subscriptions/notifications.py` and `checkout.py`, with HTML/text
  receipt content generated from the committed invoice and its billing contact.
- Borrowers: Notify v2 `services/delivery_service.py` uses the event recipient's
  email. Reuse its jobs/artifacts and consent/preview boundaries. Loans' risk-email
  readiness already recognizes simulated backends; invitation sends do not have
  equivalent readiness evidence. Do not assume every notification route is blocked.

## Proposed sender and inbox map

These addresses are examples to provision/verify, not existing mailbox claims.

| Purpose | Proposed From | Reply-To / destination |
| --- | --- | --- |
| Invitations, account/security messages | `Rokkad <notifications@notify.rokkad.com>` | Monitored `support@rokkad.com` |
| SaaS invoices/payment/subscription notices | `Rokkad Billing <billing@notify.rokkad.com>` | Monitored `billing@rokkad.com` |
| Workspace borrower notifications, later | `<Workspace name> via Rokkad <updates@messages.rokkad.com>` | Workspace's separately verified and authorized contact address |
| Human support/billing conversations | Domain mailbox or alias at `rokkad.com` | Handled in the human mail service |

Rokkad owns the platform sender. Customers do not need SMTP passwords to invite
their team. Later custom-domain Workspace sending requires proof of domain control,
provider verification and explicit authorization; never spoof a customer's Gmail
address in From. Distinguish business contact verification from an allauth login
identity. Subdomains/streams separate configuration and traffic but do not guarantee
complete reputation or provider-account isolation. Keep marketing separate.

Use the existing Google MX setup if the owner confirms it is active and controlled.
A transactional sending service does not automatically create a human inbox. Replies
must land somewhere monitored. Changing the outbound provider need not replace
root MX or move the website/domain. Do not install a new self-hosted mail server on
the application Linode as part of this setup.

## Provider assessment

Public pricing checked on 2026-09-26; charges below exclude any separately applicable
taxes, data/add-ons and mailbox subscription. This is a short shortlist, not a
contract or account approval.

| Provider | Public baseline | Fit and unresolved points |
| --- | --- | --- |
| Amazon SES, recommended first candidate | A la carte outbound USD 0.10/1,000 messages; data/add-ons separate. | Low running cost, supports an ordinary SMTP transition; more AWS setup and event handling. Verify domain, select region, obtain production access and confirm the declared SaaS/pawn-lending communication use case. |
| Postmark | Basic USD 15/month at 10,000 emails on the viewed pricing page. | Convenient transactional operations; published terms restrict short-term/payday-loan services. Obtain explicit fit clarification rather than treating borrower messages as automatically eligible. |
| Resend | Free 3,000/month with 100/day cap; Pro USD 20/month for 50,000 on the viewed page. | Convenient initial setup; daily caps can obstruct invitations. Its acceptable-use policy also restricts short-term/payday-loan content; same fit question. |

Sources: [SES pricing](https://aws.amazon.com/ses/pricing/),
[SES production access](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html),
[Postmark pricing](https://postmarkapp.com/pricing),
[Postmark terms](https://postmarkapp.com/terms-of-service),
[Resend pricing](https://resend.com/pricing),
[Resend acceptable use](https://resend.com/legal/acceptable-use).
SES approval is not guaranteed. Do not conceal the business model or split traffic
to evade a provider's terms. Start with platform communication as a bounded delivery
scope; lender communication still needs its own review.

## Proposed implementation order

1. **Confirm ownership and addresses.** Identify the domain-mail administrator,
   monitored support/billing inboxes or aliases, authorized initial test recipients
   and expected volumes. The review has not inspected the Google Admin account.
2. **Provision authenticated transactional sending.** Create a business-owned provider
   account with MFA and narrowly scoped runtime credentials, stored privately on the
   server. Request the appropriate production access, not broad administrator keys.
   Configure provider-issued DKIM and aligned envelope sender/Return-Path records
   in Linode DNS; retain Google MX/SPF and avoid duplicate SPF records at one name.
   Configure DMARC reporting initially, review legitimate sending, then plan stronger
   enforcement. Do not publish guessed keys or unverified reporting recipients.
3. **Make application configuration explicit.** Correct typed settings and timeout,
   purpose-specific From/Reply-To and environment separation. The deployment-local
   backend override must be changed through the release process, not merely by
   setting EMAIL_BACKEND in an env file that code does not read. Add a production
   email readiness check so a non-sending mode is clearly exposed. Preserve test/
   rehearsal capture and require an explicit sending mode for production activation.
4. **Reliable invitation/account/billing delivery.** Persist bounded delivery intent
   atomically with the underlying business action and dispatch after commit. Use a
   simple retry worker/command rather than add a distributed framework without need.
   Keep global account/billing events distinct from Workspace-owned Notify jobs;
   a reviewed shared transport need not merge their authority or data ownership.
   Provide purpose/event idempotency, finite retry/backoff, sanitized errors and
   authorized manual retry. Re-check revoked/expired invitations before dispatch.
   Plan token expiry/delivery timing carefully for account-security mail. SMTP has
   an ambiguous acceptance window after a crash: do not claim exactly-once delivery;
   use provider-supported evidence/idempotency where available and reconcile before
   retrying uncertain sends. No email failure may undo a captured payment.
5. **Delivery observability and recipient hygiene.** Persist actual provider IDs;
   authenticate/deduplicate delivery/bounce/complaint events and validate account/
   message correlation before selecting a Workspace. Do not trust caller-supplied
   tenant IDs. Suppress hard bounces/complaints, expose queued/accepted/delivered/
   failed/unknown states, and distinguish SMTP acceptance from mailbox placement
   or user action. Avoid copying secret links, OTPs or full message bodies into logs.
6. **Templates and scoped rollout.** Preview branded text/HTML invitation, security
   and billing messages; disable link/open tracking for token-bearing mail. Show
   clear Workspace context and safe HTTPS links. An authorised controlled test must
   verify receipt, SPF/DKIM/DMARC results, working acceptance/reset flows and replies.
   Review pending invitations for expiry/revocation; resend only selected valid ones.
   Never replay every historical receipt or notification when changing backend.
7. **Borrower email as a later explicit rollout.** Verify workspace contact/reply
   routing, provider eligibility, opt-out/preferences and rate/spend limits first.
   Reuse existing Notify review/jobs; prevent tenant content or identifiers leaking
   into other tenants' sends, callbacks, logs or support screens. Do not activate
   blanket loan reminders by enabling the platform transport.

Authentication guidance: [Google sender requirements](https://support.google.com/mail/answer/81126?hl=en).
Google recommends SPF, DKIM and DMARC; DMARC needs alignment with the visible
From domain. The exact DNS records come from the selected provider.
See also [SES verified identities](https://docs.aws.amazon.com/ses/latest/dg/verify-addresses-and-domains.html).

## Acceptance and operational handover

Use local capture/provider simulators first, then explicitly authorized test mail.
Check commit rollback sends nothing, retry does not create a second invitation or
payment, delivery errors remain actionable, rate limits and timeout work, revoked
invites cannot be accepted, links target the intended production host, Reply-To
reaches the correct mailbox, and cross-Workspace access is denied. Verify sending
from both web and worker configuration; secrets must never enter exports or the
OneDrive repository. Test authenticated callback replays and suppression handling.

Record provider/DNS evidence, credential ownership/rotation, allowed senders, retry
and suppression runbooks, alert recipients and a rollout/rollback plan. Existing
in-memory messages are not a durable retry queue. Provider message delivery is not
proof that an invitation was accepted or a borrower received a legally served notice.

**Next recommended decision:** confirm the current Google domain-mail account and
support/billing destinations, then select SES subject to use-case approval. Implement
platform delivery and reliability first; custom Workspace domains and broader
borrower communication remain later scope. No account, purchase or activation has
been performed by this review.
