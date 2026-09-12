---
status: active
owner: project
updated: 2026-09-12
tags: [agents, context, architecture]
---

# Agent Memory

Stable project understanding only. Delivery evidence belongs in [Status](STATUS.md),
selected work in [the hardening plan](plans/project-hardening.md), and shelved ideas
in [Future work](plans/future-work.md). Prior notes, including superseded decisions,
are preserved in [the historical snapshot](archive/context/2026-09-09/AGENT_MEMORY.md).

## Product and tenant foundation

Rokkad is operational pawn-lending SaaS. Supported business apps are Party, Loans,
Rates and Notify v2. General-ledger accounting/DEA, Girvi, Contact, Product and legacy
Notify are retired. Do not restore their imports or product promises. Preserve
intentional legacy redirects, 410 responses, migrations and Party `contact.*`
permission aliases until separately reviewed.

Workspace (`orgs.Company`) is the SaaS tenant; licenses and series live inside it.
PostgreSQL shared-schema forced RLS isolates directly Workspace-owned business rows.
`workspace_context()` owns transaction-local RLS context. Request identity comes
from an explicit Workspace URL/domain; `request.workspace` is authoritative.
Profile Workspace is navigation preference only. Domain/path disagreement fails
closed for everyone. Do not require Clear Workspace to manage teams or accounts.

Membership is the ordinary user/Workspace relationship. `Company.owner_id` is
canonical ownership, mirrored by Owner Membership. Runtime role grants are
Workspace-local (`WorkspaceRole`/`WorkspaceRoleGrant`); global Role identities remain
templates. Defaults seed once, never overwrite local edits. Membership, action
permissions, lifecycle, billing, entitlements and RLS are separate checks. Read
[control-plane contracts](architecture/control-plane-contracts.md) before changes.

## Business rules to preserve

Loans owns lifecycle services and immutable disbursal, repayment, release, renewal,
auction, custody and document evidence. Correct completed work through explicit
compensating/reversal actions. Rates supplies reference values; Loans freezes used
values. Party owns borrower identity. Notify delivery never determines loan state.
See [the constitution](constitution.md) and [dependency policy](implementation/dependency-policy.md).

Authorization precedes mutation and idempotent replay. Public actor-less business
commands are denied; internal bootstrap/delivery helpers are not staff APIs.
Servicing requires explicit repay/release/accrue/capitalize grants; renewal composes
release+approve+disburse. Setup/funding administration uses workspace settings
permission. Export/document permissions are recorded in the
[action-permission review](implementation/action-permission-review.md).

`Company.loan_workflow` defaults to EXTENDED. Owners can choose SIMPLE for atomic
review/approval and disbursal while retaining both evidence records. Adding staff
never changes this mode. Use plain labels: Dashboard, New loan, Loans. "Counter"
is historical workflow shorthand, not mandatory product language. See
[workflow choice](flows/loan-workflow-choice.md) and [business setup](flows/business-setup.md).

Setup is resumable and stays accessible after completion. Select a sole usable
series/product only on unbound new forms; preserve submitted/explicit values and
fixed edit choices. Gold 2% monthly, silver 4% monthly and INR 10 document charge
are editable setup form defaults, not automatic persisted policies.

Multiple-loan release groups at most 20 current-date full releases atomically.
One payer funds settlement; each loan records its own verified collector. Signed
quotes expire after ten minutes. Reversals and original loan evidence remain
canonical. See [multiple-loan release](flows/multiple-loan-release.md).

Official document issues retain exact bytes and immutable published layout/assets.
Reprints retain the original issue; fixed-renderer recovery is explicitly authorized
and audited. See [layout/print guide](flows/loans-document-layout-operator-guide.md).
Physical phone/camera and printer acceptance remains deferred.

## Private media and cache

Party/KYC and collateral media use authorized Workspace routes; templates/widgets
must not expose business storage URLs. Reviewed private responses disable caching.
Draft-only photo deletion preserves shared renewal file lineage. Development raw
media permits only company logos and personal profile pictures; deployment bucket,
proxy/CDN privacy still needs acceptance. See [private media](implementation/private-media-access.md).

Rates has no request cache middleware or cache-writing signal. Loans reads its
Workspace facade from PostgreSQL. Redis is optional via CACHE_URL; local memory is
the default display cache. Borrower autocomplete uses signed tokens and rebuilds its
authorized queryset, without cache-stored widgets. See [cache configuration](implementation/cache-configuration.md).

## Billing and operations

Billing is global control-plane data linked to Workspace subscriptions; browser
billing actions require canonical owner/Membership or the existing platform override.
Frozen checkout/order/amount/currency evidence precedes verified captured-payment
activation. Paid access ends at end_date through the shared effective policy; reads
do not rewrite stored status. Old payment replay cannot restore expired access.

Refunds and final review decisions are immutable. Full refunds await owner decisions;
ending access is restricted to the latest current started term. Known stale payments
can be closed after verified full return without granting old terms. No refund
issuance or guessed orphan-contract restoration. See [billing flow](flows/subscription-checkout.md).

Web/workers use restricted DB credentials. Migrate only with
`python manage.py migrate --settings django_project.settings.migration`.
Tests use `--settings django_project.settings.test`; adversarial RLS DML must run
under a restricted role. New Workspace-owned tables require direct non-null
ownership, forced RLS, registry coverage and isolation tests. Container/CI runtime
startup checks role/RLS and pending migrations; it never migrates. See
[container/CI guide](implementation/container-and-ci.md) and
[testing guide](implementation/testing-and-migrations.md).

Loans operator seed/integrity/notice commands require `--workspace-id` and own their
context. Seeding/dispatch require ACTIVE; read-only integrity supports recovery.
See [operator commands](implementation/loans-operator-commands.md).

## Owner constraints and current direction

The owner approved the bilingual Rokkad / रोक्कड़ logo with forest teal, gold,
and ivory. Shared product branding lives in `components/brand.html` and
`static/images/brand/`; preserve Workspace and issued-document identities.
See [branding](implementation/branding.md).

Development data is experimental; do not infer permission to alter production.
Public env examples contain placeholders only; never print or commit secrets.
The owner confirmed the historical OAuth credential was rotated/deleted; sanitization
was published with the access/media checkpoint. Historical Git cleanup is separate.

FW-001 optional owner-configurable license scope remains shelved pending fresh
review and explicit approval. Do not infer assigned-license or creator-only access.
FW-002 Razorpay setup/test-mode acceptance is shelved because setup has not started.
Do not request provider keys or run provider setup during other work. Acceptance is
still required before real paid onboarding. Neither item resumes from "proceed" on
unrelated cleanup.

R08/R09/R10 cleanup is complete: current docs are separated from history, tour
choices use current product names and preserve old saved answers, and six unused
schema-tenancy settings are removed. The tracked-source AST import guard replaces
the DEA facade guard; migrations/archives and intentional compatibility remain.
R13 removed four unused packages (Viewflow, Slick Reporting, activity-stream and
extensions) and 14 unreachable legacy templates; compatibility routes remain.
See [reachability evidence](implementation/dependency-template-cleanup.md).
Dashboard payment queues explicitly warn when schedule-review loans are excluded.
The unused exported monetary summary reports unavailable totals as None with a
count/completeness flag and requires matching Workspace context.
Dashboard schedule reads are batched per Workspace/date and share the canonical
termination predicate and obligation fold; no persistent cache.
All 136 canonical Loans routes use named workspace_loans adapters. Templates,
redirects, HTMX targets, checklist and borrower-history links explicitly carry the
Workspace. Old mapped-domain routes and named aliases remain available. The old
Loans dispatcher name is only a URL-building compatibility fallback that rejects
unknown paths; it never dispatches views or rewrites responses. New collateral and
storage labels encode scoped QR URLs; old mapped-domain scan links remain valid.
See [routing migration](implementation/loans-workspace-routing.md).
The two Loans setup-link failures were incomplete fixtures: readiness correctly
checks numbering before economics and borrowers. Fixtures now cover each stage.
The Loans views portion of R12 is complete: views.py is a compatibility import
file; feature handlers live in web/. Shared preview assets and loan read helpers
have small dedicated modules. Preserve decorated public imports and scoped routes;
feature modules must not import views.py. Test mocks patch the owning module.
See [module map](implementation/loans-view-organization.md). No business rules changed.
The orgs views portion of R12 is also complete: views.py contains compatibility
imports; account/preferences, slug adapters, workspace settings, role editing,
team/invitations, lifecycle and navigation have dedicated web modules. Shared
access helpers retain the existing policy. All retirement aliases remain; two
unrouted/uncalled backup view classes were removed. See the
[orgs module map](implementation/orgs-view-organization.md). Feature modules must
not import the facade. Model/form/renewal-service review remains separate; avoid
splits solely for size, speculative abstractions and blanket package upgrades.
Document layout, overlay, asset and print-profile forms now live in
loans/web/document_forms.py. loans/forms.py retains their public class imports;
document handlers use the owning module. Preserve fields, validation and scoped
assignment querysets when organizing other form families.
License creation, renewal and series setup forms live in loans/web/license_forms.py;
forms.py preserves their public imports and license_setup.py uses the owning module.
Economic, fee and monitoring setup forms live in loans/web/economic_forms.py;
forms.py preserves their public imports and economic_setup.py uses the owning module.
Form organization preserves policy scope choices, Workspace filtering and starter
defaults; calculations and persistence remain in existing services.
The eight funding forms live in loans/web/funding_forms.py; forms.py preserves
their public imports and funding read/action handlers use the owning module.
Keep eligible collateral, lender selection, confirmation words and request keys
unchanged during organization work; funding services still own lifecycle changes.
The five storage/physical-verification forms live in loans/web/custody_forms.py;
forms.py preserves their public imports and custody handlers use the owning module.
Preserve Workspace/location filtering and resolution inputs. Intake and lifecycle
forms and their shared formsets remain together pending a concrete need to move them.
Rates/appraisal review now drives the next increments. Lending setup shows actual
usable quotes; a source alone is not quote readiness. New/edit loan price preflight
uses the selected series/policy/date/metals and preserves the current form/files
when missing quotes require a Rates detour. Gold-only and appraisal-only loans
must not require unrelated quotes. Commands retain final validation. Quote ages
are displayed. The owner selected same-day quotes at new-loan approval on
2026-09-12, for methods that consume Rates. Enforcement is not implemented;
delayed-disbursal, backdated-entry and legacy-approval handling remain proposals
in the [origination review](implementation/origination-rate-freshness-review.md).
Do not silently change approved economics or reuse monitoring-age limits. Complete
monitoring and worker capacity are described below; see
[review](implementation/rates-appraisal-monitoring-review.md).
Rates quotes are immutable evidence: operator effective time is distinct from entry
time, corrections/withdrawals append actor/reason-linked records, and referenced
sources cannot be deleted. Source snapshots preserve recorded metadata. Use the
authorized Rates commands, not model updates or admin edits. Loans selects the
latest applicable INR pure-metal buying price per gram across sources with explicit
effective/recorded/ID ordering; `24k` remains the compatible pure-metal key, labelled
Pure metal for gold and silver. Historical lookups use current corrected knowledge;
completed loan evidence remains frozen. See [quote decision](adr/2026-09-11-rate-quote-evidence.md).
Current collateral monitoring enforces the effective monitoring policy's quote and
appraisal age limits, inclusively by local calendar date (zero means same-day).
Only evidence required by the frozen valuation method blocks coverage; stale or
missing required evidence is unknown. Active held collateral can receive a new
current-time appraisal through the authorized reassessment service, requiring
data.view/data.edit/loan.approve, method/reference/reason and the reviewed version.
It appends immutable evidence with quote context and marks its risk snapshot stale
within the transaction. Original loan/draft evidence stays unchanged; history is
readable with data.view. See [reassessment](flows/collateral-reassessment.md).

Loan health starts from all active Workspace loans, including unassessed ones.
Only today's successful V2 projection is current; reads derive outdated status.
Unknown collateral coverage is separate from assessment freshness and payment
performance. Missing current monetary assessments make whole-portfolio totals
unavailable. Source invalidation stays inside its RLS transaction; existing ERROR
projections remain errors (and retry candidates) until a successful refresh.
Monitoring policies amend through immutable, actor/reason-linked successors;
old values/end dates remain unchanged, same-scope precedence uses effective date
then version. Amendments cannot be backdated; original loan terms stay frozen.
The existing reassessment command supports explicit-Workspace bounded repeated
passes, oldest attempts first, under the restricted runtime role and ACTIVE
lifecycle. Optional Compose wiring does not itself start a worker. See
[loan health](flows/loan-health-monitoring.md) and
[monitoring decision](adr/2026-09-11-complete-loan-monitoring.md).

Launch sizing supplied by the owner: 30-100 loans processed per organization/day,
3,000-10,000 active loans per organization, and at least 100 organizations. The
worker is not capacity-validated for this
300,000-1,000,000-active-loan baseline. Correctness tests are not load acceptance.
Prioritize the [capacity review](implementation/rates-appraisal-monitoring-review.md#launch-capacity-requirements-and-review-2026-09-11)
before production claims or simply increasing batch sizes. Closed-loan monitoring
cleanup is implemented; realistic multi-Workspace load acceptance remains open.
The owner shelved further large-scale monitoring tests until better representative
hardware is available (FW-004). Do not automatically restart long local runs.
The one-hour target remains unproven; preserve measured findings for resumption.
See [the shelved work](plans/future-work.md#fw-004-launch-scale-loan-monitoring-capacity).

Closed loans keep their financial and monitoring evidence, but leave live health
calculations, source invalidation, active alert lists and background assessment.
Refresh rechecks state under the loan lock, including its error path. Reversing a
release to ACTIVE invalidates the saved assessment and resumes normal selection.

The monitoring command owns per-loan transactions through `risk_jobs`; it must not
run inside a caller's transaction/context. Candidate selection is bounded and
advisory; each loan is rechecked/locked through calculation and commit. Explicit
Workspace IDs receive round-robin turns. Successful rounds use a short busy pause;
empty/error-only rounds use the longer repeat interval. No Redis/queue or tenant
enumeration is introduced. See [worker turns](adr/2026-09-11-monitoring-worker-turns.md).

Single-schedule obligation reads now prefetch date-filtered allocations in two
queries and use the existing fold. Keep reversal effective-date filtering and
integrity findings unchanged. Mixed benchmarks are synthetic evidence, not a
production distribution or launch SLA.

Owner-selected monitoring launch acceptance target: all affected active loans
receive an updated health assessment within one hour of a metal-price change.
This is a target to load-test, not an established SLA. Closed loans are excluded;
individual authorized refresh remains available. Full-platform capacity remains
unproven until the 100-Workspace workload meets this target alongside servicing.

Health reassessment follows source changes and daily date rollover; worker polling
is not an hourly recalculation requirement for already-current loans. Operational
performance uses oldest unpaid contractual obligation DPD, with default Watch >=1
and Substandard >=90, independently of collateral coverage. This is not a formal
regulatory NPA engine; lender-specific classification/cure/reporting review is
captured as FW-003, unscheduled and not authorized by the capacity task. See
[the explanation](flows/loan-health-monitoring.md#payment-performance-and-the-npa-distinction).
