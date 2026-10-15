---
status: active
owner: project
updated: 2026-10-15
tags: [implementation, whatsapp, control-plane, scheduling, limits]
related:
  - platform-whatsapp-transport-pw03.md
  - ../plans/platform-owner-whatsapp-phase1-20261014.md
  - ../adr/2026-10-14-platform-whatsapp-delivery-boundary.md
  - ../architecture/control-plane-contracts.md
---

# Platform WhatsApp scheduling and release controls: PW-04

Later software delivery is complete in the [15 October combined release](reviewed-production-release-20261015.md). This dated note retains its local implementation evidence. Production activation remains disabled; live sender and pilot acceptance are separate.

The owner authorised continuation after PW-03. This local change implements current
trial-ending reminders, reviewed service announcements and count/spend reservations.
Live sending, sender configuration, shared migrations and deployment are separate.
The implementation uses ordinary Django services, forms, commands and PostgreSQL
forced RLS; SES email, Workspace Notify and financial posting retain their boundaries.

## Trial reminder

A standalone restricted-runtime command accepts 1–100 explicit positive Workspace
IDs. Each turn locks its Workspace/subscription and reads the latest accepted
trial.started event. Its saved end must equal the current subscription's end.
The reminder applies on the three Asia/Kolkata calendar dates **before the expiry
date** (date difference 1–3), while the actual trial remains unexpired. There is no
catch-up on the expiry date or afterwards. Queueing and dispatch consult the existing
workspace_activity policy: active lifecycle, current trial/full access and no
current administrator override are required. Conversion, an override, changed
end/ownership, lost pairing or changed consent block an obsolete message.

TrialReminder is immutable, directly Workspace-owned and unique per accepted trial
event. It freezes end/stage/recorded time; Delivery has its typed one-to-one source.
The native trial boundary records one accepted trial event, so an end change cannot
produce a second reminder or revive the old one. It expires within 24 hours, bounded
by the actual trial end. Enrollment does not invoke the scheduler or replay events.
A regular explicit scheduler turn may consider a current trial in its date window.
It never changes trial dates, paid access, grace, an offer or charging.

queue_platform_whatsapp_reminders --workspace-ids … captures at most one reminder
per explicit Workspace and never dispatches. No timer or worker has been activated.

## Reviewed service announcement

/app/platform/whatsapp/announcements/ reuses active-superuser/global-context console
authorization, CSRF and reviewed POSTs. GET and review create no source records.
The form permits maintenance or incident information, a notice revision, impact
start/end, expiry and at most 100 explicit affected Workspace IDs. Text is bounded
and excludes custom URLs; the only message link is the canonical existing contact
page. Urgency is available for incidents only. No arbitrary phone composer exists.

The ten-minute signed review binds administrator, complete notice facts, exact
Workspace/owner/lifecycle/name targets, eligible contact revision/consent evidence,
representative recipients, template revision, transport/pilot configuration and
conservative estimated INR reservation. Changed consent, ownership, templates,
pricing or service details require a new review. Confirmation takes sorted Workspace
and contact locks, rechecks the review and persists all source/target/intents in one
transaction. A review digest provides confirmation replay safety.

Announcement is a global platform publication/audit, with creator and the complete
reviewed affected list, including ineligible targets. AnnouncementTarget is directly
Workspace-owned, immutable and forced-RLS, retaining each eligible Workspace's
owner/contact/consent source. One representative per announcement/owner creates a
Delivery; additional owned affected Workspaces retain target evidence. Receipts remain
per invoice. A service message may apply to a suspended Workspace without granting
business access, as allowed by the approved plan.

Before claim and immediately before IO, the global job takes sorted locks on all
represented Workspaces and checks their current reviewed choices through successive
explicit scoped units. It never switches a conflicting active Workspace identity,
uses RLS bypass or infers scope from a callback. The account preview checks its own
Workspace only; group eligibility is proved by dispatch. Any represented Workspace
change blocks a new request. Already accepted delivery evidence remains readable.
Urgency bypasses quiet hours only; cohort, consent, expiry, pricing and caps still apply.

## Private pilot inputs and mode

PLATFORM_WHATSAPP_INTENTS_ENABLED and PLATFORM_WHATSAPP_DISPATCH_ENABLED are
independent, default-false settings. PLATFORM_WHATSAPP_PILOT defaults to an empty
object. Test settings clear them so a local .env cannot activate messaging.

Pilot JSON has exactly version, starts_at, ends_at, cohort, purposes, platform_limit,
contact_limit, daily_spend_inr and tariff. Start/end are timezone-aware and the pilot
must be current. Cohort contains 1–100 exact Workspace/owner ID pairs, with distinct
Workspaces; purposes are a bounded subset of setup/trial/paid/ending/service.
The hard maximums are **100 platform requests/day** and **5 per phone/day**; private
inputs may lower them. The daily monetary cap is a positive explicit Decimal INR
string, with at most six fractional digits. Routine hours are 09:00 inclusive to
18:00 exclusive, Asia/Kolkata.

Tariff has exactly revision, effective_from, effective_until (inclusive local dates),
source_url, currency, market and rates. Version one accepts INR/IN only and normalized
Indian mobile recipients. The evidence URL must be on an official Meta pricing
host. All five retained categories (utility, marketing, authentication,
authentication_international, service) need explicit nonnegative Decimal rate
strings and at least one positive rate. No actual tariff or monetary cap has been
selected by development. Fictional tests use clearly labelled arithmetic inputs.
Actual rates/categories and English Meta template mappings remain release inputs.

Source capture stays independent of transport readiness. A new source can create a
non-capture intent only with intent creation enabled, a valid current pilot,
matching cohort/purpose and a source recorded no earlier than pilot activation.
Existing captures remain immutable and are never promoted. Source replay finds the
existing intent; enrollment/activation do not backfill old events. A non-capture
intent still needs approved typed template configuration and every dispatch check.
Test payments cannot dispatch. The PW-03 unconditional missing-controls gate is
replaced by strict pilot validation; disabled defaults continue to stop transport.

## Atomic limits and cost evidence

BudgetDay is a global platform aggregate with immutable day/policy fingerprint and
count/contact/spend limits. ContactDay is a global hashed-phone daily count, so the
same phone cannot evade its cap through multiple Workspaces. Neither stores business
records or recipient numbers. Reservation and CostEvidence have direct non-null
Workspace ownership, forced RLS and composite delivery/attempt/receipt guards.
The ownership registry now has 155 entries, including four new scoped models.

Each HTTP attempt obtains a Reservation **before** its Attempt is inserted, in the
same durable transaction. A deferred composite FK settles after both exist. The
Attempt insert guard requires its exact reservation. Under the shared BudgetDay
lock, the reservation trigger increments both counters and the spend total, rejecting
capacity overflow. It reserves the largest configured category, rather than assuming
the requested template will retain a cheaper classification. Constraints also
protect the hard count maximums. Reservations are append-only and never refunded,
including definitive rejection, cancellation, interruption or unknown acceptance.
This conservatively counts requests, not only successful deliveries, against caps.
Unknown acceptance never creates a fresh retry.

The first reservation freezes that day's policy fingerprint; later configuration
changes cannot raise that day's capacity. Configuration, date/quiet hours, source,
consent and reservation are rechecked before IO. A quiet/capped candidate returns
deferred only if its next permitted window precedes source expiry, otherwise expired.
No automatic deferral worker is installed; another explicit turn rechecks every rule.
A stored intent's evidence and expiry are not edited to extend usefulness.

Matched delivered/read callbacks produce immutable tariff-based CostEvidence when
billable/category/PMP/date facts support it. Free delivery evidence estimates zero;
known estimates remain separate from conservative reservations. They are **not
provider-billed actual charges**: the callback carries no invoiced amount. A read
callback omitting pricing does not erase a previous known observation. Missing or
conflicting pricing holds future sends; the reserve is retained. Unknown bounded
provider category/model strings become an unknown marker, without raw arbitrary
text or loss of delivery evidence. Such authenticated unknown delivered/read pricing
blocks a new request even before scoped matching. Unmatched callbacks cannot assign
a Workspace or change its business data.

Pricing holds are fail-closed and cannot be cleared by ordinary DML or automatically
at midnight. Operational review/resolution and provider invoice reconciliation are
PW-05 release work. No platform cost becomes a loan/accounting entry or customer fee.
The [official pricing page](https://whatsappbusiness.com/products/platform-pricing/)
was checked 14 October: rates depend on delivery, recipient market and category.
No numeric live rates were inferred from search results.

## Migration and rollback

0004_release_controls adds the seven evidence/aggregate tables, four forced-RLS
policies, typed Delivery sources and composite references. It replaces source/attempt
insert guards while retaining immutable history and the single-use attempt outcome
transition. Existing PW-03 captures, accepted attempts and receipts are unchanged.

Owner-only migration uses django_project.settings.migration. Web/commands use the
restricted runtime role; tests use django_project.settings.test. The reverse guard
runs first and refuses downgrade if any PW-04 source/target/capacity/cost table has
evidence. Empty-new-evidence reverse restores PW-03 SQL guards and preserves its
source/attempt/receipt rows. Stop dispatch before a compatible-code rollback; retain
all evidence and never restore old data over subsequent source transactions.
A retained PW-03 claim without a reservation cannot cross the new request boundary.

## Verification

All **399 distinct selected cases** pass across the 313 wider regressions, 37
existing dispatch/transport tests, 38 PW-04 controls and 11 receipt tests (the final
boundary run overlaps several control/dispatch cases). Three affected final HTTP
cases recheck native date inputs/readable local review dates. The manifest checks
unique test IDs; counts are not summed across repeated runs.

Eight desktop/390px Chromium states (form/review/saved/stale) use cached Bootstrap
and local assets with external network blocked. No horizontal overflow or duplicate
IDs; new review buttons have 44px height. The final phone review was visually
inspected. Real devices/screen readers/provider delivery remain unproven. All-model
migration drift checks, 34 source syntax checks, the 1,125 tracked import guard and
29 untracked runtime import checks pass. Current documentation links and scoped
whitespace checks pass.

Evidence is kept under outputs/pw04-verification and tmp/pw04-*.log. The populated rehearsal
preserves hashes of contact/consent, setup/trial/paid/SES sources, an accepted attempt
and matched read receipt across upgrade, empty PW-04 reverse and reapply. A populated
budget blocks downgrade, and all ten Workspace tables have enabled forced RLS.
Both exact task databases are removed after verification, without terminating
connections. No shared review/production migration, real message, provider setup,
commit or deployment occurred.

The next slice is PW-05: owner/platform diagnostics and operational release review,
then a specifically consented bounded pilot only after real sender identity, actual
approved templates/locales, dated tariff/cap, retention/erasure and monitored support
are settled. Local mocks/layouts cannot establish provider or real-person acceptance.
