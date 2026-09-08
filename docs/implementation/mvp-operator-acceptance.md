---
status: active
owner: project
updated: 2026-09-08
tags: [mvp, acceptance, loans, party, workspace, rls]
related: [../STATUS.md, ../ROADMAP.md, ../adr/2026-09-08-workspace-constraint-boundary-and-default-document-evidence.md]
---

# MVP operator acceptance

## Scope and method

Baseline: pushed Phase 11 commit `c8de539` on `rls-mvp`.
The executable gate is `django_project.test_mvp_operator_journey`.
It uses Django's real HTTP middleware, CSRF-checked form submissions, a temporary
restricted PostgreSQL role, and real transaction commits. It does not mock
domain commands, create completed loans through fixtures, or bypass billing.
Public role/plan catalog and authenticated identities are test prerequisites;
Workspace creation and the lending setup/actions themselves run through HTTP.
Files use a temporary media directory and test-only evidence. No live customer
loan, real payment, provider message, or production database is changed.

This is server-side acceptance. No interactive browser automation is available
in this session, so visual layout, JavaScript behavior, camera access, physical
custody handoff, and printer acceptance have not been signed off.

## Verified checklist

| Step | Evidence / expected result |
| --- | --- |
| Create Workspace | Owner Membership is created; no automatic Subscription; navigation reaches the plan page. |
| Start trial | Owner POST starts a real trial and returns to the slug-scoped dashboard. |
| Configure lending | Create licence/evidence and numbered series, set gold/silver interest and calculation policies, seed/review/activate a product through HTTP. |
| Create/edit borrower | Party is saved and both success redirects remain on the explicit Workspace detail URL. |
| Originate | One photographed gold collateral item, principal 10,000, and three-month bullet product create a DRAFT with a numbered loan. |
| Approve/disburse | Real services produce APPROVED then ACTIVE state and a canonical recorded principal of 10,000. |
| Repay | A same-day 1,000 payment reduces recorded principal to 9,000; resubmitting its request key adds no event. |
| Release | Submit the prefilled exact quote with handoff confirmation; all collateral is returned and loan closes with zero recorded total due. |
| Reprint | Ticket, repayment receipt, and release memo return stored exact bytes; each source has one official issue. Ticket bytes remain unchanged after settlement. |
| Nested transaction | Repeat the entire journey inside a caller transaction; deferred checks complete while the correct Workspace is still visible. |
| Two Workspaces | Changing the preferred Workspace does not change an explicit URL; another Workspace cannot read a known Party ID under RLS. |
| Permissions | Member can open operational loan list, cannot administer lending/billing, cannot enter another Workspace, and loses access after Membership removal. |
| CSRF | An un-tokened setup mutation is rejected; normal form actions require and use a token. |

Run the core gate:

```powershell
.\.venv314\Scripts\python.exe manage.py test django_project.test_mvp_operator_journey apps.tenancy.tests apps.tenant_apps.loans.tests.test_document_issuance --settings django_project.settings.test --noinput --keepdb
```

For combined discovery include `--top-level-directory .` to keep test module
identities consistent. The final combined gate passes **795/795 tests** across
orgs, subscriptions, onboarding, tenancy, Party, Loans, Rates, Notify v2,
control-plane contracts, shell/routes, and all three operator scenarios.
Django checks, migration drift, and whitespace checks pass. See
[STATUS](../STATUS.md).

## Reproduced blockers and fixes

| Priority | Finding | Resolution |
| --- | --- | --- |
| P0 | Full release fails at COMMIT under the restricted role: its deferred custody trigger sees no collateral after context reset. | Outermost `workspace_context()` validates deferred constraints before restoring database context. Nested same-Workspace scopes allow the workflow to finish first. Constraint failure still rolls back. |
| P1 | Creating/editing Party returns `/party/<id>/` on a global host, dropping explicit Workspace identity. | Success redirects now use `workspace_slug_party_detail` and the validated request Workspace. |
| P1 | Full release prefills an amount with trailing precision beyond the two-decimal form limit; submitting it unchanged fails. | Format the form's initial amount to cents. The service still owns the quote and exact settlement validation. |
| P1 | Without a custom layout, normal PDF GETs regenerate bytes and create no official issue. | Persist the existing fixed renderer's output in the same immutable issue ledger used for custom layouts; reuse it on reprint. Explicit audited admin recovery remains separate. |
| P2 | General setup calls itself readiness while omitting licence/series, economics, and active products. | Add a first-loan setup guide with canonical links and clarify the general checklist's limits. |

The broader run also exposed a stale Party UI fixture with no Subscription;
its 23 failures occurred before the business views. The fixture now explicitly
starts a real trial, preserving the runtime billing boundary.

## Prioritized follow-up

1. **Completed: Party action routes.** Named `workspace_party:*` URLs reuse
   existing decorated views. Forms and redirects retain the validated Workspace
   slug, including invalid-form rerenders. Restricted-role HTTP tests cover
   contact CRUD, route/form coverage, CSRF, permissions, and cross-Workspace
   mutation denial. The follow-up gate passes 90/90 Party, MVP journey, and
   route-intent tests. Other Party workflows retain their focused domain tests.
2. **P1: Browser and counter acceptance.** Run the checklist on desktop and a
   mobile device, verify borrower search/select2, dynamic collateral forms,
   camera permission/fallback, validation messages, and actual print alignment.
   Record device/browser/printer, outcome, and operator observations.
3. **P2: Later-date lending scenarios.** Exercise interest catch-up, fees,
   reversals, renewal, auction, and storage/verification as complete HTTP
   journeys. Existing focused tests remain evidence for their individual
   services; the same-day journey above does not certify every product variant.
4. **P2: Other app deep links and provider pilots.** Audit Rates and Notify v2
   deep navigation; complete provider-configured email/WhatsApp acceptance with
   explicit authorization for real recipient messages.
5. **P2: UI design based on observations.** Use the operator findings to select
   the smallest Loans UI changes. No broad redesign is approved by this record.

## Operator record still required

| Check | Status | Evidence to record |
| --- | --- | --- |
| Desktop and mobile forms/search | Pending | Browser/device, scenario, usability findings. |
| Camera capture and denied-permission fallback | Pending | Device, permission path, saved-photo verification. |
| Ticket/receipt/release print | Pending | Printer/paper, readable fields, alignment, Original/Duplicate copies. |
| Physical handoff | Pending | Operator confirms UI settlement and actual item return procedure. |
| Real notification delivery/callback | Pending | Authorized recipient, provider attempt and delivery/callback evidence. |

See [README](../../README.md) for project setup.
