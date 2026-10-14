---
status: active
owner: project
updated: 2026-10-15
tags: [domain, notifications]
---

# Notifications

Notify v2 is the supported borrower-notification delivery app. Loans owns notice intent and the financial
facts behind it; delivery attempts and provider outcomes do not determine loan
state. Customer notice creation/retry and internal scheduled delivery have separate
authorization boundaries. Keep batching, retries and delivery evidence testable.

A borrower correction binds later loan notices to the current Party and the
immutable correction identity. Previously queued notices cannot inherit that
identity, even when both Parties share an email/phone address; the corrected Party
needs independent consent and current financial/risk readiness. A native risk event
can retain its former notice and receive one reviewed notice for the corrected
identity. The database still rejects duplicate intents for that identity. Delivery
evidence and original notice payloads stay available. See the
[origination release](../implementation/origination-production-release-20261015.md).

The operator opens Notifications, filters batches by name/event or status and
reviews a batch's recipients, documents and attempts. Sending eligible digital jobs
is an explicit edit-authorized POST; already sent/cancelled jobs are skipped.
Printing/posting buttons record handling and do not themselves print or send.
Batch status and a job's Sent status do not prove receipt. Connection checks and
stored credentials likewise do not replace provider delivery acceptance. Advanced
template/policy administration stays behind its existing staff/domain requirements.

Read [action permissions](../implementation/action-permission-review.md),
[Workspace operator commands](../implementation/loans-operator-commands.md), and
[private media](../implementation/private-media-access.md) before changing delivery,
exports or attachments. Provider acceptance must not be inferred from mocked tests.

Legacy Notify is retired. Prior redesign notes and integration investigations remain
in the [historical snapshot](../archive/context/2026-09-09/domain/notifications.md)
and [notification archive](../archive/notifications/).

Platform invitations and paid subscription receipts use the separate control-plane
[platform mail queue](../implementation/platform-mail.md). Its source transaction
records intent; delivery never determines membership acceptance or payment truth.
Shared Django account-security mail is a separate, still-captured path. Keep these
purposes distinct from Workspace-owned borrower notices.

## Platform owner WhatsApp

The locally verified PW-01 platform_whatsapp app owns Rokkad-to-owner account
enrollment and opt-out evidence. Per-Workspace Preference and ConsentEvent rows
have direct ownership and forced RLS; current canonical owners alone choose their
categories. Number/pairing revisions and ownership changes invalidate old choices.
A paired WhatsApp account is not legal identity or consent to every category.

The exact default-disabled global inbound endpoint accepts authenticated pairing
and opt-outs, not borrower content. Its readiness/drafts always remain preview
only. PW-02 adds immutable Workspace-owned SetupRequest/Delivery records, exactly
one typed setup/trial/paid source and source-time pairing/consent. Setup uses a
signed reviewed request; native trial/payment commits record eligible previews
beside independent existing email. Replays, email retries and enrollment never
backfill old events. Current source/owner/consent changes block eligibility, and
capture-only records cannot become live through configuration. Outbound delivery has no live
activation. PW-03 implements committed restricted-role attempts and a bounded
Cloud template adapter behind an unconditional gate awaiting PW-04 controls. Minimal
authenticated status receipts remain global until a known scoped attempt proves the
provider ID/sender/recipient match. Immutable receipt links project delivered/read
monotonically and retain failures/conflicts; unknown acceptance cannot auto-resend.
Native source writers still capture only. Platform mail keeps independent SES
evidence and Workspace Notify keeps borrower traffic.
See [PW-03 evidence](../implementation/platform-whatsapp-transport-pw03.md),
[PW-02 evidence](../implementation/platform-whatsapp-source-intents-pw02.md),
[PW-01 evidence](../implementation/platform-whatsapp-enrollment-pw01.md)
and [delivery plan](../plans/platform-owner-whatsapp-phase1-20261014.md).

PW-04 adds one reminder on the three local dates before the accepted trial-expiry
date, with no current access override/conversion/end change, and reviewed service
notices for exact affected Workspaces. Owners with several affected Workspaces
receive one notice, retaining scoped target evidence. Global job checks use
successive explicit Workspace contexts; a message never reopens access. Default-off
intent/dispatch flags, named cohorts, dated tariffs and immutable daily count/spend
reservations protect new sends without promoting captures. Unknown/conflicting
pricing holds sending; callback tariff estimates are not provider invoice charges
or Loans postings. Actual consented acceptance and operational resolution remain
PW-05. See [PW-04](../implementation/platform-whatsapp-controls-pw04.md).

PW-05 adds canonical-owner history and independent invoice message status, plus
bounded platform diagnostics. Reading status cannot send, reconcile callbacks or
change payment/access. Reviewed retry permits only a current owner's definite
retryable rejection; unknown/accepted/captured evidence cannot resend. Operator
reconciliation attaches exact authenticated facts without sending. Unknown pricing
holds remain blocked; no automated correction or billed-cost integration is claimed.
Deployed JCL owner metadata is verified read-only, but sender/template setup,
compatible deployment and real consented acceptance remain pending. The owner
monitors support@rokkad.com; ordinary WhatsApp replies are not forwarded there.
See [PW-05](../implementation/platform-whatsapp-pilot-pw05.md).
