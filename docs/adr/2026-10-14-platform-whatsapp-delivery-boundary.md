---
status: accepted
owner: project
updated: 2026-10-14
tags: [adr, whatsapp, control-plane, delivery]
related:
  - ../plans/platform-owner-whatsapp-phase1-20261014.md
  - 2026-09-26-durable-platform-mail.md
  - 2026-08-14-whatsapp-cloud-api-only.md
  - ../architecture/control-plane-contracts.md
---

# Platform WhatsApp enrollment and delivery boundary

## Context

The owner selected platform-to-owner WhatsApp first and requested phase-one design.
platform_mail delivers global SES invitations, invoices and account email.
Notify v2 owns Workspace borrower jobs/Cloud credentials. Neither is a generic
platform messenger.

platform_mail.Delivery enforces invitation/invoice/account-email sources, email
recipients and SES-specific states/events. Notify v2 requires Workspace context
and contains borrower notice data. A dummy Workspace for Rokkad traffic would
confuse ownership; turning email into a universal messenger broadens a proven
path without a current need to migrate it.

## Decision

Use a small Django platform_whatsapp app for Rokkad-to-owner communication through
Meta Cloud API. Keep a private deployment sender and an exact global authenticated
webhook. Never use Workspace credentials, customer jobs or broaden their callback
exception.

Store global account enrollment and typed control-plane evidence. Sources are
explicit setup requests, SubscriptionEvents, paid Invoices and reviewed service
announcements. Bind source, owner/Workspace and consent/contact/template revision,
with unique intent keys. No borrower payload, general CRUD or arbitrary recipients.
Future business-owned tables still need direct ownership, forced RLS and registry/
isolation coverage.

Reuse existing policies/source services, libraries and ordinary Django patterns.
Do not refactor platform_mail/Notify v2 into a channel framework. Limited explicit
Cloud transport code is preferable to tenant-job coupling for platform messages.

Commit intent with its source transaction, claim attempts durably and call Meta
outside business transactions. Recheck source/authority/consent before dispatch.
Require real IDs and authenticated receipts; delivered/read facts remain monotonic.
Unknown acceptance prevents automatic retry; external exactly-once is not promised.

Keep email and WhatsApp activation, suppression and delivery evidence independent.
Message failure never changes payment, subscription, trial, Membership, access
or loan state. The platform sender cannot substitute for Workspace customer traffic.

## Consequences and status

There is one small additional delivery path to test/operate. Existing email and
borrower boundaries stay intact. Source intent hooks share the receipt boundary
without sharing transport states.

The owner authorised PW-01 implementation on 14 October. Its global account
enrollment and exact inbound pairing/opt-out boundary are locally verified.
Preference and ConsentEvent refine the design: they have direct non-null Workspace
ownership, forced RLS and registry coverage; account/global context never substitutes
for scoped ownership or action checks. PW-02 is now locally verified after explicit owner instruction. SetupRequest and
Delivery refine the global sketch with direct non-null Workspace ownership, forced
RLS, registry coverage, immutable evidence and typed source/consent database guards.
Source transactions capture previews beside independent email; a capture_only
constraint prevents later flags from promoting stored previews to live sends.
The signed setup review, source/authority rechecks and original-source uniqueness
are part of this contract. No outbound transport is implemented. Attempt and
announcement schemas remain subsequent work; their ownership must be explicit. Retention and live-provider acceptance remain
release requirements. See [PW-01](../implementation/platform-whatsapp-enrollment-pw01.md) and
[PW-02](../implementation/platform-whatsapp-source-intents-pw02.md).


## PW-03 refinement

Continuation authorised PW-03, now locally verified. Attempt and ReceiptLink are
directly Workspace-owned with forced RLS and composite source/correlation guards.
ProviderReceipt is a minimal global authenticated inbox because an early/unmatched
provider ID does not prove a Workspace. Reconciliation uses a known scoped attempt
and exact recorded ID/sender/recipient; no global tenant scan or callback RLS bypass.
Attempts commit before bounded IO and complete once. Immutable receipt facts feed
read-only monotonic delivery/read projections; uncertainty cannot auto-resend.

Delivery's creation schema now admits future non-capture sources; immutable history
cannot change mode, and every current native writer explicitly creates captures.
The old always-true creation check is replaced by attempt-level prohibition on
captured sources. Dispatch additionally has an unconditional release-control gate
until PW-04 implements cohort/count/spend reservation. Flags cannot promote history
or activate missing controls. Populated attempt/receipt or non-capture evidence blocks
schema downgrade; compatible code rollback preserves history and source transactions.

360 distinct selected cases and source-preserving migration/layout checks pass.
Actual sender/template/version, tariff/cap, retention and live acceptance are not
established by mocks. See [PW-03](../implementation/platform-whatsapp-transport-pw03.md).

## PW-04 refinement

Continuation authorises current trial scheduling, reviewed platform service notices
and conservative pilot reservations. TrialReminder, AnnouncementTarget, Reservation
and CostEvidence are directly owned/forced-RLS; Announcement is a global reviewed
platform publication, and BudgetDay/ContactDay are minimal global aggregates.
Sorted global job locks and successive explicit scoped units recheck a deduplicated
owner's reviewed targets without switching a conflicting active Workspace context.

The source/dispatch flags default off. Only new, named-cohort/purpose sources within
a dated pilot can create non-capture intents; captured history never promotes. Every
new attempt reserves count and the maximum configured category estimate atomically
before claim. Reservations never release, including uncertainty. Known callback
tariff estimates are distinct from actual invoiced charges; unknown/conflicting
pricing pauses further sends. No cost changes Loans or customer charges.

Empty PW-04 schema reverse restores PW-03 guards and preserves its accepted/read
evidence. Retained PW-04 source/capacity/cost evidence blocks downgrade. Operational
resolution, actual sender/templates/tariff/cap/retention and real consented acceptance
remain PW-05 release work. See [PW-04](../implementation/platform-whatsapp-controls-pw04.md).

## PW-05 local diagnostics refinement

Owner history and invoice status use canonical current-owner authorization and
explicit scoped reads. The platform console uses its existing global authority
and bounded selected Workspace contexts. GET never sends or ingests pending facts.
Signed reviewed retries allow only definite transient rejection, rechecking source,
consent, configuration, backoff and capacity through the durable dispatch service.
Reviewed operator reconciliation never sends or invents provider IDs. Reservations
and known tariff estimates remain distinct from provider invoiced charges.

Private retention/support references gate transport; they do not implement erasure
or prove policy adoption. Pricing-hold resolution remains fail-closed pending verified
external facts and a separately reviewed append-only correction workflow. No new
schema or isolation exception is introduced. JCL is the selected pilot; deployed
canonical owner metadata is verified read-only, while sender/template setup and
production app/schema deployment are absent. The live pilot remains pending. See
[PW-05](../implementation/platform-whatsapp-pilot-pw05.md) and the
[sender handoff](../plans/platform-whatsapp-sender-setup-20261014.md).
