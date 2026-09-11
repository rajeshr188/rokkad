---
status: active
owner: project
updated: 2026-09-11
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
R12 orgs extraction has started: web/workspace_settings.py owns workspace setup,
profile/module/security pages; web/role_settings.py owns role editing; shared access
helpers live in web/access_helpers.py. views.py retains public imports. See the
[orgs module map](implementation/orgs-view-organization.md). Team/invitations are
next. Model/form/renewal-service review remains separate; do not split for size. Preserve history and avoid speculative abstractions
or blanket package upgrades. Prefer Django services/selectors, templates and HTMX.
