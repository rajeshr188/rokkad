---
status: proposed
owner: project
updated: 2026-09-09
tags: [architecture, saas, review, cleanup]
related: [control-plane-contracts.md, ../plans/future-work.md, ../STATUS.md]
---

# Project review: SaaS architecture, organization and legacy residue

Reviewed checkpoint: `4b08c3f` on `rls-mvp`. This is an evidence-based review and
proposed delivery order, not approval to implement all recommendations. Application
code, schema, business data and external services were not changed by this review.
The owner says the business data is experimental development data. Production
infrastructure, external storage and real payment-provider behavior were not audited.

## Assessment

Keep the modular Django monolith, Workspace as the SaaS tenant, forced PostgreSQL
RLS, Workspace-local action grants and Loans-owned immutable evidence. These are
coherent foundations for one owner or a staffed business. Neither microservices
nor replacing Workspaces with licenses solves the gaps found here.

The principal weakness is uneven completion: the operational lending workflow has
stronger evidence and tests than deployment, subscription checkout and some CLI
entry points. Historical documentation and compatibility code also obscure which
architecture is current. Prioritize correctness and reproducibility before a broad
directory reorganization or another visual redesign.

License scoping remains [FW-001](../plans/future-work.md#fw-001-optional-owner-configurable-license-scope):
shelved, optional, owner-configurable and subject to a fresh review and explicit
approval. This review does not reactivate it.

## Findings and proposed priority

P1 means fix before relying on the affected deployment, commercial or operational
path. P2 means a bounded maintainability/product improvement. P3 means investigate
or measure before changing anything. These are not claims of a production incident.

### R01 — P1: CI still targets removed schema tenancy

Evidence: [tenant-seed-smoke.yml](../../.github/workflows/tenant-seed-smoke.yml)
runs `migrate_schemas`, imports `django_tenants`, and names schema-based seed jobs.
Push triggers cover `main` and `dea-kiss`, not the active `rls-mvp` branch. Python
3.12 in CI is compatible with Django 6; the removed tenancy commands are the issue.

Replace this workflow with clean shared-schema migrations using the owner role,
restricted-runtime checks, all-model RLS metadata and adversarial tests, action
conformance, and the first-loan HTTP journey. Run it for the active development
branch and PRs. Keep fast boundary checks separate from a broader regression job.
Acceptance: a fresh runner passes without django-tenants or a prepared developer DB.

### R02 — P1: Container recipe is stale and the build context is not bounded

Evidence: [Dockerfile](../../Dockerfile) starts with Python 3.11, while
[requirements.txt](../../requirements.txt) pins Django 6.0.3. Django 6 supports
Python 3.12–3.14 ([official release notes](https://docs.djangoproject.com/en/6.0/releases/6.0/)).
The Dockerfile copies the entire context and there is no `.dockerignore` at this
checkpoint. Local `.env`, media, backups and virtual environments could enter an
image if present in its build context. This is an exposure risk, not evidence that
an image has been built or published with those files.

[docker-compose.yml](../../docker-compose.yml) also uses PostgreSQL 13, trust
authentication and `runserver`, with no explicit owner/runtime provisioning. Replace
it with a documented development recipe and a distinct deployment recipe. Align
supported runtime versions, exclude local/private artifacts, provision separate DB
roles and keep migrations out of web startup. Verify a clean build and startup.

### R03 — P1: Payment confirmation does not bind the paid order to the Workspace and plan

Evidence: [PaymentView.post](../../apps/subscriptions/views.py) accepts a client
`plan_id`, updates the current Workspace subscription, then finds an invoice using
only `razorpay_order_id`. It does not constrain that lookup to the current Workspace
or compare the order's saved plan/amount/currency with the requested subscription.
The subscription update precedes the missing-invoice rejection and the whole action
is not one transaction. A valid provider signature authenticates payment identifiers;
it does not establish these application-level relationships.

The [checkout template](../../templates/subscriptions/checkout.html) first POSTs
plan/cycle to `payment-create`, expecting an order ID. That URL maps to payment
confirmation, which instead expects a payment signature. There is also an immediate
entry-point defect: `@require_POST` is applied directly to the class method;
invoking `PaymentView().post(request)` raises `AttributeError: 'PaymentView' object
has no attribute 'method'` before entering the handler. Treat paid checkout as
unfinished. The scoping flaws described above must be fixed along with the entry
point, even though that immediate exception currently blocks the handler.

Create a server-owned checkout intent/invoice that fixes Workspace, plan, billing
period, amount and currency. Verify and lock that record before any subscription or
entitlement mutation. Make confirmation idempotent and transactional, with external
delivery after commit. Test another Workspace's order, changed plan, wrong amount,
unknown invoice, repeats and concurrent confirmations using mocked provider I/O.
Do not enable real paid onboarding until this path is verified end to end.

### R04 — P1: Billing retains user-owned assumptions and incomplete provider handling

Evidence: `Subscription` has `company`, with no `user` field/property. Nevertheless,
[invoice PDF and email helpers](../../apps/subscriptions/views.py),
[Razorpay order creation](../../apps/subscriptions/razorpay_service.py), and the
invoice template still access `subscription.user`. The reachable PDF path therefore
has an invalid attribute reference; its exception redirect also references a
`workspace` variable not defined in that method. Some other helpers have no normal
caller found and should be classified before repair/removal.

The webhook view reads `RAZORPAY_WEBHOOK_SECRET`, which is not declared in the
settings files inspected (and is absent in the local settings object). The adapter
reads payment IDs directly from `payload.payment`, while Razorpay's published
payload uses `payload.payment.entity` ([provider-owned example implementation](https://github.com/razorpay/razorpay-woocommerce/blob/master/includes/razorpay-webhook.php)).
The existing replay test mocks the adapter, so it cannot catch this mismatch.
The event row is not locked before the already-processed check, leaving concurrent
delivery behavior to review despite the unique provider-event identity.

Choose an explicit Workspace billing contact, correct invoice rendering, configure
the webhook secret, and test actual signed payload shapes without sending payments
or emails. Include retries, concurrent events and out-of-order captured/failed
events. Keep the canonical billing/entitlement services rather than introducing a
second billing state machine.

### R05 — P1: Three CLI entry points still require unavailable ambient context

Evidence: `dispatch_pawn_loan_notices`, `check_loan_document_integrity`, and
`seed_default_loan_products` have no `--workspace-id` argument and do not open a
Workspace context. Their downstream operations require one. The read-only integrity
selector was invoked without context and raised its explicit context error.
The neighboring [reassess command](../../apps/tenant_apps/loans/management/commands/reassess_pawn_loans.py)
already shows the intended explicit-ID/context pattern.

Add explicit Workspace selection, appropriate lifecycle checks, bounded execution
and useful command errors. Preserve the distinction between user-authorized commands
and internal delivery of previously authorized notice intent. Test commands from a
fresh process under the restricted role, including wrong/missing IDs. Do not just
call them inside a test's pre-existing Workspace context. No notices were dispatched
during this review.

### R06 — P1 before deployment: Make the runtime/operations contract executable

Evidence: [prod.py](../../django_project/settings/prod.py) falls back from
`DB_RUNTIME_USER` to `DB_USER`, and includes `*` in `ALLOWED_HOSTS`. The restricted
role check exists but is a deployment check; ordinary WSGI startup does not itself
run that command. Private-media acceptance is explicitly pending in the
[media review](../implementation/private-media-access.md).

Require explicit production runtime credentials and allowed hosts; run deployment
checks against the runtime connection. Verify private files at the actual proxy/
storage origin. Secure cookies are already forced true at the end of base settings;
do not misreport them as disabled because earlier assignments differ. Consolidate
duplicate security settings and document the actual TLS/proxy arrangement.

Publish one current operations runbook covering DB plus media backup/restore,
recovery objectives, migration rollback limits, scheduler ownership, failed delivery
alerts, tenant-aware support logs and billing recovery. Earlier backup/pilot notes
exist, but do not establish a current SaaS restore rehearsal. Workspace-specific
restoration in a shared DB needs deliberate reconciliation; do not blindly overwrite
rows from a whole-database dump. Retention/export/deletion policy remains a product
decision, not permission to hard-delete immutable loan evidence.

### R07 — P2: Replace Loans response rewriting with canonical URL generation

Evidence: [workspace_slug_loans_dispatch](../../apps/orgs/views.py) resolves legacy
Loans paths and rewrites `Location` and quoted HTML `/loans/` prefixes. Party, Rates
and Notify already have the simpler explicit Workspace adapter. Rewriting is a
tested transition mechanism, but makes correct URLs depend on response format and
puts app routing responsibility in the organization module.

Migrate Loans route families incrementally to named Workspace URLs, preserving old
redirects and tests for HTML, HTMX, redirects, downloads and multi-tab identity.
Do not remove the dispatcher until all canonical callers are converted.

### R08 — P2: Documentation currently teaches contradictory architectures

Evidence: [dependency-policy.md](../implementation/dependency-policy.md) is marked
active but says DEA is the accounting core and Contact owns party data. The current
[documentation index](../README.md) prominently lists retired Girvi/DEA/Contact
material. At this checkpoint AGENT_MEMORY has 2,846 lines and STATUS has 4,446 lines,
mixing current decisions with old milestones. The memory still says example-secret
sanitization is local although checkpoint `4d15477` published it.

Rewrite the current index and dependency policy around Party, Loans, Rates and
Notify. Keep a short current status and stable memory; move dated history to a
linked archive. Preserve accepted/superseded ADRs and migration history. Label
historical material rather than deleting the reasoning. Add documentation-link and
retired-import checks for current sources to CI.

### R09 — P2: Onboarding still offers retired product areas

Evidence: [TourPreferencesForm](../../apps/onboarding/forms.py) is still used by the
tour view and offers Accounting/Ledger, Sales/Invoicing, Purchase and Loan/Girvi.
These choices conflict with the current product, even if the main setup flow is
already improved. Align tour choices/help with supported apps and preserve or map
existing preference values where necessary. This is cleanup, not a new onboarding
wizard or a project-wide UI rewrite.

### R10 — P2: Settings and guardrails retain obsolete tenancy/DEA concepts

Evidence: [base.py](../../django_project/settings/base.py) retains clone-mode,
`TENANT_LIMIT_SET_CALLS`, `PG_EXTRA_SEARCH_PATHS`,
`SHOW_PUBLIC_IF_NO_TENANT_FOUND`, and multitenant static/media settings. Searches
found their definitions but no active application consumers. The naming and comments
mislead operators about the actual RLS model.

[check_dea_boundary.py](../../scripts/check_dea_boundary.py) guards a retired domain,
allows its facade import and has stale allowlist paths. Replace it with a supported
app import-boundary/retired-import check over tracked source files, not a recursive
scan into local virtual environments. Remove confirmed unused settings with a
configuration/documentation pass; do not rename database columns or migration
symbols as part of this cleanup.

### R11 — P2/P3: Dashboard work grows with the Workspace and can hide incomplete totals

Evidence: [counter_work.py](../../apps/tenant_apps/loans/selectors/counter_work.py)
loads every draft/approved/active loan and folds schedules per active loan before
pagination. [workspace_dashboard.py](../../apps/tenant_apps/loans/selectors/workspace_dashboard.py)
loads all loans, calculates active balances one at a time and silently skips certain
balance errors before summing. A partial total can look complete.

First expose incomplete-total status and affected-record counts. Then measure query
count and latency with representative development portfolios, batch related reads
and add justified indexes. Only introduce projections/caching if measurement warrants
them, with freshness and reconciliation against canonical evidence. Redis is not a
correctness fix for repeated per-loan work.

### R12 — P2/P3: Organize large modules by existing responsibilities

At this checkpoint Loans core models span 2,354 lines, Loans views 2,272, orgs views
2,042, Loans forms 1,405 and renewal services 1,446. Size alone is not a defect, but
these files mix multiple workflows and make boundary changes harder to review.

Extend the already-used `web/`, `services/`, `selectors/`, `documents/` and model
submodules. Separate orgs views into Workspace, membership/invitations, role settings
and compatibility routing. Move one feature family at a time with stable public
imports and route names; avoid a simultaneous model/app rename or generic service
framework. Business calculations stay in Loans services/domain; templates display
results. Keep local module tests plus a small cross-app journey suite.

### R13 — P3: Dependency and dead-template cleanup needs reachability proof

The installed environment passes `pip check`; that establishes dependency metadata
consistency, not vulnerability clearance or a reproducible clean installation.
`viewflow` and `slick_reporting` remain installed; current-source searches found
little direct usage beyond settings/older templates. Requirements also include
activity-stream/extensions packages without normal runtime usage found. Treat them
as candidates, not confirmed safe deletions. `render_block` is actively used.

There are 11 tracked `templates/contact/` files with legacy intra-template references.
Check template inheritance, dynamic render names, template tags and fixtures before
removing them. Group runtime, development and optional dependencies after a clean
install and usage inventory; run an advisory audit separately. No blanket upgrades
or security claims follow from package age alone.

## Target organization and user navigation

Keep these ownership boundaries explicit without moving every directory:

| Area | Responsibility |
| --- | --- |
| accounts | Personal identity, sign-in, account preferences |
| orgs | Workspace identity/lifecycle, membership, invitations, role grants |
| subscriptions | Workspace commercial terms, billing, entitlements |
| tenancy | RLS context, ownership contract, metadata checks |
| Party | Shared borrower/counterparty identity and private documents |
| Loans | Origination, servicing, collateral, releases, financial evidence/documents |
| Rates | Reference rates consumed and frozen by Loans where required |
| Notify | Delivery of authorized intent and delivery evidence |

User-facing grouping should remain: **Work** (Dashboard, Loans, Collateral,
Releases), **People & reference** (Parties, Rates, Notifications), **Business
settings** (setup, team/roles, billing, documents/imports), and separate **My
account / Workspaces**. Keep New loan prominent. Give loan setup one canonical
landing page and contextual links from work screens. Do not require clearing the
Workspace to manage account/team/billing. This is an information-architecture
refinement of the approved shell, not grounds for another redesign.

For docs, make `README` the entry point, `architecture` the current map, `domain`
the current business rules, `flows` the operator journeys, `implementation` the
technical/runbook details, and `plans/future-work` the shelved register. A single
active delivery plan should link to this review rather than duplicate its findings.

## Compatibility to preserve until deliberately retired

- Legacy Girvi/Contact redirects and retired inventory 410 responses are intentional
  compatibility behavior, not surviving business implementations.
- `contact.*` permission aliases still participate in Party access. Removing them
  needs a permission migration and regression tests, not a search-and-replace.
- `Company.schema_name` is historical metadata; immutable `slug` is routing authority.
- `apps/tenant_apps` is a package name, not evidence of schema-per-tenant isolation.
- Historical migrations, compensating events, source-document links and old ADRs
  must not be deleted as ordinary residue.
- Do not restore retired accounting/Girvi/Product capabilities because old docs or
  preferences mention them.

## Recommended incremental delivery

1. **Reproducible foundation:** R01/R02 and runtime-role gate from R06. Acceptance:
   clean CI/container setup, ordinary migrations and restricted-role checks.
2. **Operational correctness:** R05 plus R03/R04 before paid rollout. Give each its
   own tested checkpoint; no real provider messages/payments needed for regressions.
3. **Current product/documentation cleanup:** R08/R09/R10 and verified R13 residues.
4. **Maintainability/performance:** R07, visible incomplete dashboard totals, measured
   R11 optimization, and small R12 feature-module extractions.
5. **Pre-production rehearsal:** R06 media/privacy, restore, alerts and billing
   acceptance against the selected deployment. Keep deferred physical tests visible.

The next recommended implementation is step 1. Do not treat this list as permission
to run all phases or to reactivate license scoping.

## Review evidence and limits

Tracked source/configuration and current/historical contracts were inspected, with
targeted searches for retired imports, settings, templates, routing, commands,
billing, dependencies and operating procedures. Key invalid attributes and missing
command options were confirmed through local Django introspection. No live payment,
email, notification delivery, container publication or production access was used.
This is a broad architectural review with targeted verification, not a line-by-line
security audit. The final explicit-module run passed 66 tests covering tenancy,
registry, control-plane contract registration, supported-app authorization and
billing state/replay behavior. The first package-label run hit two relative-import
discovery errors; using explicit test modules resolved that invocation problem.
Include a tested discovery command in the replacement CI workflow. `pip check`
passed. These tests do not establish complete checkout, deployment or load readiness.

## Implementation follow-up

The owner approved incremental delivery. R01/R02 and the R06 runtime startup gate
are implemented in the first foundation checkpoint; see
[the delivery plan](../plans/project-hardening.md) and
[container/CI guide](../implementation/container-and-ci.md). The findings above
describe the reviewed `4b08c3f` baseline; remaining gaps are not thereby resolved.
R05's three operator commands now require explicit Workspace context, with lifecycle
checks and fresh-process restricted-role tests; see
[the command guide](../implementation/loans-operator-commands.md). R03/R04 billing
correctness is the next delivery increment.

### Billing implementation follow-up

R03/R04 checkout/order binding, captured-payment verification, atomic replay,
Workspace billing contacts and signed webhook processing have been implemented.
See [the flow](../flows/subscription-checkout.md) for evidence and the remaining
expiry/reconciliation/refund/provider acceptance work. The original findings above
are checkpoint evidence, not a claim that those specific defects remain unfixed.

### R08 current-documentation follow-up

The current index, dependency/testing guidance, Party/Notify overview, roadmap,
active plan, Status and Agent Memory now describe the supported product and current
priority. Their nine previous versions are preserved in the
[context archive](../archive/context/README.md); dated claims remain historical.
The CI current-entry link check validates local targets/headings without crawling
archived legacy sources or external sites. The retired-import guard replacement
remains explicitly queued with R10, not claimed as completed by this docs change.
R09 onboarding choices and R10 obsolete settings/guardrails are next. FW-001/FW-002
remain shelved.

### R09/R10 implementation follow-up

Tour preferences now offer Loans, borrower profiles, Rates, Notify and reports;
role preference choices no longer promise accounting/sales workflows. Historical
OnboardingChoice values are retained, with no permission or membership effects.
Removed definition-only ONBOARDING_TEMPLATE_CLONE_MODE, TENANT_LIMIT_SET_CALLS,
PG_EXTRA_SEARCH_PATHS, SHOW_PUBLIC_IF_NO_TENANT_FOUND, MULTITENANT_RELATIVE_MEDIA_ROOT
and MULTITENANT_STATICFILES_DIRS after application/settings/template/command searches
found no consumers. This does not change RLS, URL resolution or private storage.

The former DEA facade-only guard is replaced by scripts/check_app_boundaries.py and
CI coverage. Its AST scan covers tracked source roots, relative/direct imports and
literal dynamic imports, excluding migrations/archives. Computed imports remain a
manual-review limitation. No package, compatibility URL, permission alias or migration
was removed. Validation is recorded in current Status; R13 reachability is next.

## R13 implementation follow-up (2026-09-09)

Removed four unused direct packages and 14 unreachable legacy templates after
source/settings/template/migration/metadata review. Compatibility routes and
permission aliases remain. [Evidence and retained dependencies](../implementation/dependency-template-cleanup.md)
record the bounded scope. Clean image installation, pip check, template/static
smoke and 73 affected regression checks passed. This is not a vulnerability audit
or an exhaustive declaration that all remaining dependencies are used.

## R11 first implementation follow-up (2026-09-09)

The current UI consumes counter work, not the older monetary summary. Added a
visible exclusion warning to payment queues; the exported summary now reports
unavailable totals and enforces matching context. The [measured baseline](../implementation/dashboard-reliability.md)
shows 401 queries for 100 bullet loans. Batching remains the next increment;
no caching/projection or index redesign is claimed complete.

## R11 batching follow-up (2026-09-10)

Batched Workspace/date-scoped reads now share the canonical obligation fold.
The 100-loan benchmark improved from 401 queries/418 ms to 5 queries/19 ms;
restricted-role timing also measured 19 ms. All 54 targeted regressions passed.
See [measurement scope and remaining limits](../implementation/dashboard-reliability.md).
Portfolio memory/CPU still grow before pagination; no cache/projection was added.

## R07 first family follow-up (2026-09-10)

Five document/photo routes now reuse the ordinary Workspace adapter and existing
Loans paths/callbacks, with seven templates using named Workspace links. Remaining
families retain the dispatcher. [Scope and validation](../implementation/loans-workspace-routing.md)
include two setup-link failures reproduced without this change; these precede the
next HTML-family migration. R12 extraction remains pending.

## Setup-link test repair (2026-09-10)

Both R07 setup-link failures came from missing numbering prerequisites in the
fixtures. The real readiness flow correctly returned the first incomplete step.
Stage-specific fixtures now reach economics and borrower creation, while a new
test preserves numbering-first behavior and read-only GET. All 51 setup/route
tests pass; no application behavior or schema was changed.

## R07 browsing follow-up (2026-09-11)

Collateral/release lists and release detail now use direct Workspace adapters.
Templates and table links generate scoped destinations; scan and batch workflows
still use the scoped compatibility dispatcher. All 69 route/intent/media checks
passed, including populated HTMX/history responses and Workspace access denials.
See [migration scope](../implementation/loans-workspace-routing.md).

## R07 release-batch follow-up (2026-09-11)

Create/search/history/detail use direct Workspace adapters, with scoped form actions,
search URLs and completion redirects. HTMX history restores a full page. All 61
batch and routing tests passed, including service rollback/idempotency, CSRF,
release-action denial and Workspace search isolation. Remaining scan/loan workflows
still require the dispatcher; see the [migration record](../implementation/loans-workspace-routing.md).

## R07 collateral scans/labels follow-up (2026-09-11)

Direct collateral scan/label adapters now generate scoped redirects and new QR
targets. Existing printed labels/evidence are unchanged; legacy mapped-domain scan
entry remains supported. All 71 targeted tests passed. Storage-location scan/labels
remain next; [migration details](../implementation/loans-workspace-routing.md).

## R07 storage scan/label follow-up (2026-09-11)

Storage scans/labels use direct Workspace adapters, scoped new QR targets and
explicit transfer/verification/register redirects. Pending-item Workspace checks
and owner permissions remain intact. Validation covers 72 targeted checks; see
[routing record](../implementation/loans-workspace-routing.md). Storage forms remain next.

## R07 storage forms follow-up (2026-09-11)

Storage register/create and collateral placement/transfer now use direct Workspace
adapters, explicit form actions and scoped redirects. Owner authorization and
movement validation remain in the existing guards/services. Physical-verification
and other remaining route families still require the compatibility dispatcher.

## R07 physical-verification follow-up (2026-09-11)

The five physical-verification routes now use direct Workspace adapters and scoped
forms/redirects. Original immutable evidence, completion, compensation and owner
rules are unchanged. All 74 targeted route/media/intent checks pass. Notice register
and operational retry remain next; see the routing implementation record.

## R07 notice register/operational retry follow-up (2026-09-11)

The register and operational retry use direct Workspace adapters. Their forms,
source-record links and retry redirects retain scope without response rewriting.
Existing permissions and delivery services remain unchanged. Customer-notice
creation/retry are next; other families still use the compatibility dispatcher.

## R07 customer-notice actions follow-up (2026-09-11)

Customer-notice creation/retry now use direct Workspace adapters and explicit
scoped form/navigation/redirect URLs. Existing permissions, confirmation, notice
idempotency and delivery services remain. All 87 targeted notice/media/route/intent
tests pass. License setup routes remain next.

## R07 license setup follow-up (2026-09-11)

License pages/actions, register PDF and private revision download now use direct
Workspace adapters. Navigation, form actions and redirects are scoped explicitly;
setup permissions and revision/lifecycle services remain unchanged. Series
configuration is the next family. Optional license-scoped collaboration remains
shelved and is unrelated to this URL migration.

## R07 series setup follow-up (2026-09-11)

Series creation/configuration now use direct Workspace adapters with explicit form
actions, license links and redirects. Existing authorization and atomic numbering
services remain unchanged. Economics and workflow settings are the next family.

## R07 completion (2026-09-11)

All 136 canonical Loans routes now use direct Workspace adapters. Templates,
redirects, HTMX headers and selector-generated navigation are explicitly scoped.
Old Workspace aliases call views directly, mapped-domain routes remain available,
and the old dispatcher URL name only retains path-building compatibility with a
404 fallback. Response rewriting and secondary URL resolution are removed.
The earlier R07 evidence above is historical. R12 module organization remains
separate; see [routing record](../implementation/loans-workspace-routing.md).

Completion evidence covers 595 distinct broad/focused regression checks, with stale
compatibility and setup-label expectations corrected. System, documentation and
whitespace checks pass; exact runs are recorded in the routing implementation note.

## R12 first module extraction (2026-09-11)

After local hardening checkpoint c9e27f9, the five product-catalog setup handlers
(62 source lines) moved from Loans views.py to web/product_setup.py. Public view
imports and URL callbacks retain the same decorated functions. Function-body and
decorator ASTs match exactly; services, forms, templates and models are unchanged.
The new module has explicit dependencies and no import back to views.py. Economic
setup is the next bounded family; broader R12 work remains pending.

All 66 product-catalog/setup/Workspace-route checks pass, together with the runtime
system check, staged import guard, documentation links and whitespace checks.

## R12 economic setup extraction (2026-09-11)

Moved pawn_economics_setup to web/economic_setup.py, retaining its public import
in views.py and existing route callbacks. The handler/decorator AST is unchanged;
ten exclusive dependencies moved with it. Economic, interest, fee and monitoring
forms, defaults, services, authorization and Workspace filtering remain unchanged.
All 58 setup/Workspace-route tests and the runtime system check pass. Import-boundary,
documentation-link and whitespace checks pass. License/series setup is next;
broader R12 work remains pending.
