---
status: verified-local
owner: project
updated: 2026-10-14
tags: [implementation, whatsapp, consent, control-plane, rls]
related:
  - ../plans/platform-owner-whatsapp-phase1-20261014.md
  - ../adr/2026-10-14-platform-whatsapp-delivery-boundary.md
  - ../architecture/control-plane-contracts.md
  - ../domain/notifications.md
---

# PW-01: owner WhatsApp enrollment and consent

## Delivered locally

The owner authorised PW-01 after reviewing the phase-one design and its next
implementation slice. The small platform_whatsapp app now provides optional
account enrollment, per-Workspace consent, authenticated inbound pairing/opt-out,
offline readiness and read-only message drafts. Outbound delivery is absent:
can_send is always false, there is no dispatch worker/HTTP send call, and this
slice does not insert setup/trial/invoice notification intents.

Account Settings links to /app/account/whatsapp/. The page uses the global
account shell, masks the saved number and leaves all categories unchecked until
the current owner chooses them. Phone entry uses the installed phone-number
library with India default/E.164 storage, rejecting extensions and notes.
Language is explicitly English for this increment. Pause/disconnect and
category changes are normal CSRF-protected POSTs; GET never creates enrollment.

Enrollment returns an unpredictable pairing code only in the request response.
Only its SHA-256 hash is stored. It expires after 15 minutes; issue requests have
a 60-second cooldown and five/hour limit. Five failed matching messages invalidate
the challenge. Provider timestamp validation allows one second for integer-second
rounding, not stale issuance. A signed message from the exact entered phone is
required to pair. No browser or operator action can directly mark pairing successful.

Categories are chosen in a separate explicit form and recorded even while pairing
is pending; pending choices cannot be delivered. A number change or reenrollment
advances the contact revision, invalidating prior preferences. STOP and equivalent
clear opt-outs suppress that phone across platform messages and advance revision.
START alone does not restore permission. Fresh pairing plus reviewed categories
is needed to resume. Disconnect clears the current number and releases its
single-account binding; pause retains the binding. Pairing evidences account
access at that time, not legal identity, SIM ownership or KYC.

## Persisted boundary

Migration platform_whatsapp.0001_initial adds six narrow models:

| Model | Ownership and evidence |
| --- | --- |
| Contact | Global account OneToOne; one non-empty phone binding; state/revision, hashed challenge/expiry and pairing configuration fingerprint |
| ContactEvent | Global account contact/revision/kind/time; database-immutable |
| Suppression | Global phone hash/time; no stored raw inbound text |
| InboundReceipt | Global unique Meta inbound ID/outcome/time; replay protection, not outbound delivery evidence |
| Preference | Direct non-null Workspace ownership; one row/Workspace, contact/revision, three booleans, English language and consent version |
| ConsentEvent | Direct non-null Workspace ownership; contact/actor/revision, chosen booleans, text version/time; database-immutable |

Preference and ConsentEvent use forced PostgreSQL RLS and exact registry/migration
coverage. They are deliberately Workspace-owned, refining the design's initial
global preference proposal. Database write guards require the Workspace's current
owner contact; consent actor must own that contact. History remains readable only
in the matching Workspace context. Model default CRUD permissions are empty.

Account services require an active authenticated global actor. They resolve the
exact target Workspace and enter workspace_context explicitly, reuse
require_billing_owner and require the canonical owner as recipient. Platform
override cannot consent on another user's behalf. Number/account settings never
derive scope from a navigation preference. Ownership transfer does not confer the
previous owner's consent on the successor; current ownership and contact revisions
are checked on every draft. Global preferences permit revocation when commercial
access or operational lifecycle restricts business entry; this grants no business
action, trial or entitlement.

No borrower tables, source financial events, subscription/Invoice/Payment state
or Workspace lifecycle are written by this feature.

## Inbound authentication and readiness

The exact /app/integrations/whatsapp/webhook/ route handles enrollment and STOP
only. It requires global request/RLS context, an explicit inbound-enable flag,
configured WABA/phone IDs and secret material. GET checks the verification token;
POST checks HMAC over original bytes, object, exact WABA and phone ID, bounded
payload/message sizes and timestamps. Every entry is validated before mutation;
processing and receipt deduplication share a transaction.

Other inbound text is ignored. No support auto-reply or agent inbox is implemented.
Provider delivery-status handling stays in PW-03. Workspace callback exemptions
and credentials are not reused; existing borrower integration tests still pass.
No raw inbound body, plaintext pairing code, signature, app secret or verify token
is persisted in the new evidence records.

Private deployment settings are PLATFORM_WHATSAPP_INBOUND_ENABLED (default false),
PHONE_ID, WABA_ID, APP_SECRET, VERIFY_TOKEN, SENDER_NUMBER, BASE_URL and VERSION
under the PLATFORM_WHATSAPP_ prefix. Tests explicitly clear inherited credentials
and inbound enablement. No sender registration/configuration was performed.

check_platform_whatsapp makes no network call and prints only presence/validation
diagnostics. Configured inbound reception is not Meta identity approval or actual
delivery readiness. Message drafts always show preview-only status; credentials,
successful pairing or flags cannot enable outbound sends in PW-01.

## Verification

The final selected broader run passed 100 tests. Four final UI/consent checks
also pass, two overlapping the broader run: 102 distinct passing cases, including
33 new enrollment tests. These cover:

- Global/account and explicit Workspace authority; canonical-owner-only consent,
  no platform impersonation, ownership transfer and restricted-role cross-Workspace
  reads, bulk inserts and wrong-owner contact linkage.
- Unchecked/default consent, checked selections and revocation, pending pairing,
  number uniqueness/change, pause/disconnect, STOP/replay and safe resumption.
- Pairing expiry, request/match limits, stale/wrong-number codes, replays and
  credential-version changes.
- HMAC/WABA/phone mismatches, malformed/partial payloads, non-ASCII signatures,
  timestamp checks, disabled reception, CSRF and HTTP methods.
- Draft escaping/masking, secret non-disclosure, no financial/account source writes
  and no readiness claim of delivery.
- Existing platform mail/account email, billing/request boundaries, setup and
  Workspace WhatsApp integration behavior.

Test fixtures execute under NOSUPERUSER NOBYPASSRLS roles. Fresh test migration
and all registry metadata checks pass. An initial test-discovery import issue
and failed-DML savepoint fixture were corrected; final counts above refer to
the corrected runs.

The empty PW-01 migration was reversed and reapplied in the disposable database
using owner settings. Existing Company/subscription/Invoice/Payment/PawnLoan row
counts stayed unchanged. This is an empty-new-table schema rehearsal, not approval
to reverse migrations containing real consent history. Rollback of a later live
release must preserve contact/evidence tables and source transactions.

All-model makemigrations --check --dry-run, syntax/new-source import guards and
the existing supported-app guard pass. Document references are checked separately.

Three fictional HTTP-rendered states (empty contact, pending pairing and draft)
were examined in Chromium at 1440px and 390px: all six have no horizontal overflow,
no duplicate preference field IDs and no preselected categories. Long Workspace
names wrap and checkboxes use touch-friendly label controls. The test used the
exact cached Bootstrap 5.3.8 asset with matching integrity hash, local styles and
no app/network mutations. This is static browser layout plus Django POST verification,
not real device/screen-reader or provider acceptance. Fictional fixture writes
and temporary roles roll back.

Artifacts: outputs/pw01-verification contains rendered fictional states, six PNGs
and layout-results.json; tmp/pw01-regressions.log and
tmp/pw01-final-ui-tests.log record the passing runs. Both exact task databases are
removed after verification. Existing review/production databases were not migrated.

## Release and next work

Code is locally verified, uncommitted and not deployed. Migration is required
before serving the new preference page in a review or production database.
Real-person retention/erasure, actual sender/number ownership, supported API,
templates, cost controls and consented pilot remain separate release inputs.
Protected contact/history references intentionally prevent casual deletion;
a future authorised retention/erasure path must account for them.

PW-02 was subsequently authorised and [verified locally](platform-whatsapp-source-intents-pw02.md):
durable source-backed setup/trial/paid intents and controlled previews preserve
the existing email receipt path. PW-03 supplies outbound
transport and status reconciliation; [PW-04](platform-whatsapp-controls-pw04.md)
reminders/announcements/caps are also locally verified, while PW-05
the full operating UI/live pilot remain pending.
