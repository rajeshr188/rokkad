---
status: complete-local
owner: project
updated: 2026-10-10
tags: [onboarding, workspace, loans, ux, validation]
---

# Guided business setup

Workspace creation now leads into six contextual setup steps using existing
configuration forms and services. The journey supplies resume links, saved-state
summaries, paper/import starting guidance, number previews, lending choices,
calculation review and a bounded fictional payout/closing example. A borrower is
no longer required for business configuration. Saved economic revisions can write
gold only, silver only or both monthly rates atomically.

Navigation lives in `apps/onboarding/navigation.py` and
`services/business_journey.py`. Bounded markers survive form submissions and
internal setup links; successful saves return to the current canonical Workspace.
The setup selector matches monthly rates and valuation evidence within one usable
series, including prospective quote freshness and appraisal-only policies.
The read-only review selector and `loans/services/setup_examples.py` resolve saved
policies and fees and use the ordinary Loans arithmetic without financial writes.

The main template and reusable components provide an accessible stepper, visible
saved progress, example details and an unissued ticket summary. Advanced economic
groups collapse during guided entry and open for errors. English/Hindi text and
responsive CSS cover desktop, tablet and phone. Ordinary setup forms and non-guided
redirects continue to use their existing behavior.

## Verification

All 294 affected onboarding, economic-policy, setup UI, draft UI, rate-readiness,
Workspace URL/membership and rate-source regression tests pass. This includes the
new journey tests for read-only review, fee/advance credits, anchored month dates,
single-metal saves, configuration readiness, stopped series, explicit selection,
resume redirects and permission boundaries. Three older UI assertions were
updated to the current running/exhausted-series labels and new setup copy.

New modules pass parse/import checks, guided templates compile, and the existing
boundary checker passes for 1,110 tracked Python files. Django system checks and
migration-drift checks pass with no new migration. The active Hindi catalog
compiles; its existing placeholder metadata headers still warn. The exact
isolated regression and synthetic export databases are removed after validation.
No production deployment is performed.

Synthetic browser fixtures use fictional workspace, policy and fee records in a
separate disposable database. Headless Chromium checks all six steps in English
and Hindi at 1440, 768 and 390 pixels: 36 layouts, no horizontal overflow, one
current-step marker, visible headings and link navigation without JavaScript.
Screenshots and reports are local task artifacts under
`.tmp/guided-business-setup/`; they contain no production loan data.

## Local browser review (10 October)

The first native development launch exposed a stale local schema: the missing
LoanOriginationSettings.maximum_quote_age_days column was caught by best-effort
checklist collection, leaving PostgreSQL's Workspace transaction aborted. The
next dashboard query surfaced the secondary InternalError. Login/static checks
alone had not exercised a signed-in Workspace request.

Automatic approval review rejected applying pending migrations to the shared
development database without explicit approval. The safer completed remedy is
an isolated copy named rokkad_onboarding_review_20261010. A read-only local
development snapshot was restored into that new database, then existing
migrations were applied there through owner-only settings. Original loan
identity/state, event payload and sequence-counter fingerprints match after
migration. The shared development and existing pilot databases are unchanged.

The current source runs at http://127.0.0.1:8000 using the restricted runtime
role, separate cookies/cache/media, captured mail and inactive payment providers.
The development accounts were copied, so sign in again with the same local
development credentials. They remain separate from the pilot's accounts.
Review edits affect only this copy. No delivery workers run.

Authenticated HTTP checks pass for the jcl-13 dashboard, Workspace list, create
form and all six setup steps: nine 200 responses. The temporary verification
session was removed. Review scripts, private snapshot, configuration and logs
are task artifacts under .tmp/onboarding-local-review/. Restart with:

```powershell
.\.venv314\Scripts\python.exe .tmp/onboarding-local-review/serve_review.py
```

During the later Party merge-picker review on 10 October, unrelated unfinished
portability work introduced an invalid migration dependency and prevented shared-
checkout startup. The same launcher now loads a tracked committed-source snapshot
under .tmp/party-merge-picker/review-source, with only the four verified Party picker
implementation files overlaid. It reads the existing local environment in memory,
and keeps the same restricted review database, cookies and media; no environment
file is copied into the snapshot. The unfinished source/migration is unchanged.
Refresh this bounded snapshot deliberately after later changes are validated,
rather than assuming it follows every working-tree edit.

Stop the existing review server before restarting on the same port. The task
profile and copy are local only, with no production migration or deployment.

## Initial configuration before activation (10 October)

The first signed-in new-Workspace review exposed a redirect-chain gap: creation
returned the correct setup URL, but missing-subscription recovery middleware
redirected that request to Plans. Earlier tests asserted only the first redirect
or used fixtures that granted trials.

SubscriptionValidationMiddleware now permits exact configuration routes for the
canonical owner while workspace_activity remains recovery-only. Initial setup
is configuration, not commercial activation; the allowlist excludes lending,
customer entry, imports, funding, notices and team expansion. GET, HEAD and POST
retain normal CSRF, scoped resolution, role permissions and service validation.
Expired/cancelled/past-due subscriptions, read-only decisions and lifecycle
restrictions do not acquire this exception. Setup hides loan/import actions
until activity.can_write and offers an explicit activation link on review.

All 81 focused onboarding, access-policy, billing, public-trial and canonical URL
tests pass. Eight new regression tests create an ordinary owner and follow the
entire Workspace creation redirect without a trial fixture. They cover all six
steps, configuration forms and a real saved economic policy, no billing evidence
or loan events, still-gated operations, staff/nonmember denial, expiration,
platform restrictions, lifecycle and unsupported methods.

The isolated review server was restarted with current source. Six actual setup
steps and eight configuration forms return HTTP 200 for the owner's newly created
history-free Workspace; loan and register-import entry still land on Plans.
All allowlisted route names exist. The temporary authentication session was
removed. No new schema migration, trial allowance change or production deployment
is performed. See the [access decision](../adr/2026-10-10-initial-setup-before-activation.md).

## Financial and operational limits

The example assumes today's loan date, one selected metal and no repayments,
concessions or collateral valuation. It shows deductions and separate fees once.
Simple-interest periods use inclusive native anniversaries and selected part-month
rules; compound closing balances are not fabricated from configuration alone.
The illustration is not a product repayment schedule or an issued document.
Actual loans retain their full server validation, evidence and posting boundaries.

Paper/import paths reuse existing origination and guided register import. They do
not broaden supported import formats, change original facts or confirm data entry.
A chosen-metal save retains earlier rate evidence for other metals; it is not a
workspace-level metal restriction. Optional document customization, team invites
and dashboard reminders do not complete unavailable lending settings.

See the [accepted decision](../adr/2026-10-10-guided-business-setup.md) and
[user flow](../flows/business-setup.md).
