---
status: active
owner: project
updated: 2026-09-28
tags: [plans, future-work, ideas]
related: [active.md, completed.md, ../ROADMAP.md, ../STATUS.md]
---

# Future work

The main register for ideas we deliberately shelve and may pick up later. Record
enough context here to resume without reconstructing the conversation. An entry is
not a commitment, a scheduled task, or approval to implement it.

Use [active work](active.md) for work selected for delivery, [the roadmap](../ROADMAP.md)
for priorities, and [completed work](completed.md) for delivery history. Detailed
designs and decisions stay in their linked plans and ADRs. The older
[backlog](backlog.md) is historical input to review, not a second current idea queue.
Release requirements such as production media verification stay in their acceptance
plans; shelving an idea must not hide a release blocker.

## Register

| ID | Idea | State | Resume trigger | Where it stopped |
| --- | --- | --- | --- | --- |
| FW-001 | Optional owner-configurable license scope | Shelved; review and owner approval required | Owner chooses to revisit staff access across licenses | Direction documented; no license assignments or restrictions implemented |
| FW-002 | Razorpay setup and provider test-mode acceptance | Active preparation under FW-019; required before paid onboarding | Prepare isolated rehearsal runtime and provider workflow acceptance | Monthly/annual capture, webhooks, replay/recovery, refunds and one paid-test-receipt delivery pass; remaining methods and recurring acceptance open |
| FW-003 | Formal lender-specific NPA classification | Unscheduled design review; no implementation approval | Intended lender type needs regulatory NPA reporting | Existing per-loan operational DPD and collateral-risk classifications documented |
| FW-004 | Launch-scale loan monitoring capacity | Shelved at owner request | Better representative hardware is available and owner resumes testing | 300,000-loan baseline failed; million-loan fixtures prepared, latest retry stopped at owner request |
| FW-005 | Broader historical loan admission and quote-age policy | Partial scope implemented; remaining work unscheduled | Missing historical evidence or a guided import contract is needed | Native earlier payouts and explicit daily confirmations are implemented; wider exceptions remain deferred |
| FW-006 | Party bundle history progress filter | Shelved at owner request; optional usability | Operators need to find unfinished attempts in a larger history | Saved history and cancellation work; filtering not implemented |
| FW-007 | Guided customer-facing legacy migration | Recorded at owner request; future work, unscheduled | Owner selects self-service migration onboarding for delivery | Customer spreadsheets and prepared loan imports work; source-specific loan preparation still requires an operator |
| FW-008 | Servicing-only subscription restriction | Deferred beyond the pre-cutover continuity increment | Owner selects a collections-only stage after read-only/grace acceptance | Full access, seven-day grace, read-only and audited administrator decisions implemented; action-level servicing exceptions undesigned |
| FW-009 | Consent-based borrower identity verification / Aadhaar-assisted onboarding | Shelved at owner request; desk review complete | Owner explicitly resumes legal-entity clarification and written eligibility/pricing enquiries | App-sharing and hosted DigiLocker candidates compared; bounded pilot and unsent enquiry preserved |
| FW-010 | Platform administrator role, operational workflows and UI | Recorded at owner request; unscheduled, no implementation approval | Owner selects platform operations discovery and design | Existing authorization/control-plane foundations identified; coherent operator role, journeys and console need review |
| FW-011 | Platform and Workspace WhatsApp messaging and phone verification | Recorded at owner request; unscheduled discovery | Owner selects messaging product/policy review and integration acceptance | Workspace Cloud API foundation and acceptance plan exist; broader platform/workspace experience and verification need definition |
| FW-012 | Complete Workspace export and guided restore into a fresh Workspace | Existing M7 scope clarified at owner request; unscheduled | Owner selects complete archive/restore design and coverage acceptance | Partial Party bundles and bounded loan restore exist; whole-Workspace package and continuation workflow remain future work |
| FW-013 | Tamil Nadu prescribed forms and pledge book in English/Tamil | Recorded at owner request; unscheduled legal/form review | Owner selects statutory-document inventory, current-law verification and sample approval | Official Rules linked; preliminary form inventory and printing foundations identified |
| FW-014 | Domain-owned email and reliable platform/Workspace communication | Active: SES production access approved | Paid-receipt delivery and monitored activation | Mumbai approval verified 28 September; 50,000/day and 14/second; health monitoring enabled, dispatch disabled |
| FW-015 | Safe orphan-media cleanup and Workspace storage usage | Recorded at owner request; unscheduled | Owner selects media lifecycle and storage-metering design | Reported R2 orphans need inventory; safe cleanup, usage display and future billing measurement captured |
| FW-016 | Product blog | Recorded at owner request; unscheduled | Owner selects publishing scope and editorial workflow | Product stories, guides and release updates captured; implementation approach undecided |
| FW-017 | Community forum | Recorded at owner request; unscheduled | Owner selects community scope and moderation responsibilities | Questions, discussions and feature suggestions captured; access and moderation need design |
| FW-018 | Support ticket system | Recorded at owner request; unscheduled | Owner selects support workflow and operator responsibilities | Private customer support, tracking and resolution captured; integration approach undecided |
| FW-019 | Workspace subscription monetization and Razorpay automatic renewal | Active: owner selected delivery | Local implementation and provider acceptance | Held-access review and collection-attention guidance implemented; provider failure simulation unexpectedly captured, so actual failure/recovery and naturally due acceptance remain open |

## FW-019: Workspace subscription monetization and Razorpay automatic renewal

**Captured:** 2026-09-26. **State:** Active: owner selected delivery on 2026-09-26.
Latest receipt continuation: the exact-recipient command and 56 targeted tests pass.
One owner-approved receipt for the new monthly Test Mode payment reached
admin@rokkad.com's mail server, with one attempt and correlated SES Send/Delivery.
Temporary worker credentials/tunnel are removed; the settled test mandate is
cancelled with paid time/history preserved. Inbox/header/reply checks and general
activation remain open. See [receipt acceptance](../implementation/billing-provider-readiness.md#addressed-receipt-command-and-paid-fixture-2026-09-28).

Earlier continuation: the fully refunded annual test agreement is now explicitly
closed after settlement review, with dates/history and read-only access preserved.
Replacement exact-period handling passes local tests; actual replacement payment
and broader settlement policies remain. Both unresolved provider attempts are
preserved, and production remains disabled. See the
[release checkpoint](../implementation/recurring-agreements.md#refunded-agreement-release-and-replacement-2026-09-28).

Working prices are confirmed at INR 1,499/month and INR 14,990/year, with the owner
plus five staff (six members total). The offer remains unpublished. Razorpay
has reclassified Rokkad as software/SaaS; the owner reports application submission
and completed KYC. The owner confirms test-key generation and Subscriptions
are accessible; regenerated keys are verified through Payments and encrypted
locally. On September 27 the owner reported approval and Live/Test activation;
Payments/Plans/Subscriptions test APIs all return HTTP 200. Workflow acceptance
remains open; live-key generation is unknown. See the [active rollout](subscription-monetization-rollout.md)
for implementation stages and provider acceptance. The original proposal follows.

September 27 continuation adds the local recurring contract foundation: immutable
provider-plan bindings, durable creation attempts, explicit provider-ID recovery
and one open agreement per Workspace. It is operator-only, Test Mode-only and
default-off; provider status alone grants no access. See the
[runbook](../implementation/recurring-agreements.md). Verified paid-cycle processing
and recovery are now locally tested, including replay, delayed events, refunds and
restricted-role concurrency. Prepared owner authorization/cancellation is now
locally implemented, including durable uncertain cancellation recovery. September
28 actual Test Mode initial authorization/payment, signed replay, invoice recovery
and cancellation passed. Cancellation preserved six-member paid access and the
held agreement reservation. The accelerated renewal-failure attempt stayed Created
with an unpaid future invoice; renewal/failure recovery acceptance remains open.
Temporary callbacks are stopped and recurring authorization is disabled again.
Self-service creation, settled reservation release and scheduled transitions also
remain open; this is not production activation or full FW-019 completion.

A fresh September 28 diagnostic agreement proved recovery of a real Test Mode
initial capture with the webhook disabled. Its accelerated success attempt captured
after about six minutes. Its future invoice is now recorded once locally with
access held for review; existing Subscription fields and entitlements are unchanged.
Replay, including after period start, does not apply the hold. Owner/invoice/receipt
wording explains the separate review, and older agreements' review payments remain
visible. An authorized, audited Test Mode command now applies eligible started,
unexpired holds using fresh provider/refund/current-term checks and one immutable
resolution. Actual future provider evidence correctly remains unapplied. Naturally
due provider acceptance and failure/recovery remain next. Both test
mandates are cancelled after settlement; see
[current evidence](../implementation/recurring-agreements.md#future-period-financial-recording-2026-09-28).
Unpaid recovery also explains its status and preserves access. Validation covers
98 distinct held-access/recurring-cycle/owner/refund-review/checkout tests across
the two latest runs. Migration 0017 is applied only to the isolated rehearsal DB.
No live activation or production deployment occurred.

Latest continuation used a third fictional agreement to select **Charge as failure**
once. The payment instead progressed Created -> Authorized -> Captured while the
agreement stayed Active, so actual failure/Pending/Halted recovery remains open.
Reconciled the captured future period once with access held, then cancelled after
settlement. All three test mandates are cancelled and test authorization/mail/
callbacks remain off. Pending/Halted owner guidance and 50 cycle/owner tests pass.
Provider diagnostics and an unsent support draft are retained; see the
[latest rehearsal](../implementation/recurring-agreements.md#failure-simulation-continuation-2026-09-28).

Annual continuation passed actual initial capture/recovery/replay and cancellation
in a fourth fictional Workspace. The observed midnight-IST annual boundary is now
accepted with exact timestamps; six-seat paid access survives cancellation. All
four mandates are cancelled and authorization/mail/callbacks remain off. Annual
renewal/completion, actual failure recovery and naturally due application remain
open. See [annual evidence](../implementation/recurring-agreements.md#annual-provider-acceptance-2026-09-28).

The fifth fixture now has a captured/recovered initial annual period and one pending
final renewal attempt. At 01:34:08 IST it remained Created/Issued with the agreement
Active; preserve it for GET-only reconciliation. Four old mandates are cancelled;
the pending fifth is not. All 56 cycle/owner tests pass, including new completion
and contract-count boundaries. Production remains gated by the
[critical path](subscription-monetization-rollout.md#production-critical-path-reviewed-2026-09-28),
with no committed launch date. See [current evidence](../implementation/recurring-agreements.md#annual-final-charge-attempt-and-production-critical-path-2026-09-28).

The latest continuation submitted both provider reports (tickets 21146138 and
21146171), added immutable scheduled Test Mode starts, and passed actual full
recurring refund/owner end-access/replay acceptance on the earlier annual fixture.
All 127 focused recurring/review/recovery tests pass. A sixth short scheduled
fixture's INR 5 authorization remains Created despite Checkout reporting failure;
no paid invoice/access exists. Preserve that and the older annual pending attempt.
The earlier refunded annual Workspace is read-only with dates/history intact;
reservations stay held. Live operations, replacements and due-period acceptance
remain open. See the [latest checkpoint](../implementation/recurring-agreements.md#scheduled-start-support-and-refund-continuation-2026-09-28).

**Commercial direction.** Charge per Workspace, paid by its owner, with included
staff seats. Start with one core paid plan and monthly/yearly choices. Separately
quote assisted migration, reconciliation, configuration and training; price
WhatsApp/SMS usage or packages separately with a clear margin. Larger plans should
follow demonstrated customer needs and cost differences. SaaS fees remain separate
from borrower loan repayments and lending accounting.

| Proposed offer | Starting price to validate | Scope |
| --- | --- | --- |
| Rokkad monthly | INR 1,499 per Workspace/month | Core loans, customers, rates, documents and reports; 5 staff seats |
| Rokkad annual | INR 14,990 per Workspace/year | Same package; approximately two months free |
| Assisted onboarding | Separately quoted one-time fee | Migration, reconciliation, setup and training |
| Messaging | Separately priced usage/package | WhatsApp/SMS provider costs plus margin |

Display applicable taxes clearly. Validate willingness to pay, seat allowances,
support effort, hosting, storage and messaging costs before publishing prices.
At the proposed monthly rate, 100 paying Workspaces produce INR 149,900/month
before taxes, payment fees and operating costs; this is an illustration, not a
forecast. Storage billing depends on FW-015's auditable metering and a separately
agreed billable-usage policy.

**Existing foundation and gap.** Workspace plans, entitlements, invoices,
verified captured-payment activation and expiry access already exist. The
[current checkout](../flows/subscription-checkout.md) uses Razorpay Orders for
individual monthly/yearly paid terms; it does not implement automatic renewal.
New checkout is gated off pending deployment-specific provider acceptance.
FW-002 provider setup/test-mode acceptance is active under selected FW-019. Receipt delivery depends on FW-014's activation.

**Proposed recurring journey and implementation scope:**

1. Owner selects the Workspace plan/cycle. Server fixes the price and links a
   Razorpay subscription to the correct Workspace and local commercial contract.
2. Owner authorizes recurring payments through Razorpay Checkout using supported
   cards, UPI AutoPay or eMandate. Recheck account eligibility, method support,
   limits and current provider terms when selected for delivery.
3. Verified provider payment evidence activates/renews the purchased term and
   records payment, invoice, dates and audit evidence atomically. Browser success
   or mandate authorization alone must not grant a paid term. Deduplicate events
   and reconcile missed, delayed and out-of-order delivery without duplicate terms.
4. Allow cancellation of future renewal while retaining already-paid access until
   its end date. Define renewal reminders, failed-collection recovery, refund
   handling and plan changes before launch; keep the first version simple.
5. Preserve seven-day normal-access grace after natural expiry, then read-only
   access and permitted exports. Explicitly map recurring failures: current stored
   PAST_DUE enters read-only directly, so copying provider states blindly could
   interrupt paid access or bypass intended grace. FW-008's servicing-only stage
   remains a separate deferred capability.

Extend existing billing transitions and entitlement services; provider events must
not change Workspace identity, membership, permissions, lifecycle or RLS. Retain
owner-authorized billing recovery and immutable payment/refund evidence. Coordinate
operator recovery with FW-010 and messaging/email with FW-011/FW-014.

**Provider references, checked 2026-09-26.**
[Razorpay Subscriptions](https://razorpay.com/docs/payments/subscriptions/) describes
scheduled recurring billing and supported methods. Its
[pricing explanation](https://razorpay.com/blog/?p=26027) describes a 0.99%
subscription fee plus the underlying payment-method fee and applicable GST; the
2% gateway example is approximately 3.53% including GST on those fees. This is a
planning reference, not an account quote; recheck actual commercial terms before
setting margins. GST on provider fees is distinct from taxes on Rokkad's invoices.

**Delivery order when selected.** Finalize the offer; resume FW-002 merchant setup
and existing checkout acceptance; implement recurring subscriptions, cancellation
and recovery; complete provider rehearsals; then run a small paying pilot.
Validated prepaid monthly/yearly checkout can support first revenue before
automatic renewal. Acceptance must cover initial payment, successful renewal,
failed/retried collections, cancellation at term end, duplicate/delayed/out-of-order
webhooks, local rollback/reconciliation, invoice/receipt delivery, expiry/grace,
refund behavior and cross-Workspace isolation. Select an active delivery plan
before implementation; no provider setup, charges or production activation occur
as part of this documentation entry.

## FW-016: Product blog

**Captured:** 2026-09-26. **State:** Future work, unscheduled; no implementation approval.

Provide a public Rokkad blog for product stories, practical guides, announcements
and release updates, discoverable from the landing page. Potential scope includes
categories, search, illustrations, author/date information and shareable URLs.
Define an editor/publisher workflow for drafts, review, publication and corrections.
Reuse and link the existing user handbook where appropriate rather than maintaining
conflicting instructions. Do not publish customer or borrower data as examples.
Choose between a small native implementation and an existing publishing tool when
this work is selected; no provider or architecture has been chosen.

## FW-017: Community forum

**Captured:** 2026-09-26. **State:** Future work, unscheduled; no implementation approval.

Provide a place for customers to ask questions, share workflow advice, discuss the
product and suggest features. Candidate scope: searchable topics/categories,
replies, accepted answers and links to relevant guides. Decide public versus
signed-in visibility, posting eligibility, moderation ownership, reporting/spam
controls and notification preferences before launch. Participation must not expose
Workspace business records or confer access to another Workspace. Direct private
account, billing and borrower-specific issues to the support ticket system rather
than public discussions. Evaluate integration versus building when resumed.

## FW-018: Support ticket system

**Captured:** 2026-09-26. **State:** Future work, unscheduled; no implementation approval.

Allow customers to raise private support requests and follow their progress;
give platform support staff a manageable queue and a record of resolution.
Candidate scope: ticket reference, subject/category, description, controlled
attachments, assignment, priority, replies, internal notes and status transitions
such as open, awaiting response, resolved and reopened. Define requester versus
Workspace-admin visibility explicitly; internal notes remain staff-only, and
support access to a ticket must not grant unrestricted access to lending data.

Review how the existing `support@rokkad.com` inbox connects to ticket creation and
replies, including duplicate prevention, verified requester identity, notification
delivery and retention. Choose a hosted helpdesk integration or a minimal native
workflow only after reviewing needs. No vendor purchase, response-time promise,
automatic mailbox ingestion or additional data access is authorized by this entry.
Coordinate with FW-010 for operator roles/UI, FW-014 for email, and FW-015 for
attachment storage/cleanup. Link solved general questions to guides or forum
answers only after removing private information and reviewing publication.

For FW-016 through FW-018, select a bounded delivery plan and acceptance criteria
before implementation. These are separate capabilities and may be delivered
independently; recording them does not schedule or activate them.

## FW-015: Safe orphan-media cleanup and Workspace storage usage

**Captured:** 2026-09-26. **State:** Recorded at owner request; unscheduled,
no implementation or deletion approval.

**Problem.** The owner reports many orphaned images in R2 and no usable cleanup
workflow. Workspaces also need to see how much media storage they occupy, with
reliable usage history if storage-based billing is introduced later. The quantity
and ownership of suspected orphans have not been independently inventoried.

**Who benefits.** Platform operators can reclaim genuinely unused storage and
investigate unassigned objects; Workspace administrators can understand their own
usage; future subscription plans can use an auditable storage measure.

**Proposed scope for later design and implementation:**

1. Inventory existing media references, upload/delete paths and R2 objects before
   choosing a schema or cleanup mechanism. Cover Party photos, collateral photos,
   licence documents, template assets, issued PDFs, import/export artifacts and
   temporary uploads. Reconcile object ownership with Workspace records; unknown
   ownership must remain explicitly unassigned, not guessed from a filename.
2. Identify cleanup candidates through a dry-run report with object count, bytes,
   age and reason. An image absent from the current UI is not necessarily unused:
   preserve historical references, issued-document evidence, retained archives,
   shared references and uploads/imports in progress. Keep production, rehearsal,
   migration and backup prefixes separate.
3. Provide an operator-reviewed cleanup workflow with a grace/quarantine period,
   recoverability appropriate to the storage setup, a final reference recheck,
   bounded retry-safe deletion and an audit of what was removed and bytes reclaimed.
   Handle concurrent saves and partial failures; do not make a bucket-wide delete
   or age-only lifecycle rule the default. Explain how new orphan creation is prevented.
4. Track actual stored object bytes and counts per Workspace, reconcile totals
   periodically against storage, and show usage with a last-updated timestamp and
   useful categories. Workspace administrators see only their own usage; platform
   operators see totals, unassigned bytes and cleanup candidates through explicitly
   authorized operations. Avoid listing the whole bucket on each page request.
5. Define displayed versus billable usage before introducing charges: treatment of
   thumbnails/derivatives, shared objects, temporary uploads, quarantine, exports,
   historical evidence and backups; units, allowances and metering period. Keep
   dated usage snapshots and correction evidence. Storage usage is distinct from
   request/transfer costs. No pricing, quota enforcement or automatic charges are
   approved by this entry.

**Acceptance when resumed.** Demonstrate correct totals against known fixtures,
Workspace isolation, safe repeated reconciliation, reference/retention protection,
concurrent-upload handling and an audited cleanup rehearsal with recovery. Start
with visibility and dry runs, then reviewed cleanup; billing remains a later decision.

Coordinate with FW-010 for the platform operations UI and FW-012 for archive/media
coverage and retention. Select an active delivery plan before implementation.

## FW-014: Domain-owned email and reliable platform/Workspace communication

**Captured:** 2026-09-26. **State:** Active; owner selected SES and approved focused improvements.
See the [active rollout](platform-email-rollout.md) and
[email communication review](email-communication-review.md).

The owner wants proper invitation and communication sending independent of his
personal email. Read-only verification found production's deployment settings use
an in-memory, non-sending backend and a `rokkad.com` sender domain. This differs
from the remembered personal SMTP configuration and is a current delivery gap,
not merely an optional future feature. Do not rely on sent flags as delivery proof.

Approved first scope: domain-owned support/billing inboxes, authenticated
transactional sending through SES, typed configuration,
branded invitations/account/billing mail, durable post-commit retries and provider
delivery/bounce evidence. Public DNS points to Google for inbound mail; confirm
mailbox ownership rather than replacing MX blindly. Keep platform mail separate
from borrower traffic, custom Workspace sender domains and marketing. The owner
created Google Workspace and AWS accounts. Aliases are saved; SES identity/DKIM
and custom MAIL FROM are verified. Durable invitation/receipt delivery is deployed
with scoped AWS credentials and private feedback resources. Worker units validate
but dispatch/feedback/recovery timers remain disabled; separate health monitoring
is enabled. Controlled invitation/billing-sender inbox tests
passed with SPF/DKIM/DMARC and correlated delivery events. Simulator bounce/complaint
and suppression checks passed. Google-verified invitation acceptance passed.
SES case 179042575700203 approved production access on 28 September at 11:20:42 IST
in Mumbai, with 50,000/day and 14/second; independently read in the support console.
General sending and actual paid-receipt acceptance remain open. Explicit billing
mode and test receipt safeguards are implemented locally; see
[billing readiness](../implementation/billing-provider-readiness.md).
The combined external alias test reached the admin inbox (scope in rollout).
Operator stop-mail, pause and sticky-alert acceptance passed; 61 focused tests
include isolated receipt delivery with mocked providers. Monitoring is local,
with manual SQS/DLQ review; external alert routing remains to be agreed for broader
unattended traffic. Provider approval and supervised activation remain gates;
account-security mail remains a separate integration gate.
FW-010 covers operator visibility; FW-011 covers WhatsApp and does not substitute
for reliable email. Next step and acceptance gates are in the linked review.

## FW-013: Tamil Nadu prescribed forms and pledge book in English/Tamil

**Captured:** 2026-09-26. **Decision owner:** project owner.
**State:** Future work; unscheduled, no implementation approval.

**Problem and intended value.** Every applicable business/Workspace should be able
to generate the prescribed forms and pledge book when required, in English and
Tamil, using its own licence and business records. Provide discoverable statutory
documents with reviewed content, rather than requiring each customer to design
forms from scratch. This is a compliance-support objective, not a present claim
that Rokkad or its existing loan tickets satisfy every statutory obligation.

**Owner-supplied source.**
[Tamil Nadu Pawnbrokers Rules, 1943, CRA PDF](https://www.cra.tn.gov.in/tnscs/Files/act/003b_Tamil%20Nadu%20Pawnbrokers%20Rules%201943.pdf).
The linked document is the Rules under the Act, not the Act itself. Initial text
review on 2026-09-26 identified this inventory; current amendment completeness and
official Tamil wording have not been established:

| Prescribed form | Subject in the supplied Rules |
| --- | --- |
| A / B | Licence application / authority-issued licence |
| C, D and D-1 through D-8 | Declarations and notices for specified circumstances |
| E | Pledge book (Rule 7) |
| F | Pawn ticket (Rule 8) |
| G | Sale book of pledges (Rule 8) |
| H | Redemption receipt (Rule 8) |
| I / J | Account-copy certificates (Rule 9) |
| K | Pass-book (Rule 11A) |
| L | Auction register (Rule 14; auctioneer context) |
| M | Half-yearly advances return (Rule 4B) |

Rule 10 specifies Tamil and additional languages for listed localities. Do not
assume an English-only form meets its language requirement. The supplied Form F
also contains reverse-side interest wording: reconcile applicable current terms
and charging rules before approving a statutory template. No lending policy is
changed by this entry. Cross-check the
[Act on India Code](https://www.indiacode.nic.in/bitstream/123456789/20521/1/1943tn23.pdf)
and applicable amendments/notifications during the substantive review.

**Existing foundation.** Loans has configurable layouts, print profiles, licence/
series assignment, document snapshots and preserved issued PDFs. Tamil font support
is described in the configurable-document plan. Reuse those capabilities where
appropriate; existing JCL/JSK custom tickets and Tamil artwork are not evidence
that every prescribed field or register is implemented. No dedicated future-work
entry for the full statutory suite was found.

**Proposed scope and workflow.**

1. Build a rule/form/version matrix with a qualified local review: applicability,
   initiating event, required fields, wording, language, signatures/attestations,
   service/submission requirements and supporting evidence. Distinguish documents
   a lender can prepare from those an authority or auctioneer must issue/maintain;
   the app must not manufacture an official Form B licence or attestation.
2. Start with reviewed E/F/H/M output and the associated data gaps, then select
   the remaining applicable forms. Treat this order as a proposal for later review,
   not approval to implement only a subset of the requested suite.
3. Provide a **Statutory forms & registers** entry point: choose licence/place of
   business, date or reporting period, form and language, inspect coverage, preview
   and generate a printable PDF. Add contextual actions on relevant loan/release
   screens. Decide whether bilingual side-by-side output is appropriate in addition
   to separate English/Tamil copies; preserve prescribed structure and pagination.
4. Map every field to source evidence or an explicit authorised completion step.
   Review owner versus pawner identity, addresses, collateral detail/weight/value,
   interest basis, dated payments, redemption and purchaser/recipient information.
   Do not substitute current prices for historical evidence or infer missing facts.
   Show incomplete imported/paper-history coverage instead of declaring a complete
   statutory register from the digitally recorded subset.
5. Reconcile register/return totals to immutable loan and collection evidence,
   including reversals, corrected payouts, renewals and actual business dates.
   Derive reporting-period definitions and treatment of principal/interest/fees
   from reviewed rules. Do not treat outstanding balances as period cash collections.
   A later print must not pretend missing entries were recorded contemporaneously.
6. Provide versioned, ready-to-use templates and professionally reviewed Tamil
   statutory wording. Test font embedding, shaping, line wrapping, long names,
   addresses and multi-page books. Preserve original customer details; do not silently
   machine-translate legal names or invent Tamil spellings. Allow reviewed local-
   language details where needed. Existing dd/mm/yyyy and Indian amount display
   preferences apply only where compatible with prescribed formats/precision.
7. Explain each form's purpose, prerequisites and next action in the user guide.
   Generation, signing, issuance, acknowledgement, service and filing are distinct
   events; printing or WhatsApp delivery alone must not mark a legal duty fulfilled.
   Confirm acceptance of electronic records versus physical books/signatures before
   proposing retirement of paper registers or automated filing.

**Acceptance and boundaries.** Require field-by-field source mapping and reviewed
English/Tamil samples against current prescribed forms, then visual/physical print
checks and reconciliation tests. Include multiple licences, mixed series, partial
payments, cancellations/reversals, long content, missing legacy evidence and correct
Workspace authorization/RLS. Preserve issued bytes and actual actor/time/version;
reprints and later corrected statements must remain distinguishable. No fabricated
signatures, backdated issuance, cross-Workspace data or silent alteration of approved
loan economics. A source/model gap may require separately reviewed domain work,
not a misleading blank or invented default. Do not claim universal compliance from
successful PDF generation.

**Related work:** [document printing](../flows/loan-document-printing.md),
[configurable documents](loans-configurable-documents-plan.md),
[licences and series](../domain/loans-regulatory-setup-and-policy.md).
FW-012 should preserve statutory template versions and issued artifacts in its
future archive inventory. FW-011 messaging does not replace prescribed notice
service. Resume with current-law/Tamil-source verification and the form-to-data
inventory; no forms, filings or production changes are authorised by this capture.

## FW-012: Complete Workspace export and guided restore into a fresh Workspace

**Captured:** 2026-09-26. **Decision owner:** project owner.
**State:** Future work; unscheduled, no implementation approval.

**Owner scenario.** Export a Workspace's data in Excel or another suitable format,
save it to a personal Google Drive, create a new Workspace, import it and continue
operating on the same business data. The owner compared the desired experience to
Tally. The objective is a customer-controlled portable business snapshot, not just
a readable report or an infrastructure PostgreSQL backup.

**Already planned; this is the register entry for that scope.**
[M7: Complete Workspace archive and binary portability](data-portability.md#m7--complete-workspace-archive-and-binary-portability)
already proposes the full archive and media inventory. This entry captures the
explicit end-user restore/continuation acceptance scenario and links that existing
milestone rather than starting a competing archive project. FW-007 remains guided
legacy/paper/Excel migration; transferring Rokkad's own complete snapshot is a
distinct journey sharing the same domain-owned portability foundations.

**Current verified boundary.**

- `party-bundle/1` exports/imports six Party profiles with manifest, schemas,
  checksums, dependency-aware review and atomic combined commit. It declares
  PARTIAL coverage: no Loans, binary files/KYC, Party metadata, role-type definitions,
  Workspace settings/access or other apps. It is bounded to 1,000 rows per profile
  and 5 MiB per profile; it cannot represent arbitrary-size Workspace backups.
- Supported complete-history loans have per-loan JSONL export and staged import
  with explicit borrower/licence/series/product preparation and reconciliation.
  Unsupported histories are rejected, not silently reduced to simpler records.
- Imported opening positions have dedicated bounded export/restore; v2 preserves
  supported payments and allocations. Media bytes and pre-opening transactions
  remain outside that contract. Source actors are provenance, not new local users.
- Historical-only archives and source-specific media migration are separate paths.
  Their existence does not prove a single complete Workspace restore workflow.

**Proposed experience.** Export a **Workspace backup package**, show its capture
time/version, included record/file counts and any exclusions, then download it.
The user may store the downloaded artifact in private storage of their choice.
In a fresh Workspace, **Restore from Rokkad backup** validates compatibility and
integrity, previews mappings/coverage and financial totals, and obtains explicit
confirmation before restoring. After reconciliation and setup checks, the owner
can continue servicing existing loans and issuing correctly numbered new loans.

**Format direction to design.** Reuse the existing versioned JSONL contracts in a
package with manifest, relationships, checksums, necessary configuration and
referenced media/issued-document bytes. Excel/CSV views help inspection/reporting;
a workbook alone must not be advertised as a complete, lossless restore of files,
immutable events, snapshots and relationships. Decide package encryption and key
recovery deliberately, since customer-held archives contain private data. Manual
download/upload is the first candidate; direct Google Drive connection, scheduled
backups, OAuth permissions and retention are separate optional work, not implied
by this storage example. No real data transfer is authorised by this entry.

**Acceptance and boundaries before implementation.**

1. Inventory every applicable entity and file: customers/contacts/addresses/photos,
   native and imported loans, collateral/quantities, drafts/approvals, payments,
   releases/reversals/renewals, interest and policy evidence, custody, historical
   archives, issued documents, licences/series/counters, products, economic settings,
   Rates, ticket layouts and permitted notification history. Publish operationally
   restorable, archive-only and excluded coverage; neither FULL nor ready-to-operate
   may silently omit unsupported data. Widen contracts only through reviewed tests.
2. Capture a consistent business snapshot while handling concurrent writes and media
   changes. Define volume limits/chunking, safe interrupted retries, compatibility
   upgrades and corrupt/missing-file failure. Checksums prove integrity, not source
   authenticity. Fail clearly rather than export a misleading partial backup.
3. Support an empty compatible destination first. Existing/nonempty Workspaces need
   a separate reviewed merge/conflict workflow; no blind overwrite, name-only matching,
   double debt, sequence rewind or duplicate cash/custody events. Map all references
   to new local IDs within the selected Workspace under forced RLS.
4. Restore business configuration and historical evidence without importing login
   sessions, passwords, staff grants, provider secrets, subscription entitlements or
   automatic verification claims. Set up destination ownership/access/integrations
   separately. Preserve actual source actors as evidence and record the restore actor.
5. Verify balances and future interest behaviour, loan states, collateral custody,
   exact issued bytes and numbering continuity against the snapshot. Restoring must
   not charge/disburse cash, resend old notifications or issue replacement originals.
   Historical licence evidence must not silently grant present-day lending authority.
6. Distinguish a recovery snapshot from an operational move. Changes made after export
   are absent; do not let both copies become unnoticed competing books. For a live
   move, agree a final snapshot/handover and which Workspace receives future entries.
   Do not automatically delete, freeze or disable the source during import.
7. Define controlled publication of a fully reconciled restore and recovery from
   interruption. Prove export -> fresh restore -> re-export semantic equality and
   supported subsequent lending/servicing, with permissions, RLS, replay/conflict,
   malformed-package and private-download tests at representative volumes.

**References:** [Party bundle implementation](../../apps/tenant_apps/data_portability/bundles.py),
[complete-history workflow](../flows/loans-history-import.md),
[opening restore reconciliation](../adr/2026-09-12-opening-restore-reconciliation.md),
[opening export v2](../contracts/loan-opening-export-v2.md),
[customer exchange principle](../adr/2026-09-11-customer-data-portability.md).

## FW-011: Platform and Workspace WhatsApp messaging and phone verification

**Captured:** 2026-09-26. **Decision owner:** project owner.
**State:** Future work; unscheduled discovery. **Implementation approval:** not
granted. No account connection, provider submission, test message or automation is
authorised by recording this idea.

**Problem and intended value.** The owner wants WhatsApp to become a useful product
differentiator: platform operators communicate operational/subscription events to
Workspace owners, while each lending business communicates with its borrowers
through its own business number. Phone verification is a related need. The overall
onboarding, workflows and UI are not yet defined. Validate customer value and
permitted uses before publishing the capability as an available USP.

**Two distinct sender/audience scopes to design.**

| Scope | Intended sender and audience | Candidate messages, subject to eligibility |
| --- | --- | --- |
| Platform operations | Rokkad business identity to Workspace owners/designated billing or operational contacts | Subscription/trial status, invoice/payment confirmation, service/access changes and account-related verification codes |
| Workspace operations | Workspace's authorised business identity/number to its customers/borrowers | Requested loan-state updates, transaction receipts, approved service notifications and customer contact-verification codes |

The platform sender must not become a fallback for Workspace borrower traffic.
Define the global control-plane ownership and authorization separately; do not put
platform billing alerts in an arbitrary customer's Workspace to reuse the sender.
Specify who can connect/disconnect a number, approve templates, send/retry messages,
inspect recipient data and spend the messaging budget. Handle multiple branches
under one legal business explicitly rather than assuming unrestricted number reuse.

**Existing foundation and overlap.** A dedicated register entry for this combined
product need was absent, but
[Workspace WhatsApp Cloud integration acceptance](workspace-whatsapp-cloud-integration-acceptance.md)
already covers a narrower future test-and-readiness workflow. Preserve that plan
as a delivery dependency, not duplicate it. Current Notify v2 code includes a
Workspace-specific Cloud integration, encrypted secrets, setup route, template
delivery jobs, authenticated/replay-safe status receipts and readiness checks.
These do not prove live production delivery or a complete onboarding/OTP product.
The accepted provider remains Meta Cloud API only; provider changes require a
separate decision. Use current shared-schema/RLS contracts; older WhatsApp documents
contain historical tenant-schema and retired-app descriptions.

**Discovery and proposed workflow.**

1. Map allowed event/audience pairs and sender ownership, including actual lender
   use-case eligibility. Separate service notifications, authentication and marketing;
   do not assume calling something transactional makes it eligible.
2. Design **Connect WhatsApp** for each authorised business, number ownership checks,
   template/language setup, explicit recipient consent and a controlled delivery test.
   Evaluate Meta's supported onboarding and Business App coexistence/migration rules
   before promising that an existing shop number can stay unchanged. Do not automate
   personal WhatsApp sessions or introduce an unofficial browser-bot integration.
3. Define opt-in evidence, preference/category controls, opt-out processing and
   recipient selection. Existing/imported phone numbers are not messaging permission.
   Clarify how replies reach staff; decide whether a shared inbox is a later increment.
4. Let authorised users preview eligible messages, choose manual versus selected
   event-triggered delivery, and see queued/accepted/delivered/read/failed evidence.
   Add safe retries, event deduplication, quiet hours for routine alerts, throttling,
   spend limits, diagnostics and an explicit alternative when delivery is unavailable.
   A read receipt is not borrower agreement or statutory notice acceptance.
5. Treat contact verification as its own challenge flow: short-lived, one-use code,
   attempt/resend limits, authenticated binding to the intended contact and purpose,
   and no OTP logging. Successful code entry evidences access to that WhatsApp account
   at that time; it does not prove legal identity, SIM ownership or Aadhaar verification.
   Define reassessment when the number changes and a supported alternative channel.
   SMS currently has no delivery provider; do not promise automatic SMS fallback.
6. Define who pays Meta charges, any Rokkad markup/allowance and recipient-market/
   category pricing. Establish per-Workspace accounting of usage without changing
   loan accounting. Review the UI, staff guide and a consented pilot before rollout.

**Current policy checkpoint (2026-09-26).** WhatsApp requires recipient opt-in,
respect for opt-outs and approved templates for business-initiated messages;
free-form replies have a 24-hour customer-service window. Its prohibited-use list
includes debt collection and certain lending categories. Resolve eligibility for
pawn lending and each reminder/recovery use case with Meta before enabling them;
template approval alone is not a policy exemption. Do not disguise collections
as another message category. [WhatsApp Business Messaging Policy](https://whatsappbusiness.com/policy/)
WhatsApp supports authentication messages carrying one-time codes, but Rokkad still
needs its own challenge-validation workflow.
[Official authentication overview](https://whatsappbusiness.com/products/conversation-categories/authentication/)

**Acceptance boundaries.** Source applications own business intent and committed
facts; Notify owns delivery. A failed or duplicate message must never disburse,
release, alter a subscription or otherwise decide business state. Keep Workspace
data/credentials isolated under existing RLS and authorization; authenticate and
bind callbacks before processing. Minimise sensitive loan data in messages and use
authorised document access rather than public media links. Verify opt-out enforcement,
sender isolation, stale/replayed events, OTP abuse, provider outages, cost controls
and genuine callback reconciliation. No mass messaging or automatic borrower contact
starts from this backlog entry.

**Related work:** [Notify domain](../domain/notifications.md),
[Cloud API-only decision](../adr/2026-08-14-whatsapp-cloud-api-only.md),
[Workspace integration ownership](../adr/2026-08-13-workspace-owned-whatsapp-cloud-integrations.md),
[current control-plane contracts](../architecture/control-plane-contracts.md).
FW-010 owns the platform-admin operating experience. FW-009 remains separately
shelved; phone verification does not resume Aadhaar work. Before implementation,
recheck current Meta requirements, supported API versions and pricing.

## FW-010: Platform administrator role, operational workflows and UI

**Captured:** 2026-09-26. **Decision owner:** project owner.
**State:** Future work; unscheduled. **Implementation approval:** not granted.

**Problem.** The owner reports that the platform administrator's role, day-to-day
operating workflows and UI are not yet clearly defined/implemented as a coherent
experience. Define who operates the SaaS, what they may do, and where/how they
perform those tasks without confusing platform administration with a customer's
Workspace Owner/Admin role.

**Existing foundation, not a blank slate.** No dedicated entry for this overall
problem existed in this register. There is already a superuser-only platform
override policy, explicit Workspace selection and audited access, control-plane
services for ownership/lifecycle/authorization, and dated administrator subscription
access decisions. The existing global/Workspace UI contracts also remain relevant.
These foundations do not by themselves establish a complete operator console or
operational handbook. Inventory actual screens, permissions, services and tests
before classifying individual capabilities as missing.

**Discovery and proposed scope.**

- Define platform responsibilities and the role/action matrix: platform owner,
  support, billing and operations are candidate responsibilities to evaluate, not
  approved new roles. Decide whether any non-superuser delegation is actually needed.
- Map common operational journeys: locate a Workspace, inspect setup/access issues,
  assist onboarding and ownership recovery, review subscriptions/entitlements,
  grant or end dated access extensions, and deliberately suspend/restore service.
  Identify which actions already exist and which need design or implementation.
- Define authorized support entry into a specific Workspace, visible acting identity
  and target, reasons/audit history, and a clear exit. Do not assume silent user
  impersonation or unrestricted borrower-data access is required.
- Design a discoverable platform console with navigation, Workspace search, status
  summaries, actionable queues, operation detail/history and clear confirmations
  for consequential actions. Decide which exceptional tasks remain in Django admin
  or operator commands; reuse existing services instead of duplicate business logic.
- Document operating procedures, escalation/recovery paths and staff guidance.
  Review mockups and end-to-end operator scenarios before implementing increments.

**Boundaries and acceptance.** Preserve canonical authorization, explicit Workspace
context, forced RLS and audited actor/target/reason. Global metadata access must not
silently imply access to tenant business data. Keep suspension separate from billing
expiry/extensions, and distinguish the operator from the customer being assisted.
No automatic superuser grants, new role system, impersonation, production changes
or deletion workflows are authorised by this entry. Before delivery, validate
permission boundaries, denied actions, lifecycle effects and audit evidence as well
as desktop/mobile navigation and discoverability. Broader access changes need an ADR.

**References and related work:**

- [Control-plane contracts](../architecture/control-plane-contracts.md) are the current normative boundaries.
- [Platform override policy](../adr/platform-admin-override-policy.md) supplies the role-policy foundation; read historical implementation wording alongside current contracts.
- [Global and Workspace UI contracts](../implementation/control-plane-phase6-url-ui.md).
- [Subscription access continuity](../adr/2026-09-24-subscription-access-continuity.md); FW-008 remains the separate servicing-only restriction idea.
- FW-002 remains payment-provider acceptance, and FW-007 remains customer migration onboarding; this entry does not automatically resume either.

## FW-009: Consent-based borrower identity verification / Aadhaar-assisted onboarding

**Captured:** 2026-09-26. **Decision owner:** project owner.
**State:** Shelved at owner request; desk feasibility review complete. Recording this idea does not approve implementation,
provider onboarding, real identity-data collection or a production marketing claim.

**Shelved (2026-09-26).** The owner deferred resolving contracting legal entities
and obtaining written answers before integration selection and a small pilot.
Resume only on the owner's explicit instruction. Preserve the review and unsent
enquiry; no provider outreach, registration, integration selection or pilot work
should proceed meanwhile. On resumption, recheck current requirements and pricing.

**Owner agreement (2026-09-26).** The owner agreed with the feasibility-first
recommendation and the potential product promise: **"Verify customer identity and
reduce manual entry."** The next step is a small feasibility review of permitted
lender/platform arrangements, customer effort and costs, followed by a recommendation
for the simplest consent-based workflow. This agreement establishes product direction;
integration selection and delivery remain pending. Market it as an available capability
only after implementation and validation.

**Review outcome (2026-09-26).** The owner authorized the review; see the
[feasibility recommendation](borrower-identity-feasibility.md). First investigate
registered-lender app credential sharing, with a provider-hosted DigiLocker route
as an alternative. Legal-entity/hosting eligibility and an all-in quote remain
unconfirmed. The review includes public sources, repository gaps, an unsent enquiry
and pilot gates. No provider selection, external contact or production integration
has occurred.

**Problem and intended value.** The owner wants greater confidence in borrower
identity, less manual entry, and essential official details such as name and address
to populate customer records with consent. He sees this as a potential SaaS selling
point. Validate that value with lenders and customers; do not promise fraud prevention,
creditworthiness, collateral ownership or complete regulatory KYC compliance from
an identity check alone.

**Existing foundation.** Party already has Workspace-owned identifiers (including
an Aadhaar type), documents, verification flags/timestamps, multiple addresses and
contacts, and a photo gallery/default photo. These are record-management foundations;
a saved identifier or verification flag is not proof of UIDAI verification. Review
`PartyIdentifier.value`, masking, hashes, metadata, exports and existing permissions
before accepting any new Aadhaar data. Reuse Party rather than create a parallel
customer registry.

**Proposed experience, subject to feasibility.**

1. Staff selects **Verify customer** while creating or updating a customer; explain
   what is requested, why, and what will be retained. Offer an alternative identity
   review route for customers unable or unwilling to use Aadhaar.
2. Customer consents and shares a supported credential, or completes an approved
   provider flow. Validate its authenticity and separately establish that it belongs
   to the person presenting it; a signed document alone does not establish presence.
3. Show the shared name/address and permitted photo alongside existing details.
   Staff resolves differences and possible same-Workspace duplicate customers before
   saving. Never silently replace current contact/address information.
4. Collect the usable contact number separately and, if selected for delivery, verify
   possession through a separate contact-verification step. Distinguish official
   credential address from current residence and phone possession from identity proof.
5. Save only approved necessary fields plus method, result, consent/evidence reference,
   time and actual authorized actor. Show precise labels for source-verified details,
   staff-reviewed evidence, pending/failed checks and later changes to verified fields.

**Routes to investigate, not selected architecture.** UIDAI documents digitally signed
offline XML containing identity details; its mobile/email fields are hashes, not
plain contact details that Rokkad can fetch. UIDAI also documents selective credential
sharing through the Aadhaar app. Compare app sharing, Secure QR and offline XML with
an authorised online e-KYC arrangement, including KUA/Sub-KUA eligibility. An arbitrary
Aadhaar-number lookup or purchase of a generic API is not sufficient authorisation.

**First discovery gate.** Establish the legal and operational roles of Rokkad and each
lender. UIDAI's current OVSE FAQ says offline verification cannot be performed on
behalf of another entity. Resolve the permitted SaaS processing/registration model
with UIDAI or qualified advice before assuming one Rokkad registration covers all
workspaces. For online e-KYC, verify provider authority, lender onboarding and onward
sharing restrictions. Compare costs, user effort, supported devices and failure paths
only within an eligible arrangement. Recheck current rules before implementation.

**Proposed retention and isolation boundaries.** Minimise collection and define lawful
retention/deletion and consent handling first. Do not add storage of full Aadhaar
numbers, biometrics, OTPs, share codes or raw credentials by default; transient
processing must not leak into logs, analytics, backups or public media. Retain only
permitted, necessary evidence/references under an explicit policy. Any new records
must follow existing Workspace ownership, forced RLS, private-media and audit rules.
No cross-Workspace identity search or platform-wide borrower registry is authorised
by this idea. Do not treat last-four digits as a unique customer identifier.

**Before delivery.** Define evidence states and presenter matching, field-level
provenance, retention, authorization and a non-Aadhaar/manual route. Test tampered
credentials, mismatches, duplicate customers, retries, unavailable providers/devices,
consent handling and tenant isolation. Use synthetic/provider test identities for
evaluation. Publish only the exact capability actually delivered.

**Official discovery references checked 2026-09-26:**

- [UIDAI offline e-KYC details and signature verification](https://www.uidai.gov.in/en/about-uidai/307-english-uk/faqs/aadhaar-online-services/aadhaar-paperless-offline-e-kyc.html).
- [UIDAI Aadhaar app and selective sharing FAQs](https://www.uidai.gov.in/en/faq).
- [UIDAI OVSE registration and entity restrictions](https://uidai.gov.in/hi/ovse).
- [UIDAI Authentication and Offline Verification Regulations, consolidated December 2025](https://uidai.gov.in/images/The_Aadhaar_Authentication_and_Offline_Verifications_Regulations_2021-_Clean_copy-30122025.pdf).

## FW-008: Servicing-only subscription restriction

**Captured:** 2026-09-24. **State:** Deferred; unscheduled.

The approved pre-cutover increment provides normal grace, read-only access and
dated administrator decisions. A later stage could allow repayments, collateral
release and the documents needed to service existing loans while blocking new
lending. Define exact allowed actions, reversals, renewals, backdated operations,
document issuance, notification delivery and import/operator behavior first.
Do not equate this with GET versus POST, loosen lifecycle/RLS, or accidentally allow
new financial exposure. Add action-level tests and an explicit customer/admin
explanation before enabling it. Razorpay provider acceptance remains FW-002 and is
required before real paid onboarding. See the
[continuity decision](../adr/2026-09-24-subscription-access-continuity.md).

## FW-007: Guided customer-facing legacy migration

Reconfirmed on 2026-09-25 in the [loan journey reference](../flows/loan-journey.md#7-imported-history-and-deliberate-digitization)
and in-app staff guide. Manual old-paper loan admission and guided Excel loan
imports remain future work; the published product story distinguishes them from
the existing assisted migration foundation.

**Captured:** 2026-09-24. **Last reviewed:** 2026-09-25. **Decision owner:** project owner.
**State:** Future work; unscheduled. **Implementation approval:** not granted by
this entry. The owner explicitly requested that this gap be retained in the backlog.

**Problem.** Customers should be able to bring supported legacy data and complete
a guided migration without writing canonical JSONL, invoking server commands or
depending on an operator for every source mapping and reconciliation decision.
Existing portability is not a universal upload-any-spreadsheet-or-database importer.

**Existing foundation to reuse.** Party CSV/XLSX/JSONL mapping, previews, identity
checks, reusable presets and bundle commits; complete-history loan admission;
reviewed opening balances; historical-only archives; source-specific PostgreSQL
dump preparation; and the separate media migration pipeline. The hosted Linode
rehearsal used these capabilities plus operator preparation, not a generic customer
migration wizard. Preserve existing financial services and evidence contracts.

**Proposed user journey.**

The owner's two onboarding scenarios are explicit acceptance examples:

- **Start fresh digitally:** use a new series under an existing verified licence
  for new customers/loans; earlier paper loans remain outside Rokkad. No legacy
  import is required. Reporting covers only recorded loans, not the whole physical
  business portfolio.
- **New lending plus gradual paper migration:** continue normal lending while
  bringing earlier physical loans into the same Workspace, either by manual entry
  or Excel. Both proposed input paths must use the same historical admission and
  reconciliation services. A guided manual legacy-entry screen and generic loan
  spreadsheet preparation are future work, not the ordinary new-disbursal form.

For the second scenario, propose an **Add existing loan** entry point with manual
and spreadsheet options. Support explicit matching to borrowers already created
during new lending; the current import identity foundation does not itself provide
a customer-facing existing-Party binding editor. Preserve old licence/series/loan
references and protect the new live number range. Classify evidence as complete
supported history, a reviewed outstanding opening, or archive-only closed history;
active status alone does not select opening mode. Each admitted loan/batch needs an
explicit financial handover date and reconciliation so a payment is recorded once,
old interest is not charged twice, and original loan age is not reset. Different
loans may be prepared in later batches while new lending continues. Current opening
servicing requires dates strictly after the opening date; the proposed journey must
explain this boundary or separately review an extension. Show migration coverage
so partial digitisation is never presented as the complete business portfolio.

1. Choose a supported source format/template or adapter, see its coverage and limits,
   and upload source data into private Workspace staging.
2. Map columns and source identities; resolve borrower matches and duplicates;
   map destination licences, series, numbering and products through guided forms.
3. Classify each loan as supported complete history, a reconciled active opening,
   historical-only evidence, or blocked/unsupported. Explain the reason in ordinary
   business language; never infer eligibility from active/closed status alone.
4. Guide missing-evidence decisions and reconcile principal, interest, fees, original
   dates, continuation rules, collateral/custody and supported media references.
   Show source-to-destination totals and every unresolved exception before approval.
5. Preview without creating operational financial records, obtain explicit approval,
   and import through existing atomic, idempotent services. Show progress, safe retry,
   retained audit/source evidence, result links and post-import reconciliation.

**Acceptance boundary.** Start with an explicitly selected source/template and a
representative customer completing the flow without hand-written JSON or CLI work.
Test permissions, Workspace isolation, conflicting/repeated identities, changed
source files, missing versus zero values, partial failures, retry and reconciliation.
Show unsupported data/attachments honestly. Never execute an uploaded SQL dump
against the application database, invent historical transactions, overwrite posted
evidence, silently merge borrowers, or recycle reserved numbers.

**Open decisions / first step when resumed.** Inventory current adapters and import
screens, select the first supported customer source and batch sizes, and design a
single end-to-end journey using representative data. Define media coverage, operator
handoff cases and cancellation/resume behavior before selecting an active delivery
slice. This backlog item does not by itself become a production-cutover blocker or
promise arbitrary-source self-service migration.

**References:** [Party workflow](../flows/party-master-portability.md),
[loan setup preparation](../flows/loans-import-preparation.md),
[complete-history import](../flows/loans-history-import.md),
[prepared legacy openings](../flows/legacy-opening-import.md),
[portability follow-up](loans-portability-audit-followup.md).

## FW-001: Optional owner-configurable license scope

**Captured / last reviewed:** 2026-09-09. **Decision owner:** project owner.
**Priority/date:** unscheduled. **Implementation approval:** not granted.

**Problem and possible benefit.** A business with multiple licenses may want some
staff to work with only part of its loan portfolio while sharing borrower profiles.
This should be an optional business choice, not a restriction imposed on every owner.

**Where we left it.** Workspace remains the SaaS tenant, with PostgreSQL forced RLS,
membership and action permissions. Loan access is currently organization-wide subject
to those permissions. The role, private-media application and onboarding improvements
are published in checkpoint `4d15477`; they did not implement license scoping.
Production media verification remains a separate acceptance gate.

**Preserve these decisions.**

- Keep organizations/Workspaces as tenants and licenses inside them.
- Any license scope must be optional and configurable by the owner, with an
  organization-wide mode retained.
- Borrower profiles remain shared across the organization subject to view permissions.
- “All loans under assigned licenses” was one proposed mode, not an accepted universal
  rule. Do not infer creator-only or personally assigned loan access.
- License and branch are not automatically the same concept.
- A fresh design review and explicit owner approval are required before implementation.

**Open decisions for the next discussion.** Choose the supported scope modes; define
unassigned staff, new/expired licenses, owner access, and switching restrictions on
or off. Decide what financial information a shared borrower profile exposes. Review
existing-member migration, audit, in-flight work and background jobs. Determine whether
intra-Workspace database enforcement is needed in addition to application checks.

**First step when resumed.** Read the linked ADR and SCP review criteria, compare them
with the current implementation, and prepare concrete owner/staff examples for review.
Record the owner's selected behavior and explicit implementation approval. Only then
create an active delivery plan linked back to FW-001; do not start with schema changes.

**Acceptance outline if approved.** Test both unrestricted and selected scope modes;
enforce the approved behavior on direct URLs, services and jobs, as well as borrower
financial tabs, searches, reports, exports, photos/PDFs, collateral, releases and
notifications. Cover cross-license transfers, splits and renewals, membership/scope
revocation and configuration changes without rewriting historical loan ownership.

**References:** [tenant/access ADR](../adr/2026-09-09-organization-tenant-and-license-access.md),
[SCP-01/SCP-02 delivery register and review criteria](saas-access-media-and-onboarding.md#scp-optional-scope-last-and-subject-to-explicit-owner-approval),
[action-permission review](../implementation/action-permission-review.md).

## FW-002: Razorpay setup and provider test-mode acceptance

**Captured:** 2026-09-09. **Last reviewed:** 2026-09-26. **Decision owner:** project owner.
**State:** Active preparation under selected FW-019.
**Current checkpoint:** owner reports software/SaaS reclassification, application
submission and completed KYC, followed by account approval and Live/Test activation
on September 27. Saved encrypted test keys now verify all three API endpoints.
An isolated rehearsal runtime and provider workflow acceptance remain open.
See the [active rollout](subscription-monetization-rollout.md#test-mode-preparation).

**Earlier shelving reason:** provider setup had not started, and the owner selected
other project improvements. That earlier constraint is superseded for FW-019;
no live charges or production checkout activation are authorized by this checkpoint.

**Where it stopped.** Workspace-bound checkout, paid-period expiry, verified known-
payment recovery, processed refund evidence and final owner review decisions are
implemented locally with mocked provider/mail tests. Development migrations through
subscriptions.0009 are applied. These changes remain uncommitted as of this entry.
No real Razorpay payment/refund or provider test-mode rehearsal has been performed.
The implementation is not accepted for real paid onboarding yet.

**What the postponed step means.** Establish the owner's Razorpay test environment,
configure test credentials and a webhook secret privately, provide an HTTPS callback,
and exercise checkout plus actual provider event delivery in test mode. Verify
captured payments, failed/abandoned attempts, repeated/delayed callbacks, partial/full
processed refunds, recovery and reviewed resolutions against the local records.
Mocked automated tests remain available without Razorpay setup.

**Preserve these constraints.** Workspace ownership/context, frozen order/amount/
currency/plan evidence, RLS, immutable financial evidence and idempotent handling
must remain intact. No live charges/refunds are authorized by this entry. Unknown
orphan/legacy contracts cannot be reconstructed by guessing; refund issuance,
chargebacks and proration remain outside current implementation.

**First step when resumed.** Read current billing flow/status, confirm the owner is
ready with a test environment, inventory the intended runtime and HTTPS callback,
and prepare a concrete test-mode acceptance checklist. Recheck provider documentation
at that time. Keep secrets out of Git, logs and documentation. Record the observed
outcomes and unresolved issues before declaring paid onboarding ready.

**References:** [checkout/recovery/review flow](../flows/subscription-checkout.md),
[billing decision](../adr/2026-09-09-workspace-checkout-evidence.md),
[hardening delivery plan](project-hardening.md), [current status](../STATUS.md).

## Maintaining and resuming entries

Assign a stable `FW-NNN` ID and add a register row when shelving an idea. Record the
reason, last known state, open decisions, references and first useful next step.
Use the states **Shelved**, **Ready for review**, **Active**, **Completed** or **Dropped**;
record approval separately so “Ready for review” never implies permission to implement.

When an idea is selected, update its state and link the active plan. When delivered
or dropped, retain the entry with its outcome and commit/decision link. Do not renumber
or delete entries merely to keep this list short. Update the last-reviewed date when
the decision or restart point changes. “Proceed” on another task does not reactivate
a shelved idea.

### Copyable entry template

```markdown
## FW-NNN: Idea title

- State: Shelved
- Captured / last reviewed: YYYY-MM-DD
- Decision owner:
- Priority/date: Unscheduled
- Implementation approval: Not requested / required / approved with reference
- Problem and benefit:
- Why shelved / resume trigger:
- Where it stopped (existing behavior, completed work, remaining work):
- Decisions and constraints to preserve:
- Open questions:
- First step when resumed:
- Acceptance outline:
- References (ADR, plan, files, commit):
- Outcome / active delivery link:
```

## FW-003: Formal lender-specific NPA classification

**Captured:** 2026-09-11. **Priority/date:** unscheduled.
**Implementation approval:** not granted by the monitoring capacity task.

Current Loan health derives per-loan DPD from contractual obligations and labels
Standard, Watch and Substandard using effective monitoring-policy thresholds.
Collateral LTV/shortfall is independent. The default Substandard threshold is
DPD >= 90, which must not be presented as a complete regulatory NPA decision.
The compliance-profile name alone does not implement regulatory rules.

Before implementation, identify the intended lender type and applicable framework,
then review classification boundaries, borrower-wide versus per-loan scope,
upgrade/cure rules, restructuring treatment, doubtful/loss aging and any reporting
or income-recognition obligations. Preserve canonical schedules, repayments and
reversal history. Do not silently change the operational thresholds or restore
retired general-ledger accounting. See [the current explanation](../flows/loan-health-monitoring.md#payment-performance-and-the-npa-distinction).

## FW-004: Launch-scale loan monitoring capacity

**Shelved / last reviewed:** 2026-09-12. **Decision owner:** project owner.
**Resume trigger:** better representative hardware is available and the owner
explicitly resumes capacity testing. Do not automatically restart long local runs.

**Target.** At least 100 organizations with 3,000-10,000 active loans each and
30-100 loans processed per organization/day. All affected active loans should
receive a current health assessment within one hour after a metal-price change,
while ordinary servicing remains usable. This target remains unproven; shelving
the test does not establish production capacity or waive launch acceptance.

**Where it stopped.** The valid 100 x 3,000 run assessed 121,869/300,000 loans by
3,589.09 seconds and failed the target, with zero reported errors and passing
sampled correctness checks. The million-active/200,000-closed fixture was prepared.
One upper-size attempt was invalidated by a 706-second measurement gap. The next
retry was stopped at the owner's request because it was too slow on this machine;
its last observation was 19,185/1,000,000 at 940.65 seconds, with no reported errors.
That partial retry is not an acceptance result and had no final monetary-validation
pass. Test clients are stopped and the temporary role is removed. The disposable
`test_rokkad_monitoring_load` database is retained locally (about 27.5 GB before the
latest wave); no normal development or production worker was started.

**Pickup notes.** Preserve the existing RLS, closed-loan exclusion, per-loan commits,
source-change guards and repayment/reversal rules. The
[capacity report](../implementation/monitoring-capacity-test.md) records workload,
environment, exact results, limitations and commands. Resume on documented hardware
with an uninterrupted test window; revalidate fixtures and runtime-role restrictions.
The full 300,000/1,000,000 matrix and realistic foreground traffic still need to pass.
Overlapping price changes, recovery/restarts and concurrent origination/releases
remain additional acceptance dimensions. Hardware alone is not an established fix:
measured candidates include the per-loan pending lookup and repeated financial
history reads. Assess those separately when capacity work resumes.

## FW-005: Historical market-valued loan entry

**Captured:** 2026-09-12. **Updated:** 2026-09-26.

The owner approved native earlier-payout/correction recording and explicit daily
unchanged-price confirmations. Implemented scope is documented in the
[decision](../adr/2026-09-26-earlier-payout-and-daily-price-confirmation.md) and
[staff flow](../flows/earlier-payout-and-daily-prices.md); deployment evidence is
in Status. This preserves an actual previous-day payout date instead of moving it
to pass the ordinary current-day gate.

Remaining work is unscheduled: guided historical admission when contemporaneous
policy/quote evidence is missing, authorized external evidence review, and any
configurable multi-day quote-age allowance. These need explicit business rules;
the current implementation provides no generic bypass or silent price carryover.
Coordinate broader historical/Excel onboarding with FW-007. Active/closed history
must remain immutable and corrections must not duplicate cash or principal.


## FW-006: Party bundle history progress filter

**Captured / last reviewed:** 2026-09-12. **Decision owner:** project owner.
**State:** Shelved at owner request. **Priority/date:** unscheduled.

**Problem and possible benefit.** Filter saved Party ZIP bundle attempts by progress
so operators can find unfinished work without paging through completed attempts.
This is optional usability, not a prerequisite for Party MVP or Loans portability.

**Where it stopped.** Saved history, stable review URLs, pagination, live progress,
combined commit and cancellation are implemented. No filter has been added.
Individual CSV/XLSX/JSONL imports remain separate from bundle history.

**When resumed.** Reuse existing batch-derived progress with Workspace-scoped
queries and pagination. Preserve current permissions, immutable group membership
and completed evidence. No new stored status or background worker is required
merely to filter the list. Select the work explicitly before implementation.

**References:** [Party portability scope](data-portability.md#mvp-scope-closeout-2026-09-12),
[operator guide](../flows/party-master-portability.md).
