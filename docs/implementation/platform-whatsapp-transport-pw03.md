---
status: verified-local
owner: project
updated: 2026-10-15
tags: [implementation, whatsapp, transport, receipts, control-plane, rls]
related:
  - platform-whatsapp-source-intents-pw02.md
  - ../plans/platform-owner-whatsapp-phase1-20261014.md
  - ../adr/2026-10-14-platform-whatsapp-delivery-boundary.md
  - ../architecture/control-plane-contracts.md
  - ../domain/notifications.md
---

# PW-03: Cloud transport, durable attempts and receipt reconciliation

Later software delivery is complete in the [15 October combined release](reviewed-production-release-20261015.md). This dated note retains its local implementation evidence. Production activation remains disabled; live sender and pilot acceptance are separate.

## Delivered locally

The owner's instruction to proceed after PW-02 authorises this implementation
slice. The platform_whatsapp app now has a bounded Cloud template transport,
committed attempts, authenticated status ingestion and explicit scoped receipt
reconciliation. Existing owner previews show accepted, delivered/read, failure,
unknown and conflicting-evidence labels without sending from the page.

All production dispatch remains unavailable. Private DISPATCH_ENABLED defaults
false; release_blockers also unconditionally requires PW-04's missing cohort and
atomic count/spend controls. Flags or credentials cannot bypass that code gate.
Native setup/trial/payment writers explicitly retain capture_only=True. Migration
allows future newly created non-capture intents, but never updates, promotes or
backfills PW-02 history. A database trigger prevents any intent UPDATE/DELETE;
claiming a captured intent is rejected even through direct restricted-role DML.
Future writer activation and live acceptance remain separate work.

No provider connection, real message, template registration, actual delivery proof,
shared/review/production migration, commit or deployment occurred. Every provider
request in verification is mocked. Existing SES mail, Workspace borrower Notify,
financial source facts, trial dates, access and accounting remain independent.

## Attempt and request boundary

Dispatch starts with explicit Workspace/delivery IDs, outside any caller
transaction/context and under a restricted non-owner database role. It locks
Company, contact and intent in a consistent order, rechecks current owner,
consent/suppression, source facts/mode, expiry, HTTPS link and approved English
mapping, and commits a UUID attempt before external IO. A second connection test
proves the claim is visible before the provider adapter is called.

Immediately before the request, a fresh transaction checks claim age/outcome,
configuration and exact typed payload fingerprint again. No lock or transaction
spans network IO. Cross-system opt-out races cannot be made atomic; current checks
occur directly before IO, with late status evidence retained after STOP.

The request uses the fixed graph.facebook.com versioned phone-ID/messages endpoint,
bearer header, approved template name/locale and typed source body parameters:
setup name/link, trial name/original end/link, or live paid amount/invoice/link.
TEST/unclassified payment sources cannot enter chargeable transport. Template
mappings bind the existing source wording revision; setting approved=True locally
is not evidence of Meta approval. Real mapping/version/sender acceptance is required
before a pilot. No arbitrary recipient/message composer or provider framework exists.

Requests disables ambient proxies and HTTP retries, refuses redirects, keeps TLS
verification, uses five-second connect/twenty-second read timeouts and bounds the
response at 64 KiB. These are connect/read and byte bounds, not a promised total
wall-clock SLA. A validated wamid ID from an unambiguous response records accepted,
not delivered/read. Wrong recipient, malformed/missing ID, contradictory response,
redirect, unclassified response, timeout and connection ambiguity remain unknown.
Exception text, raw bodies, access tokens and recipient values are not logged or
persisted as diagnostics.

Only a structured definite HTTP rejection can be retryable: HTTP 429 or explicit
is_transient=True, with current eligibility rechecked. Retry delays are one then
two minutes, at most three attempts. Permanent rejection, accepted status and unknown
acceptance never automatically resend. Asynchronous failure callbacks are retained
for review; they are not an automatic resend instruction. External exactly-once is
not promised; competing local workers produce one claim/request.

An interruption leaves its committed claim. Explicit recovery after five minutes
marks it unknown and cannot resend it. If a late worker result arrives after that
recovery completed, the closed attempt remains unknown; unmatched provider evidence
is retained for operator investigation, not guessed into a correlation. A returned
ID that conflicts with another attempt also records unknown. Failure to persist a
response leaves committed claim evidence for recovery and cannot undo payment.

## Persisted ownership and callback matching

Migration platform_whatsapp.0003_attempts_and_receipts adds:

| Model | Scope and evidence |
| --- | --- |
| Attempt | Direct non-null Workspace ownership, forced RLS, source relation, UUID/ordinal/time, sender/config/content/template snapshots; single-use completion with outcome, actual provider ID and bounded diagnostic/HTTP status |
| ProviderReceipt | Global authenticated minimal inbox: unique event digest, sender IDs, provider ID, recipient hash, status/time, numeric error codes and selected pricing category/model/billable facts |
| ReceiptLink | Direct non-null Workspace ownership, forced RLS, immutable one-to-one receipt correlation to an explicit attempt |

The ownership registry covers 151 models. Composite foreign keys bind attempt to
intent and receipt link to attempt in the same Workspace. Database guards reject
wrong scope, captured/current-consent-invalid claims, mutable claim identity,
completed-outcome rewrites, evidence deletion and invalid receipt fields. Provider
IDs are unique per sender across attempts. A receipt link must match the recorded
ID, phone/WABA, recipient hash, scoped attempt and bounded clock-skew window.

The exact existing global callback validates HMAC over original bytes, WABA/phone
identity, messages field/product, containers, bounds and timestamp. It validates
all text/status entries before any mutation, persists deduplicated evidence before
acknowledgement, and never infers Workspace authority from chat, session preference
or unmatched Meta ID. Unknown/unsupported status shapes fail validation. The
implemented profile uses phone-number recipient_id; other identity profiles require
separate provider acceptance. No raw text/error details or additional pricing JSON
are retained. Pricing facts are evidence, not a monetary charge/reconciliation.

An early callback remains unmatched until the actual response ID is saved. Completion
reconciles within the known Workspace. Later callbacks are ingested globally and
matched by an explicit single-delivery reconciliation command; no global tenant
scan or callback-driven RLS bypass is introduced. Each pass links at most 100 new
receipts per attempt and excludes already linked receipts so later passes advance.
A periodic operating invocation is not installed in PW-03.

Status projection is read-only over immutable receipt links. Read/delivered proof
survives late sent, failed and deleted facts, including across attempts. Failures
and contradictions remain retained and visibly flagged. Deleted alone never proves
delivery. Late authenticated receipts after opt-out still reconcile without sending
an acknowledgement. Normal owner views repeat authority and hide the predecessor's
history after an ownership transfer.

## Configuration and commands

Four additional private settings under PLATFORM_WHATSAPP_ are DISPATCH_ENABLED,
ACCESS_TOKEN, API_VERSION and TEMPLATES. Tests clear inherited values. The mapping
for each supported purpose has exactly name, language, revision and approved fields;
only explicit English locales are currently supported. Credential rotation requires
the existing VERSION bump to invalidate sender acceptance. Actual API support and
Meta approval must be established with the eventual deployment sender.

check_platform_whatsapp remains offline and masks configuration; it reports the
missing release controls. Operational commands require a restricted runtime role
and positive explicit Workspace/delivery IDs:

~~~text
python manage.py dispatch_platform_whatsapp --workspace-id <id> --delivery-id <id>
python manage.py reconcile_platform_whatsapp --workspace-id <id> --delivery-id <id>
python manage.py reconcile_platform_whatsapp --workspace-id <id> --delivery-id <id> --recover-stale
~~~

Dispatch remains blocked in this slice. Reconciliation never calls the provider or
changes business source state. Queue enumeration, owner retries, sender operating
console, quiet hours, announcements and tariff/cap reservations remain later slices.

Protocol references checked on 14 October: Meta's official
[template request](https://www.postman.com/meta/whatsapp-business-platform/request/o65u5m5/send-message-template-text)
and [status objects](https://www.postman.com/meta/whatsapp-business-platform/folder/fuaee8l/statuses-object).
Direct developer pages returned access/rate-limit errors through the browsing tool;
the official Meta collection supplied the reference. Conservative uncertainty and
retry classification above are Rokkad implementation decisions, not promises of
provider approval or external exactly-once behavior.

## Verification and release limits

360 distinct selected cases pass: 47 PW-03 cases plus 313 existing enrollment/source,
billing/provider-mode/access, mail/account, ownership, RLS and Notify/architecture
regressions. The exact ID manifest excludes duplicates. Tests exercise committed
cross-connection claims, competing workers, repeated requests, response ambiguity,
bounded rejection retries, interruption, source expiry, ownership transfer, configuration/
consent changes before IO, early/foreign/replayed/out-of-order callbacks, STOP,
masked read-only status and adversarial restricted-role DML.

The first fresh combined run exceeded the tool's five-minute limit and is not
counted as verified. Durable-log reruns passed after correcting nullable-join row
locking, a release-gate test patch, Windows migration line endings and the auxiliary
runner import path. No unresolved failure remains. Syntax and new-app import guards,
existing supported-app guards, all-model migration drift, scoped whitespace and
current-document links pass. Final source review also rechecks the trial
Subscription's current Workspace; four affected source cases pass after that
small boundary correction.

A populated PW-02 fixture preserves exact consent/enrollment, setup/trial/paid preview,
Invoice/Payment and independent email row hashes through upgrade, empty-new-evidence
reverse and reapply. Six Workspace-owned WhatsApp tables retain forced RLS. Downgrade
with retained receipt evidence or a non-capture candidate is refused before destructive
operations; old capture modes stay unchanged. This is an isolated fictional rehearsal,
not a real data restore or authorisation to erase history.

Four fictional owner states (captured, accepted/unconfirmed, read with failure
conflict, and unknown) are HTTP-rendered under a restricted role and inspected in
offline Chromium at 1440px and 390px. All eight have masked numbers, unique preference
IDs, loaded exact cached Bootstrap, no horizontal overflow and 44px review controls.
Fixtures and temporary roles roll back. Real device/screen-reader and provider
acceptance remain unproven.

Artifacts are in outputs/pw03-verification: fictional HTML/PNGs, layout-results.json,
test-manifest.json, migration-preservation.json and source hashes. Durable passing
logs are tmp/pw03-locking-fix.log, pw03-final-dispatch.log, pw03-regressions.log
and pw03-final-source-scope.log.
Both exact task databases are removed; review services and production are untouched.

Apply the owner-only migration before compatible code against a review/production
database. Rollback retains intent/attempt/receipt evidence and disables dispatch
independently of email; never restore old data over later source transactions.
Actual retention/erasure, accepted sender/templates/version, canonical origin,
tariff/monetary cap, named consented pilot and monitored support remain release inputs.
[PW-04](platform-whatsapp-controls-pw04.md) now implements current trial scheduling,
reviewed announcements, atomic cohort/count/spend controls and controlled new intent
creation locally. PW-05 is next: operating diagnostics/resolution and a consented
live pilot after release inputs are settled. Captured history is never promoted.
