---
status: prepared
owner: project
updated: 2026-09-28
tags: [billing, release, migration, operations]
related: [billing-provider-readiness.md, recurring-agreements.md, container-and-ci.md]
---

# Paused billing release candidate

The candidate is built and preflighted. It is **not deployed** and does not enable
payments, authorizations or mail dispatch. Production migration and web replacement
are the next operational checkpoint; paid launch has additional acceptance gates.

## Exact candidate and rollback baseline

| Item | Verified value |
| --- | --- |
| Application source | `4a131587ee80e2e991bfb92660ec9196461744b0` |
| Candidate image | `rokkad:billing-paused-4a131587ee80` |
| Candidate image ID | `sha256:33ed455872008db4b70c92f9eff9ea5572b6b3b47ab4c28fefe3813f109b0d48` |
| Source archive SHA-256 | `82ae164a79e21f6a9bd6a44c4e51f1b5a52edc26923a3414b03b80eea56f31ad` |
| Current web image | `rokkad:overdue-page-20260928-47571dab51d5` |
| Current image ID | `sha256:75b091f332656693cdafa4b807ea32b2bb7e7ed877b36bc07f1689ffd5aaa4d8` |
| Current static volume | `rokkad_production_static_645aa7320997` |
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

## Production evidence and validation

Read-only inspection used the existing production runtime in a repeatable-read,
read-only transaction. Production has one plan, three trial subscriptions and zero
invoices, payments, legacy mandate IDs or invoice receipts. There is no historical
payment-mode ambiguity in this database. Preserve the existing plan and trials.
The populated local Test Mode database is separate and remains untouched.

Six unapplied migrations are confined to subscriptions:

1. `0012_plan_price_labels`: model field labels/choices/help text.
2. `0013_recurring_agreement`: binding/agreement/event evidence.
3. `0014_recurring_evidence_guard`: immutable evidence protections.
4. `0015_recurring_paid_cycle`: paid-cycle evidence.
5. `0016_recurring_cycle_evidence_guard`: paid-cycle protections.
6. `0017_recurring_access_resolution`: held-access review evidence and guards.

The current production image has no pending migrations for its own source. All
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

Dispatch remains disabled/marker absent; feedback, recovery and health timers stay
active on their existing images. No production settings, Compose file, timer,
schema, application record or live provider resource changed.

## Paused deployment procedure

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
