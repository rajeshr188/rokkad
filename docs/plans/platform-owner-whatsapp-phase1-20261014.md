---
status: active
owner: project
updated: 2026-10-14
tags: [plans, whatsapp, control-plane, onboarding, billing]
related:
  - future-work.md
  - workspace-whatsapp-cloud-integration-acceptance.md
  - ../adr/2026-10-14-platform-whatsapp-delivery-boundary.md
  - ../architecture/control-plane-contracts.md
  - ../domain/notifications.md
---

# Platform-to-owner WhatsApp: phase-one design

## Mandate and completion

The owner accepted FW-011's three beneficiary groups and four-phase order on
14 October, then instructed the agent to proceed with the next stated step:
design phase one. This document completes that design and proposes an implementation
sequence. PW-01 through PW-04 have subsequently been authorised, implemented and locally verified as
recorded below. No registration, template submission or actual send occurred. Later Workspace borrower messaging remains a
separate eligible pilot.

The objective is to help owners finish setup, understand their Rokkad subscription
and obtain help with fewer manual follow-ups. Use Rokkad's authorised business
identity. Initial recipients are canonical Workspace owners; additional billing
contacts, staff recipients and internal operational alerts follow separately.

## PW-01 implementation checkpoint

[PW-01 is verified locally](../implementation/platform-whatsapp-enrollment-pw01.md):
optional account enrollment, bounded hashed pairing, per-Workspace consent,
pause/disconnect, signed inbound pairing/opt-out and read-only drafts. Preference
and ConsentEvent refine the initial global evidence sketch below with direct
Workspace ownership, forced RLS, registry coverage and immutable consent guards.
102 distinct regressions and six browser layout states pass; disposable DBs are
removed. No review/production migration or actual provider acceptance occurred.
PW-02 through PW-04 are subsequently verified below; PW-05 local work and live limits are recorded below.

## PW-02 implementation checkpoint

[PW-02 is verified locally](../implementation/platform-whatsapp-source-intents-pw02.md):
immutable setup/trial/paid intents use direct Workspace ownership, forced RLS,
typed source uniqueness and database source/consent guards. Native source
transactions retain independent email intent. Setup confirmation binds a signed
review; current authority/consent/source/expiry checks keep all records preview-only.
313 distinct selected regressions, populated PW-01 preservation and ten desktop/
phone states pass. Both disposable databases are removed. No actual provider send,
review/production migration or deployment occurred.

## PW-03 implementation checkpoint

[PW-03 is verified locally](../implementation/platform-whatsapp-transport-pw03.md):
committed restricted-role attempts, a bounded Cloud template adapter, authenticated
global minimal status evidence and forced-RLS immutable receipt links. Exact provider
ID/sender/recipient matching handles early callbacks without guessing scope; read/
delivered facts survive late failures. Unknown acceptance blocks automatic resend.
360 distinct selected cases, populated PW-02 preservation/blocked downgrade and
eight desktop/phone states pass. Both exact task databases are removed. Native
source writers still capture only and a hard release gate awaits PW-04 controls.
No provider configuration, real send, shared migration or deployment occurred.

## PW-04 implementation checkpoint

[PW-04 is verified locally](../implementation/platform-whatsapp-controls-pw04.md):
current accepted-end/access-policy reminders, signed reviewed service notices with
owner deduplication/scoped targets, and immutable atomic named-pilot/count/spend
reservations. Global broadcast jobs use successive explicit Workspace units. Four
new forced-RLS models bring the registry to 155. All 399 distinct selected cases,
populated PW-03 accepted/read preservation/blocked downgrade and eight phone/desktop
states pass; exact task databases are removed. Creation/sending flags default off,
old captures never promote and pricing uncertainty holds new requests. No actual
send, provider setup, shared migration or deployment. PW-05 remains separate.

## PW-05 local checkpoint

Owner/platform diagnostics, independent invoice receipt status, reviewed rejection
retry/reconciliation and a read-only masked preflight are implemented locally. No
new schema is added. The owner selected JCL and will monitor support@rokkad.com;
deployed canonical owner metadata matches the supplied account. Production lacks
the WhatsApp app/tables and sender/template setup is still needed. Pricing holds
remain fail-closed; correction, billed-cost and retention automation are not added.
See [PW-05](../implementation/platform-whatsapp-pilot-pw05.md) and the concrete
[sender/template handoff](platform-whatsapp-sender-setup-20261014.md). Live consented
acceptance remains pending and must not be inferred from mocks or this checkpoint.

## First release

| Message | Source and trigger | Eligibility and expiry | Destination |
| --- | --- | --- | --- |
| Setup guidance | Owner requests guidance while enabling WhatsApp for an owned Workspace | One per contact/Workspace enrollment revision; current ownership and active lifecycle; expires after 24 hours | Existing setup and public contact page |
| Trial confirmation | Successful trial.started SubscriptionEvent | Opted in when event commits; current owner, active lifecycle and still-current trial; expires after 24 hours | Existing billing/setup page |
| Paid subscription confirmation | Paid Invoice at the existing receipt-intent boundary | New paid invoice, enrolled current owner; never authorization alone; provider mode must match; expires after 7 days | Authenticated invoice detail |
| Trial ending | Scheduled review of accepted trial end | One reminder in final three local calendar days before actual expiry; no late catch-up; current owner, active lifecycle and still trial | Billing and support |
| Service announcement | Administrator reviews a dated, bounded announcement | Explicit affected Workspace list, current owner/consent, approved template and expiry; recheck before dispatch | Published service information or existing contact page |

Setup guidance is requested assistance, not an unsolicited signup campaign.
Trial-ending wording states the saved end date; it never invents an available paid
offer, automatic charge, grace period or loss of access. Read workspace_activity
for access facts, including administrator decisions. Paid conversion or an
overriding access decision cancels an obsolete reminder. Do not send suspended,
archived or deletion-pending Workspaces routine setup/trial nudges. Paid receipts
and specifically applicable service announcements may still help their owners;
control-plane communication never reopens business access.

Support initially uses the existing monitored public contact/email handoff.
Show that path in the sender profile and help messages. A shared inbox, agent
free-text replies, borrower documents, general identity OTPs, marketing and
collection campaigns remain outside this release. Incoming enrollment and
opt-out commands are necessary even for this limited release. Other incoming
messages receive at most one fixed support-handoff reply per sender per 24 hours,
only within the valid service window using verified provider message time.
Stale callbacks receive no free-form reply or account/Workspace disclosure.

## Owner journey

Use ordinary Django forms in existing account settings, with Workspace preferences
reached through explicit Workspace URLs. Enrollment is optional and must not block
email verification, trial consent, guided setup or lending.

1. Show Rokkad's sender, support route and available languages. Categories start
   unchecked: setup assistance, subscription updates and service announcements.
   Explain that this number receives Rokkad messages, separately from the shop's
   customer-messaging connection.
2. Validate/normalize the entered phone with the existing phone-number library.
   Store pending enrollment and explicit category/consent text version, actor/time.
   Existing or imported phone fields never imply messaging permission.
3. Ask the signed-in owner to send a prefilled enrollment code to Rokkad's sender.
   Use a random, hash-stored, purpose-bound, single-use code with 15-minute expiry.
   Accept only authenticated inbound pairing from the exact entered number.
   Rate-limit issue/match attempts; a GET/link click cannot activate consent.
   This narrow pairing proves account access for enrollment; the general customer
   OTP product remains phase three.
4. Activate only when pending consent and pairing remain valid. Show the masked
   number, language and per-Workspace categories. Offer an explicit setup-guidance
   request, without replaying old trial/payment events.
5. Allow pause, category changes and disconnect. Number changes invalidate contact
   verification and queued messages; require fresh enrollment.
6. Process STOP and equivalent clear opt-outs from authenticated incoming messages
   as platform-wide phone suppression. UI category opt-out can be narrower.
   START alone cannot restore consent; use the authenticated enrollment flow.

Initial rule: one verified active number per user, one active user binding per
number. An owner of several Workspaces can use the number with separate Workspace
preferences. Shared family/staff numbers are not silently linked to other users.
Operators may diagnose/suppress but cannot manufacture consent or pairing success.
Phone pairing is not legal identity, SIM ownership or Aadhaar verification.

Use current WorkspaceAccess policy and canonical billing-owner checks for scoped
preferences/retries; ownership is routing evidence, not an authorization shortcut.
Ownership transfer immediately invalidates the old owner's queued eligibility;
the new owner enrolls separately. Staff Membership/platform override does not
make someone a recipient. Email verification does not verify a supplied phone.

## Sender and delivery boundary

The [accepted ADR](../adr/2026-10-14-platform-whatsapp-delivery-boundary.md) recommends
a small Django platform_whatsapp app. Leave platform_mail's SES-specific models,
constraints and delivery intact. Notify v2 keeps Workspace borrower messages.
Do not use a dummy Workspace or platform fallback for customer jobs.

Private runtime configuration holds platform Meta phone ID, app/WABA identity
where available, supported API version, access/verify tokens and app secret.
Owners cannot read/edit them. A non-secret configuration fingerprint binds
readiness; sender/credential version changes pause sending until reacceptance.
No new provider abstraction, channel framework or automatic account onboarding.

Proposed evidence:

| Record | Responsibility |
| --- | --- |
| Contact enrollment | User, normalized phone, pending pairing hash/expiry, revision and verified-at evidence |
| Consent evidence/preferences | User/Workspace/category binding, consent-text/language revision, opt-in/out actor/time and retained changes |
| Service announcement | Typed service purpose, creator, text/template revision, impact dates, exact reviewed targets and expiry |
| Delivery | Exactly one typed setup request, SubscriptionEvent, paid Invoice or announcement source; owner/Workspace, consent/contact/template revision, recipient snapshot and unique intent key |
| Attempt | Durable claim ID, timestamps, outcome, real Meta message ID and sanitized diagnostic |
| Provider receipt | Authenticated sender, ID/status/time, digest and matched attempt; private unmatched status for reconciliation |
| Suppression | Platform phone opt-out and reason/time |

The initial global control-plane sketch is refined by PW-01/PW-02: account
Contact/ContactEvent/Suppression/InboundReceipt remain global; Workspace Preference,
ConsentEvent, SetupRequest and Delivery have direct non-null ownership, forced RLS
and registry/isolation coverage. Source links and general CRUD restrictions remain
explicit. PW-03 adds scoped Attempt/ReceiptLink and a global unmatched ProviderReceipt inbox.
PW-04 resolves announcement ownership with a global reviewed platform publication and forced-RLS scoped targets, plus scoped reservations/cost evidence and minimal global daily aggregates.

Do not persist borrower records, passwords/login/reset tokens, card/bank identifiers
or raw provider bodies. Mask numbers in routine UI and exclude personal data/secrets
from public logs. Before migrations, enumerate exact fields, constraints, indexes,
retention and erasure behavior. This design is not an executable schema.

## Actual source hooks inspected

| Existing implementation | Proposed connection |
| --- | --- |
| apps/subscriptions/billing.py: start_trial creates trial.started with accepted terms | Add eligible trial-confirmation intent inside the same transaction |
| apps/subscriptions/notifications.py: send_checkout_receipt | Add independent WhatsApp receipt intent beside existing email; checkout.py and recurring_cycles.py already use this boundary |
| apps/onboarding/services/account_journey.py | Reuse owner_business_setup_url with explicit authorized Workspace |
| apps/subscriptions/access_policy.py | Read workspace_activity without copying its rules |
| apps/orgs/services/platform_console.py and web/platform_console.py | Reuse active-platform-admin/global-context checks and reviewed POST pattern |
| apps/orgs/web/account_preferences.py | Extend the existing account preference surface |
| Notify v2 whatsapp_integration.py/delivery_service.py | Reference Cloud/template/signing concepts; do not call Workspace credentials/jobs for platform sends |

Persist source intent in the business transaction, not only in an on_commit
callback that can lose work. Render and call Meta after a durable dispatch claim,
outside the business transaction. Source rollback removes intent; a provider
failure cannot undo a committed payment. Invalid consent skips messaging;
unexpected persistence failures follow source transaction recovery and must not
be silently represented as successful durable intent.

Scheduled reminders use a unique trial-source/end-date-revision/stage key.
Re-read trial, ownership, preferences and access before queueing and dispatch.
Do not change trial dates. The platform console's existing seven-day diagnostic
filter is not the new reminder rule. No historic replay on enrollment/activation.
Local captured previews cannot become live just by enabling dispatch.

Announcements require expiring signed review binding actor, announcement revision,
explicit targets, actual eligible recipients, templates and estimated cost.
Changed or stale review requires regeneration. No arbitrary-number composer.

## Templates, links and current policy

Candidate names: rokkad_setup_help, rokkad_trial_started,
rokkad_subscription_paid, rokkad_trial_ending, rokkad_service_update.
They are proposed names, not registered/approved templates. Keep parameters typed;
no arbitrary message JSON/scripts supplied by a Workspace. Every enabled locale
needs an actual approved Meta mapping. Start with English; add Hindi/Tamil only
after wording/provider review and owner selection, without silent substitution.

Draft paid text: "Rokkad recorded payment of INR {amount} for invoice
{invoice_number}. View your invoice in Rokkad." Claim access activation only if
canonical policy supports it. Draft reminder: "Your Rokkad trial for
{workspace_name} ends on {date}. Review your workspace subscription or contact
support." Classification and exact text/buttons require provider review; utility
eligibility is not established by the local template name.

Use canonical HTTPS origin and Django reverse with explicit Workspace identity.
Billing/invoice/setup links retain their own authentication/authorization. A
message link cannot grant a session, Membership, ownership, payment or access.
Account recovery tokens remain in the existing account-email workflow.

The [Meta messaging policy](https://whatsappbusiness.com/policy/) was checked
14 October 2026: opt-in/opt-out, approved templates for initiated messages,
24-hour free-form response window and a clear human support path apply.
Lending/collection restrictions gate the later borrower phase. Platform SaaS
messages also need actual sender/template eligibility; this is not an exemption.

[Official pricing](https://whatsappbusiness.com/products/platform-pricing/) was
checked the same day. Applicable charges vary by recipient market/category and
delivered messages. Keep dated tariff/category evidence; distinguish reserved
estimates from actual reconciled cost. No fixed WhatsApp price, Workspace charge
or change to loan accounting is selected.

## Dispatch, callbacks and limits

Use a bounded restricted-role worker, separate capture/sending flags, purpose
allowlist and named owner/Workspace pilot cohort. Recheck contact revision, consent,
suppression, current owner/source, lifecycle applicability, template/language,
readiness and caps before each attempt. Atomically reserve count/spend capacity.

Persist attempt before a bounded provider request and disable implicit send
retries. A real Meta ID means accepted, not delivered/read. Missing ID, ambiguous
timeout, invalid success response or interruption after claiming becomes unknown.
Never synthesize IDs or automatically resend unknown acceptance. Definite
retryable rejection gets bounded backoff; definite-failure retry rechecks eligibility.

Proposed exact global webhook: /app/integrations/whatsapp/webhook/. Only that route
uses provider authentication with request/RLS Workspace context unset. GET checks
verify token; POST verifies HMAC over original bytes, expected object and exact
platform sender/app/WABA identity where supplied, bounded structure and correlation.
Existing Workspace webhook exemptions do not broaden. Wrong-scope sender IDs fail.

Persist deduplicated receipts before acknowledgement. Delivered/read facts never
downgrade on late sent/failed callbacks; retain failures/contradictions for review.
Hold authenticated unmatched IDs privately: a callback can arrive before local
response persistence. Reconcile after saving the attempt's provider ID; unmatched
evidence alone cannot assign recipient/Workspace or claim delivery. Accept late
delivery evidence after opt-out without sending an acknowledgement. Pairing and
STOP are replay safe; chat text cannot choose Workspace authority.

Proposed pilot defaults: 100 outbound messages/platform/day, 5/contact/day,
routine delivery 09:00–18:00 Asia/Kolkata, one trial-ending message per trial.
Defer capped work only if useful/unexpired at the next permitted window.
Deduplicate multi-Workspace service announcements for the same owner; receipts
remain per invoice. Reviewed urgency may bypass quiet hours but not consent/caps.
Exact monetary cap and actual tariff must be configured before chargeable dispatch;
unknown pricing pauses sending. Rokkad bears pilot costs; no new customer markup.

## Screens and rollout

Account preferences: masked contact, pairing, categories/language, pause/disconnect,
support. Workspace Billing: independent WhatsApp/email receipt status and retry
only for definite failure under current billing-owner authority. Recovery-only
access requires exact preference-route coverage, never a general middleware bypass.
Global account preferences allow consent revocation even when a Workspace is blocked.

Platform console: sender readiness/paused state, queued/accepted/delivered/read/
failed/unknown totals, template gaps and reserved/estimated/reconciled spend.
Source-derived target diagnostics only; configuration tests/announcements are
audited, CSRF-protected reviewed POSTs. Reading a metadata page cannot send.

| Slice | Implementation | Required evidence |
| --- | --- | --- |
| PW-01 | Resolve proposed schema/ADR; contact enrollment, consent, offline readiness/capture | Wrong owner/Workspace; pairing expiry/replay; opt-out, number change and transfer; no secret leaks |
| PW-02 | Durable setup/trial/paid intents and previews | Source rollback; checkout/recurring parity; replay and concurrent workers |
| PW-03 | Cloud transport, exact global callback and receipt reconciliation | Real IDs; early/replayed/foreign/out-of-order callbacks; unknown acceptance; global/RLS separation |
| PW-04 | Trial scheduler, reviewed service announcements and caps | Date/override/conversion changes; stale review; quiet hours; count/spend concurrency |
| PW-05 | Owner/platform UI and bounded live pilot | Restricted-role tests, migration/restore/rollback, phone UI, real consented delivery/callback/opt-out and monitored support |

PW-01 through PW-04 are locally verified. PW-05 diagnostics and reviewed operations
are implemented locally; external setup/deployment and live acceptance remain pending. Use ordinary
Django models/forms/commands and existing policies. Validate migrations through
owner settings; tests use django_project.settings.test. Mocked delivery or stored
credentials cannot prove live acceptance. Real-person retention/erasure policy,
actual sender/templates, tariff/monetary cap and a specific consented recipient
must be resolved before the live pilot.

Dispatch must stop independently of email/source transactions. Deploy compatible
readers before writers/worker activation. Rollback stops WhatsApp dispatch,
preserves source/payment/delivery evidence and restores compatible code; never
restore old data over later transactions. Credentials and recovery stay private.

## Next concrete step

Next is sender/template setup and compatible deployment for a specific consented
JCL pilot. PW-05 local diagnostics/reviewed operations are implemented, while
pricing-hold resolution remains separate. Sender identity, approved templates/locales,
actual dated tariff/monetary cap and retention/erasure must be settled; the owner
will monitor support@rokkad.com.
PW-01 through PW-04 are locally verified. Intent creation and sending flags default
off; captured history cannot promote. No provider account creation, actual messages,
shared migration or deployment follows automatically from local implementation.
