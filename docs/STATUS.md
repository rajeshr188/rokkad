---
status: active
owner: project
updated: 2026-09-11
tags: [status, architecture]
---

# Status

## Current checkpoint

Branch: `rls-mvp`. Local hardening checkpoint: `c9e27f9`; last published checkpoint:
`4b08c3f`. The local checkpoint includes foundation/operator/billing, branding,
documentation/onboarding/legacy cleanup and completed Loans routing. R12 product
setup extraction is committed separately as `752c248`; economic setup is committed as `b943118`. License/series setup is committed as `d5c4056`; print-profile setup is now extracted locally. Nothing has been pushed. No production deployment or real provider payment,
refund or email was performed during these increments.

The [hardening plan](plans/project-hardening.md) is the current delivery queue.
The [project review](architecture/2026-09-09-project-review.md) preserves the original
findings; its baseline descriptions are not a claim that fixed defects remain.

| Area | State |
| --- | --- |
| Bilingual branding | Approved Rokkad / रोक्कड़ artwork applied to shared UI, portal, admin, browser icons, checkout, billing communications, and README; see [branding](implementation/branding.md) |
| Workspace/RLS, local role grants, private-media routes, business setup | Implemented; access/media checkpoint `4d15477` published |
| Multiple-loan full release | Implemented, owner reviewed; `4b08c3f` published |
| CI/container runtime foundation and Workspace operator commands | Included in the local hardening checkpoint |
| Checkout, paid expiry, recovery, processed refunds and final owner review | Included in the local hardening checkpoint; development migrations through subscriptions.0009 applied |
| R08 current documentation | Current entry points rewritten; dated context archived and linked; documentation-link check added to CI |
| R09/R10 onboarding and legacy configuration/guardrails | Completed locally: current tour choices, six unused settings removed, tracked-source import guard in CI |
| R13 dependencies/templates | Completed locally: four unused direct packages and 14 unreachable templates removed |
| R11 dashboard reliability | Incomplete-queue warning and explicit unavailable monetary totals implemented; batching complete with shared calculations and restricted-role verification |
| R07/R12 routing/modules | R07 complete locally: all 136 canonical routes use direct Workspace adapters; response rewriting removed. R12 started: product-catalog, economic, license/series and print-profile setup views extracted; remaining families pending |

## Latest validation

- R12 print-profile setup: all 115 setup, print-profile, layout, document-issuance
  and Workspace-route tests passed. Nine handlers and two helpers retain identical
  function/decorator ASTs. Shared preview assets load through one helper without
  importing views.py. Runtime system, import-boundary, documentation-link and
  whitespace checks pass.

- R12 license/series setup: all 90 setup, license services/regulatory, numbering,
  notice and Workspace-route tests passed. Twelve handlers and four helpers retain
  identical function/decorator ASTs; two mock targets follow the moved dependencies.
  Runtime system, import-boundary, documentation-link and whitespace checks pass.

- R12 economic setup: all 58 setup/Workspace-route tests passed. Handler and
  decorator ASTs match the original; ten imports moved to the dedicated module.
  Runtime system, import-boundary, documentation-link and whitespace checks pass.

- R12 product setup: all 66 product-catalog/setup/Workspace-route tests passed.
  Moved five handlers (62 lines) with matching function/decorator ASTs; original
  public imports and route callbacks retained. Runtime system, staged import guard,
  documentation-link and whitespace checks pass.

- Checkpoint review: all 680 Loans/Party UI/billing/onboarding/deployment/route/shell
  tests passed in one combined run. Four import-guard unit checks, the staged-source
  import scan (514 Python files), runtime system check, migration drift and 128
  documentation links passed. Staged whitespace is clean after normalizing malformed
  line endings in five archived documents. Credential-pattern and artifact checks
  found no unexpected staged files; local secrets, logs and media are excluded.

- R07 complete: the broad Loans, borrower UI, legacy route and shell run exercised
  594 tests: 591 passed and three stale compatibility/UI assertions failed.
  Corrected those expectations; all 50 focused route/legacy/shell tests then passed,
  including a new response-preservation test (595 unique checks covered across runs).
  Earlier focused runs also corrected obsolete URL expectations, a query-chain
  mock and a whole-database assertion that needed to target its own series.
- All 136 canonical routes resolve directly and preserve their original decorated
  callbacks. Two-Workspace page checks prohibit dispatcher use; membership/domain
  conflicts, CSRF, action permissions, lifecycle/numbering, HTML/HTMX navigation,
  binary documents and streaming response preservation are covered. No business
  service or schema change. Runtime system, 128 current-doc links and whitespace
  checks pass. Provider and physical-device acceptance remain deferred.
- Per-family history is retained in the [routing record](implementation/loans-workspace-routing.md).

- R11 batching: 54 targeted regressions and the 100-loan benchmark passed.
  Queries fell from 401 to 5; median selector time from 418 ms to 19 ms
  (restricted role also 19 ms). Persisted schedule/payment/reversal parity and
  foreign-Workspace denial verified. No schema or cache changes.

- Saved the approved gold-stroke / Hindi ra monogram logo as
  `static/images/brand/rokkad-bilingual-monogram.png`; verified byte-for-byte
  against the generated source. This save does not replace current UI assets.

- Branding: runtime system check, static collection dry run, eight affected
  template compilation checks, Hindi text checks, documentation links, and diff
  whitespace checks passed. Existing shell smoke suite: 15 passed,
  one setup-page failure reproduced with pre-branding base/navigation templates
  (`test_workspace_settings_setup_page_renders_checklist`); its stale label assertions
  were corrected and the shell suite passed during R07 completion. Desktop (1440px) and
  mobile (375px) browser renders of home, login, Workspace, portal, and admin
  loaded the logo without horizontal overflow. Bootstrap was cached for visual
  verification because sandbox browser access to the CDN was unavailable;
  external icon fonts/scripts were not part of this visual check. No deployment,
  billing-provider action, or issued-document mutation was performed.

- R11: 33 selector/template/route tests and a synthetic 100-loan service-backed
  benchmark passed. Queue calculation: 5/41/201/401 queries at 1/10/50/100 active
  bullet loans; 100-loan median 418 ms. See [scope and baseline](implementation/dashboard-reliability.md).

- R13: 73 route/Party UI/dashboard-selector/deployment checks passed. Clean Docker
  build and pip check passed; removed packages verified absent, current templates
  loaded, model/template/URL checks and static collection passed without network.
  Local runtime check and migration drift passed. Corrected the rollout-doc test
  to inspect the linked R08 history. See [removal evidence](implementation/dependency-template-cleanup.md).

- R09/R10: 26 onboarding/deployment tests and four import-guard tests passed;
  guard scanned 493 tracked Python files. New tour preferences preserve historical
  answers and confer no membership/permissions. Removed only definition-only
  schema-tenancy settings. Runtime system check, migration drift, local-doc links
  and whitespace pass; no migration or normal development data changes.

- Foundation: 90 foundation/access/MVP checks plus six deployment-entrypoint tests;
  clean Docker build, restricted startup/HTTP smoke, negative owner-role startup
  and collectstatic verified in a removed disposable stack.
- Operator commands: 25 command/product/notice checks, including fresh-process
  restricted-role context and cleanup.
- Paid expiry: 51 subscription checks and 65 broader boundary checks (overlapping).
- Recovery: 15 dedicated checks, including concurrency, rollback and scope denial.
- Final reviews: 46 review/recovery/checkout checks, followed by 12 final review
  checks including concurrency and rollback. Provider I/O and receipt mail mocked.
- Latest documentation increment: 119 local links/fragments across 12 curated
  entry files and whitespace checked. Nine prior documents (8,066 source lines)
  preserved with archive notices and rebased relative links. No runtime behavior or schema changes; no database suite needed.

Exact historical validation and known limitations are retained in the
[status snapshot](archive/context/2026-09-09/STATUS.md). These counts describe runs
at their checkpoints, not a claim that one fresh whole-repository suite ran today.
GitHub-hosted CI execution still awaits a push.

## Deferred acceptance and owner decisions

[FW-001](plans/future-work.md#fw-001-optional-owner-configurable-license-scope):
license scoping is optional and shelved; fresh review and explicit approval required.
[FW-002](plans/future-work.md#fw-002-razorpay-setup-and-provider-test-mode-acceptance):
Razorpay setup/provider testing is shelved; the owner has not begun setup. Mocked
billing checks do not establish real paid-onboarding acceptance.

Physical phone/camera and printer checks remain deferred. External storage/CDN
privacy, production TLS/restore/alerting and selected-deployment acceptance remain
open. Orphan/legacy payment contracts are support investigations, not guessed
reconstructions. Refund issuance, proration and chargebacks are not automated.

## Next increment

Continue R12 with document layout setup views, retaining public imports and route
callbacks. Product, economic, license/series and print-profile setup now live in
dedicated web modules; preview asset loading is shared.
All R07 Loans route families are migrated, including economics/workflow, documents,
reports, lifecycle actions and funding. Razorpay and license scoping remain shelved.

Keep this file short: update current state and relevant evidence; move superseded
milestones to the [context archive](archive/context/README.md), retaining links.
