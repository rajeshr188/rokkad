---
status: deployed
owner: project
updated: 2026-09-28
tags: [billing, release, migration, operations]
related: [billing-provider-readiness.md, recurring-agreements.md, container-and-ci.md]
---

# Paused billing release

The release was deployed at **14:55 IST on 28 September 2026**. All six billing
migrations are applied. Payments, new authorizations and mail dispatch remain
disabled; this is not a paid launch. Preparation evidence below describes the
earlier checkpoint. The deployment result supersedes its pending items.

## Deployment result

The owner approved proceeding with backup, migrations and paused deployment.
A fresh server-local backup at **14:51:58 IST** contains 55,820,977 bytes; archive
catalog and SHA-256 verification passed. Digest:
`af34b83dec85d5f5b247008bb3fa4fdfae8de665e7fcd2934fe2fba2fdcc62bd`.
It remains on the server under the existing operational backup procedure.

Created and populated separate static volume
`rokkad_production_static_billing_4a131587ee80`, retaining the previous volume.
Applied only subscriptions 0012 through 0017 using `rokkad_prod_owner` and the
owner-only migration settings, with bounded lock/statement timeouts. Restricted
runtime startup, new table grants and owner-page checks passed before the switch.
All recurring tables remain empty and no migrations are pending.

Fingerprints of Plan, Subscription, SubscriptionEntitlement, WorkspaceAccessDecision,
BillingAccount, Invoice and Payment, plus every directly Workspace-owned Loans model
in all five Workspaces, match before migration, after migration and after deployment.
One plan and three existing trials are preserved. Workspaces 1–3 retain full access;
test Workspaces 4–5 retain recovery-only access. No financial or recurring backfill
occurred. Stored loan-ticket PDFs were read and hash-verified where present, without
issuing documents. Dashboard, overdue, loan detail, billing/plans and recurring
owner pages passed for all three operational Workspaces.

Compose changed only the pinned web image, static-volume reference and four explicit
paused settings: provider mode `disabled`, checkout false, recurring false and
platform sending false. Other resolved configuration and the settings file are
unchanged. No migration-owner credential reached web. Normal database writes remain
available for lending; read-only mode was confined to verification transactions.

HTTPS login, developer credits, privacy, terms, refund policy and the exact new
recurring JavaScript asset passed. Web is running with zero restarts. At **14:56 IST**,
billing inventory showed zero bindings, invoices, agreements, unresolved creation
attempts, webhook reviews and receipts, with no evidence blockers. Mail had no due
messages or queue flags. Dispatch remains disabled/marker absent; feedback, recovery
and health remain active on their existing images. No payment or email was sent.

Private additional evidence: `deployment-prepared.json`, `baseline.json`,
`migration-verified.json`, `deployment.json`, `post-deployment-health.json`, saved
Compose/release manifests and command logs in the same release directory. Automatic
code/static rollback was prepared but not needed. The old image/static volume and
fresh backup are retained; no reverse migration or restore was performed.

Next: align the mail worker images with this verified application release while
leaving dispatch paused, then complete provider/commercial and live configuration
acceptance before authorizing a bounded paying pilot.

## Exact candidate and rollback baseline

| Item | Verified value |
| --- | --- |
| Application source | `4a131587ee80e2e991bfb92660ec9196461744b0` |
| Deployed image | `rokkad:billing-paused-4a131587ee80` |
| Deployed image ID | `sha256:33ed455872008db4b70c92f9eff9ea5572b6b3b47ab4c28fefe3813f109b0d48` |
| Source archive SHA-256 | `82ae164a79e21f6a9bd6a44c4e51f1b5a52edc26923a3414b03b80eea56f31ad` |
| Previous web image retained for rollback | `rokkad:overdue-page-20260928-47571dab51d5` |
| Previous image ID | `sha256:75b091f332656693cdafa4b807ea32b2bb7e7ed877b36bc07f1689ffd5aaa4d8` |
| Previous static volume retained | `rokkad_production_static_645aa7320997` |
| Production database | `rokkad_production_20260924` |
| Restricted runtime | `rokkad_prod_runtime`, neither superuser nor BYPASSRLS |
| Migration owner | `rokkad_prod_owner`; owner-only migration settings |

Private server evidence is under `/root/rokkad-billing-release-20260928`:
`manifest.json`, `source.tar.gz`, `build-result.json`, `preflight.json`,
`worker-preflight.json`, `final-verification.json` and private logs. The package contains 1,256 tracked
application/Docker input files, excluding credentials, local data, uploads, dumps,
Git history and documentation. The image records its source revision, runs as
`app` and passes dependency verification. All 1,254 application files copied into
the image match the source manifest (the two Docker inputs are not runtime files).
The migration test added with this
preparation is separate from the pinned image; application source has not changed.

## Preparation evidence and validation

Read-only inspection used the existing production runtime in a repeatable-read,
read-only transaction. Production has one plan, three trial subscriptions and zero
invoices, payments, legacy mandate IDs or invoice receipts. There is no historical
payment-mode ambiguity in this database. Preserve the existing plan and trials.
The populated local Test Mode database is separate and remains untouched.

The six migrations pending at preparation were confined to subscriptions:

1. `0012_plan_price_labels`: model field labels/choices/help text.
2. `0013_recurring_agreement`: binding/agreement/event evidence.
3. `0014_recurring_evidence_guard`: immutable evidence protections.
4. `0015_recurring_paid_cycle`: paid-cycle evidence.
5. `0016_recurring_cycle_evidence_guard`: paid-cycle protections.
6. `0017_recurring_access_resolution`: held-access review evidence and guards.

The previous production image had no pending migrations for its own source. All
already-applied migration files match the candidate after line-ending normalization.
Other substantive source differences are billing/mail support and tests. The Loans
URL difference is whitespace; shared context/layout additions are gated Test Mode
rehearsal messaging. Existing lending services, public policies, fonts, ticket
renderers and deployed UI changes match after normalization.

The dedicated migration test upgrades a disposable test database from subscriptions
0011 to 0017. Three fictional trials, plan prices, entitlements and operator access
decisions retain identical model values; no financial or recurring evidence is
backfilled. **One migration test passed**, now included in CI. This is not a
production migration or a restored production-data rehearsal.

Candidate preflight passed restricted runtime/database/RLS checks for 117
Workspace-owned models and confirmed the exact migration plan. Existing owner
default privileges grant runtime table DML and sequence read/usage for new objects;
verify actual grants again after migration. Static collection built 865 files,
including recurring Checkout JavaScript, inside a disposable container. Production
static was untouched; a separate candidate static volume still needs staging.

The web candidate was tested with provider mode disabled, both purchase flags false
and sending false. It intentionally has no live webhook or dedicated worker SES
configuration. Deployment checks have no errors; retained warnings cover shared
Django email, debug-toolbar middleware and HSTS subdomain/preload policy. These do
not establish launch readiness. The candidate worker separately passed with the
existing private mail configuration: sending false, zero due messages and no queue
flags at **14:44 IST**. Four historical outcomes remain (two delivered, one bounced,
one complaint). No email was sent during preparation.

During preparation, dispatch remained disabled/marker absent, and feedback,
recovery and health stayed active on existing images. Preparation changed no
production configuration, schema, records or provider resources; deployment changes
are recorded above.

## Paused deployment procedure used

These steps are complete for the pinned release. Reassess current state before any
future release; do not treat the recorded six-migration plan as a reusable retry.

1. Recheck the pinned current image, target database, billing counts, worker state
   and migration plan. Save Compose/settings hashes and the static-volume identity.
   Review any differences before continuing.
2. Take and verify a fresh server-local operational backup using the existing
   production backup procedure. Preserve new lending transactions; never promote
   the Test Mode database or restore an old rehearsal snapshot.
3. Keep provider mode `disabled`, checkout/recurring flags false and shared mail
   sending false explicit in candidate configuration. Preserve other runtime and
   private-storage settings. Do not install live Razorpay credentials.
4. Stage collected assets in a new volume, retaining the current static volume and
   web image for rollback. Do not overwrite production assets in place.
5. Apply only the reviewed plan with
   `python manage.py migrate --settings django_project.settings.migration --noinput`
   using the existing private owner environment and explicit target database.
   Web and workers must never receive owner credentials.
6. Verify empty recurring tables, unchanged plan/subscriptions/access decisions,
   actual runtime grants, RLS and zero pending migrations. Run the candidate through
   `scripts/start_web.py` and read-only Workspace/billing/public-page smoke checks.
   Record a production lending baseline for before/after comparison.
7. Switch only the web image and new static volume through reviewed Compose
   configuration. Verify login, Workspace navigation, billing recovery, overdue
   loans, ticket access and public policies. Retain the exact deployed image ID.
   Mail timer scope/images can remain unchanged for this paused web release;
   updating worker images or enabling sending is separately reviewed work.

## Rollback and launch boundary

Before real billing activity, code rollback restores the saved Compose image and
static-volume reference while keeping purchase/sending flags paused. Leave the
additive billing tables and migration history intact. Do not reverse migrations or
restore the database simply to roll back code: that could discard evidence or new
lending transactions.

If payment/mail evidence appears, pause new authorization/dispatch and review it
before selecting an older image. Preserve webhook, cancellation and receipt records
and configured same-mode recovery. Never re-POST uncertain payment attempts.

Live activation still requires commercial/tax/invoice terms, mandate duration and
methods, protected live credentials/catalog, signed HTTPS callback acceptance,
receipt operations and outstanding provider acceptance. Scheduled live transitions
and live reservation release remain unsupported. See the
[production critical path](../plans/subscription-monetization-rollout.md#production-critical-path-reviewed-2026-09-28).
