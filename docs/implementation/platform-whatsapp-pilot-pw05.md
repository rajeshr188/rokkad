---
status: local-verified-live-pending
owner: project
updated: 2026-10-14
tags: [implementation, whatsapp, diagnostics, pilot]
---

# PW-05 diagnostics, reviewed operations and pilot readiness

PW-05 adds local owner/platform diagnostics and a concrete first-pilot handoff.
The real JCL pilot awaits sender/template setup and compatible deployment. The
owner monitors support@rokkad.com. Deployed JCL's canonical owner matches the
privately supplied account; the local copy differs. Production has no WhatsApp
app/tables. No production changes, real messages or template submissions occurred.
See the [sender/template handoff](../plans/platform-whatsapp-sender-setup-20261014.md).

## Local behavior

The global console at `/app/platform/whatsapp/` requires existing active-superuser
authority. It checks at most 100 explicit Workspace IDs or the private pilot cohort,
using successive matching RLS contexts. Counts, latest five messages/Workspace,
seven budget days, masked recipients, template gaps, reservations and partial
tariff estimates are read-only. A receipt outside selected matches may be unmatched
or linked outside the selection; hidden links are never globally called unmatched.
Repeated delivery/read observations do not double-count one reservation's estimate.
Provider invoiced charges are not integrated or claimed.

Owner account history at `/app/account/whatsapp/<slug>/history/` shows latest 25
recorded-current-owner sources and scoped counts. Canonical owner checks exclude
staff, platform override and predecessor history after transfer. Invoice detail
shows independent email/WhatsApp receipt status to the canonical owner; delivery
cannot change payment/access. Account history does not grant blocked business
actions. GET never sends, reconciles pending evidence or changes sources; pages
are private/no-store.

A definite transient rejection may be reviewed by its recorded current owner after
bounded backoff. Signed ten-minute confirmation binds actor, exact route/action,
Workspace/source, consent/contact revision, configuration/content and attempt/link
evidence. CSRF and unchecked acknowledgement are required. Non-atomic confirmation
calls durable dispatch, which repeats source/capacity checks before IO. Captured,
accepted, unknown and exhausted attempts cannot retry. Changed consent, ownership,
configuration, route or evidence requires another review.

An operator can review reconciliation for one exact source. POST attaches only
authenticated matching receipts and can recover a stale claim as unknown. It never
sends, fabricates an accepted ID or clears uncertainty. Completed reviewed actions
retain actor/source/status audit metadata. Audit follows the durable operation and
cannot roll back external acceptance.

Read-only `check_platform_whatsapp_pilot` requires a restricted standalone runtime
role and explicit authorized actor, slug and owner email. It returns IDs, owner-match,
masked recipient and blockers without echoing email/secrets. Missing PW-04 tables/
migration yield a schema blocker without querying absent contact storage. Schema
presence is not full release verification. Private retention/support references
gate dispatch and bind configuration reviews; neither proves approval or implements
deletion.

## Operational resolution limits

Retry only a known retryable rejection; email retry never generates WhatsApp history.
Reconcile recorded IDs and inspect retained facts. Acceptance without an ID stays
unknown pending provider investigation; never invent an ID or send a replacement.
Conflicting receipts retain delivered/read proof and contradictory failure evidence.

Pricing uncertainty stays fail-closed. Inspect reservation, dated tariff and
authenticated category/model. Do not guess prices, delete receipts, release slots
or clear holds through arbitrary SQL. This increment implements no pricing-hold
resolution workflow or provider-invoice cost reconciliation. These require verified
external facts and a separately reviewed append-only correction contract. A hold
stops expansion rather than asserting resolution. Retention automation and a shared
support inbox also remain outside this increment.

## Verification and rollback

All 424 distinct selected regressions pass in one final combined run (802.113s),
including 25 PW-05 cases. The affected invoice HTTP case passes again after its
phone header was made responsive. Twelve 1440px/390px Chromium states have no
horizontal overflow or duplicate IDs; reviewed actions are 44px high and
acknowledgements start unchecked. CSS/assets were served locally with external
requests blocked; this is synthetic rendering, not real-device acceptance.
Restricted-role diagnostic GETs preserve populated invoice/payment/subscription,
email and source/attempt/receipt/reservation/cost hashes exactly. No IO is performed
by GET; every test provider request is mocked. System/all-model drift, 39 app Python
AST/import checks, 1,125 tracked and 77 untracked source-boundary checks pass.
Both exact PW-05 disposable databases are removed. Evidence is retained in ignored
outputs/pw05-verification and tmp/pw05-* logs.
No PW-05 model/migration is added; 155 owned registry entries and PW-04 forced RLS/
immutable source/correlation/reservation guards remain authoritative.

Rollback stops dispatch/intent creation, retains source/payment/email/message
evidence and restores compatible code. Never reverse populated PW-04 schema or
restore old data over newer transactions. Read-only diagnostics do not substitute
for deployment restore/rollback acceptance. The prior
[PW-04 preservation/downgrade rehearsal](platform-whatsapp-controls-pw04.md)
is historical evidence, not a newly performed production restore.
