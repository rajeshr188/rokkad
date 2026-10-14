---
status: verified-local
owner: project
updated: 2026-10-14
tags: [implementation, whatsapp, source-intents, control-plane, rls]
related:
  - platform-whatsapp-enrollment-pw01.md
  - ../plans/platform-owner-whatsapp-phase1-20261014.md
  - ../adr/2026-10-14-platform-whatsapp-delivery-boundary.md
  - ../architecture/control-plane-contracts.md
  - ../domain/notifications.md
---

# PW-02: durable owner WhatsApp source intents and previews

## Delivered locally

The owner explicitly authorised PW-02 on 14 October. Setup requests, trial starts
and newly captured subscription payments now record immutable WhatsApp previews
inside their source transaction. Account Settings exposes a reviewed setup request
and the latest ten saved previews per owned Workspace. Nothing sends: every row
is permanently capture_only, every preview returns can_send=false, and there is
no outbound worker, provider request, status handling or send button.

The existing platform SES receipt and Workspace Notify v2 remain independent.
No amount, tax, trial date, paid term, access rule, entitlement, lifecycle,
Membership or borrower accounting rule changes. A TEST payment preview is clearly
labelled and confirms the recorded payment; it never claims access activation.

## Sources and transaction boundary

| Purpose | Existing source and integration | Uniqueness and lifetime |
| --- | --- | --- |
| Requested setup assistance | Owner reviews exact masked recipient, Workspace, text and link; confirms a signed ten-minute review through POST | One SetupRequest per Workspace/contact/enrollment revision; one Delivery/request; 24-hour preview |
| Trial confirmation | billing.start_trial captures the newly created trial.started SubscriptionEvent before commit | One Delivery/event; still-current active trial; 24-hour preview |
| Subscription payment confirmation | Existing send_checkout_receipt boundary receives capture_whatsapp=True only from a newly applied checkout or recurring-cycle capture | One Delivery/Invoice; matching captured Payment and frozen test/live mode; seven-day preview |

The source, email intent where applicable and WhatsApp intent commit together.
Source rollback removes all new intent. Unexpected local persistence errors use
the existing source transaction recovery instead of recording false success.
External sending will occur outside that transaction in a later slice, so a
provider failure cannot undo a committed payment.

Invalid/missing pairing or consent skips WhatsApp. Unknown or mismatched historical
provider evidence skips WhatsApp while preserving the existing source/email path.
Consent and verification must precede the source's local recorded timestamp;
provider-paid time is distinct from when Rokkad records a newly observed payment.
Replayed captures return their existing result, and ordinary email receipt retries
use the default capture_whatsapp=False. Enrollment, viewing, consent changes and
migration never scan or backfill historical trial/payment sources.

## Schema and authority

Migration platform_whatsapp.0002_source_intents adds two directly Workspace-owned,
non-null, forced-RLS tables. They refine the initial global-delivery sketch in the
[accepted ADR](../adr/2026-10-14-platform-whatsapp-delivery-boundary.md).
The exact ownership registry now covers 149 models.

| Model | Retained evidence and guards |
| --- | --- |
| SetupRequest | Workspace, contact/revision, immutable consent relation and request time; unique enrollment revision; immutable inserts only |
| Delivery | Exactly one typed setup request, trial event or paid invoice; owner, recipient and Workspace-name snapshots; contact/consent/template/sender revisions; source fingerprint/time, frozen provider mode, creation and expiry |

Database checks enforce exactly one purpose-compatible source, positive enrollment
revision, expiry after creation and capture_only=True. Unique source relations
prevent duplicates. Both new tables reject UPDATE/DELETE through database triggers.
Composite foreign keys bind consent/setup evidence to the same Workspace. Write
guards verify current canonical owner/contact/consent, chosen category, recipient
snapshot, source-time pairing/consent, global trial/invoice source Workspace and
paid source/mode correspondence. These checks apply to bulk/direct restricted-role
DML, not just forms. No generic CRUD permissions are introduced.

Global account services resolve the explicit Workspace, enter workspace_context
and repeat canonical billing-owner checks. Platform override cannot grant consent
or expose another owner's history. A transferred owner cannot see the predecessor's
saved recipient/source previews. Account-level opt-out remains available when
business access is restricted and never grants business actions.

Every saved preview rechecks current ownership, contact revision, latest consent,
category, suppression, sender/template revision, expiry and original source facts.
Revocation followed by re-selection does not revive old consent evidence. Converted,
expired or changed trials fail review; changed payment/source evidence cannot be
rendered as a new confirmation. Routine setup/trial guidance requires active
lifecycle; an authentic paid receipt does not reopen business access.

Links use Django reverse and the existing authenticated setup/billing/invoice
routes. A valid configured canonical HTTPS root produces absolute links. Missing
or malformed origin produces a local preview link plus an eligibility blocker;
it never establishes delivery readiness. Numbers are masked in owner HTML. No
arbitrary recipient composer, raw borrower/provider payload or payment credential
is added.

## Verification

313 distinct selected regression cases pass across the focused/broader/corrected
Notify runs and final reruns; the saved manifest records exact test IDs. All 38
PW-02 source cases pass against the final reapplied migration, including:

- Source rollback and injected local-write failure; no provider send; trial,
  one-off checkout and recurring-cycle parity with existing email.
- Replay, late enrollment and email retry without backfill; parallel setup
  confirmations and payment callbacks produce one source intent under restricted
  NOSUPERUSER NOBYPASSRLS roles.
- Signed review expiry, changed consent/content, foreign actor, STOP/re-selection,
  ownership transfer, missing origin, trial conversion, expiry and source changes.
- Forced RLS, immutable evidence, wrong-Workspace bulk inserts and direct foreign
  global SubscriptionEvent/Invoice linkage rejected by database guards.
- Existing billing/access/provider-mode, SES/account email, Workspace ownership,
  tenant isolation, Notify v2 and architecture boundaries.

Fixture-only decimal/payment-ID and suite-label mistakes were corrected. SQL
reformatting damaged dollar quoting once; the final SQL matches the tested original
exactly and the final migration/guard run passes. No unresolved test failure remains.
All-model makemigrations --check --dry-run reports no changes. Syntax/import guards
include the untracked new app as well as existing supported source. Current document
links and scoped whitespace checks pass.

Using owner-only migration settings in the exact disposable test database, a
populated PW-01 fixture retained consent/enrollment, trial sources, paid Invoice/
Payment and email receipt hashes/counts exactly through upgrade, reversal with
empty new tables, and reapply. No historical WhatsApp rows were backfilled; all
four Workspace-owned WhatsApp tables retain forced RLS. This does not authorise
reversing a database containing real setup/delivery evidence.

Five fictional HTTP states (setup review, saved setup, trial, paid receipt and
paused receipt) are checked in offline Chromium at 1440px and 390px. All ten
states load the exact cached Bootstrap asset, wrap without horizontal overflow,
mask phone numbers and have unique preference IDs. Consented categories remain
checked; pausing clears stale choices. New review/confirmation buttons have
44px minimum height. Fictional fixture writes and temporary roles roll back.
This is Django POST plus static browser layout verification, not real device,
screen-reader, provider pairing or delivered-message acceptance.

Artifacts: outputs/pw02-verification contains fictional HTML/PNGs, layout-results.json,
migration-preservation.json, and test-manifest.json. tmp/pw02-focused.log,
pw02-regressions.log, pw02-notify.log and pw02-final-intents.log record runs.
Both exact task databases are removed after verification. Existing review and
production databases are untouched.

## Release and next slice

Code is locally verified, uncommitted and not deployed. Apply the new migration
through django_project.settings.migration before source hooks or the account page
run against an existing review/production database. Web/workers retain restricted
runtime roles. Do not reverse populated immutable evidence: compatible code
rollback retains tables and source transactions; disable WhatsApp separately from
email. Capture-only history can never become live by flipping a setting or row.
A later actual-send record/attempt must preserve that distinction explicitly.

PW-03 was subsequently authorised and [verified locally](platform-whatsapp-transport-pw03.md):
bounded Cloud transport, durable attempts and authenticated status reconciliation.
Native source writers remain capture-only and missing release controls still block
activation. [PW-04](platform-whatsapp-controls-pw04.md) is now locally verified.
PW-04 implements scheduling, reviewed announcements and count/spend caps; PW-05 retains
full operating UI and the named consented live pilot. Actual sender/template
approval, canonical deployment origin, tariff/monetary cap, real-person retention/
erasure and monitored support remain release inputs. No provider account, sender
configuration, template submission, real message or live acceptance occurred.
