---
status: active
owner: project
updated: 2026-09-11
tags: [status, architecture]
---

# Status

## Current checkpoint

Branch: `rls-mvp`. Published application checkpoint: `16be7149` (2026-09-11).
All four orgs checkpoints are pushed: workspace/role settings (`ee31dda`),
team/invitations (`0177fc3`), lifecycle/navigation (`e434828`), and final
account/preferences, slug adapters and unused backup-view removal (`38eb1e3`).
Both Loans and orgs view organization are complete and published.
Document form organization is published: 13 layout/overlay/asset and
print-profile forms moved to `web/document_forms.py`, with existing public imports
preserved. Document setup handlers use the owning module; no business rules changed.
The three license/series setup forms are also extracted into `web/license_forms.py`
with compatible public imports. Both form increments are published as `16be7149`.
The three economic-setup forms are extracted locally into `web/economic_forms.py`
with public imports preserved and unchanged behavior; included in this local checkpoint.
No production deployment or real provider payment, refund or email was performed.

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
| R07/R12 routing/modules | R07 complete locally: all 136 canonical routes use direct Workspace adapters; response rewriting removed. Loans views portion of R12 complete: compatibility imports plus focused web modules; orgs views portion also complete locally; model/form/renewal-service review remains separate |

## Latest validation

- Economic form extraction: all 69 economic-default, setup UI, economic-policy,
  pawn-economics and scoped-route tests passed (26.998 seconds). All 34 original
  class ASTs from the previous forms.py checkpoint match; three public aliases
  preserve class identity. Runtime check, tracked import guard and explicit new
  module import-boundary validation pass. Documentation links and whitespace pass.
- [Workspace RLS checks for 16be7149](https://github.com/rajeshr188/rokkad/actions/runs/34594565045)
  passed, including dependency/docs/import checks, migration and restricted-runtime
  gates, boundary/first-loan checks, Loans regressions, image build and image
  runtime/static assets. Remaining-form review changes documentation only; all
  139 checked local documentation links pass.
- License/series form extraction: all 62 setup UI, license regulatory and scoped
  route tests passed (28.185 seconds). Across both form extractions, all 50
  original class ASTs match and all 16 public aliases preserve class identity.
  Runtime system check and tracked import guard pass; both new, untracked form
  modules also pass the same import-boundary validator explicitly.
- Document form extraction: 121 document/layout/print-profile, scoped-route and
  shell tests passed (18.438 seconds), plus all 32 setup UI tests (7.590 seconds).
  All 50 form class ASTs are unchanged; all 13 compatibility imports resolve to
  the owning class objects. Runtime system check, import-boundary check and its
  four unit tests, 138 documentation links and whitespace checks pass.
- [Workspace RLS checks for 38eb1e3](https://github.com/rajeshr188/rokkad/actions/runs/34591042913)
  passed: dependencies/docs/import boundaries, owner migrations and restricted
  runtime checks, boundary/first-loan checks, Loans regressions, image build and
  image runtime/static assets. Publication/review documentation passes all 138
  checked local links; no application changes were made during this review.
- Orgs views completion: all 229 orgs, invitations, ownership, role-grant, lifecycle,
  context/platform-override, shell, Loans-route and retirement checks passed
  (29.893 seconds). All 14 route-map source checks passed after the path update.
  Sixty-six moved function/class ASTs match; 137 public exports remain. No unresolved
  globals or imports back to orgs.views. System check, migration drift, import guard,
  current-doc links and staged whitespace pass. No business/schema changes.

- Lifecycle/navigation extraction: all 171 orgs, lifecycle, ownership, context,
  platform-override, slug-shell, shell-render and Loans-route tests passed
  (28.329 seconds). The updated dashboard source-dependency check passed separately.
  Seven function/decorator ASTs match; no unresolved globals or imports back to
  views.py. System check, migration drift, import guard, documentation links and
  staged whitespace pass. No service/model/template or policy changes.

- Team/invitation extraction: all 161 orgs, invitation/verified-email, ownership,
  role-grant, lifecycle, slug-shell and shell-render checks passed (14.363 seconds).
  Eleven handlers and three helpers retain identical ASTs; mock targets were
  updated without changing assertions. System check, migration drift, import guard,
  documentation links and staged whitespace checks pass. No policy/schema changes.

- First orgs extraction: all 174 workspace/settings, role-grant, ownership,
  lifecycle, shell and Loans-route tests passed in the final run (29.900 seconds).
  Nine handlers and three helpers retain identical function/decorator ASTs.
  Test mocks follow moved dependencies; assertions remain unchanged. Runtime
  system check, migration drift, 532-file import guard, 136 current-doc links and
  staged whitespace checks pass. No service, model, template or permission changes.

- Loans views completion: all 595 Loans, Party UI/history, route and shell tests
  passed together (124.773 seconds), plus four import-guard unit tests. All 56
  moved function/decorator ASTs match; 142 existing handler/helper exports remain
  available. No unresolved globals, feature-module cycles or imports back to
  views.py. Runtime system check, migration drift, import guard (528 Python files),
  132 current-doc links and staged whitespace checks pass. No business/schema changes.

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
The fb3db63 CI run was superseded by the publication-record push.
[Workspace RLS checks for af22f23](https://github.com/rajeshr188/rokkad/actions/runs/34588817552)
passed, including dependency/docs/import gates, runtime-role and boundary/first-loan
checks, Loans regressions, image build and image runtime/static-asset verification.

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

The selected Loans view organization work is complete; see the
[module map and compatibility rules](implementation/loans-view-organization.md).
The orgs view split is also complete; see the
[orgs module map](implementation/orgs-view-organization.md). Publication and CI
verification are complete. Document layout and print-profile forms are extracted
along with the three license/series setup forms in this checkpoint. The remaining
form-family review's economic-setup extraction is complete in this local checkpoint.
Next: extract the eight funding forms using the reviewed compatibility approach. See the
[review and validation scope](plans/project-hardening.md#remaining-r12-module-review).
Model and renewal-service restructuring are lower priority and remain unimplemented.
Razorpay and license scoping remain shelved.

Keep this file short: update current state and relevant evidence; move superseded
milestones to the [context archive](archive/context/README.md), retaining links.
