---
status: accepted
owner: project
updated: 2026-10-10
tags: [onboarding, workspace, loans, ux]
---

# Guided business setup over existing configuration

The Owner approved improving the basic Workspace creation and lending setup flow.
The existing checklist exposed separate settings without enough context, return
navigation or a concrete way to review the financial result.

Use six presentation steps over the existing Workspace, regulatory, product,
economic and Rates forms. Derive availability from persisted effective records
on every visit. Do not add a wizard model, completion flag or new tenant boundary.
Workspace creation keeps its existing service and Owner membership semantics.

The new/paper/import path and return-step markers are unsigned navigation hints
with a fixed allowlist. Save handlers build only the current resolved Workspace's
canonical return URL. Markers never select a Workspace, change authority, set a
financial purpose or confirm an import. Existing permissions, services, RLS and
ordinary redirects remain in force.

A business may configure gold, silver or both in an economic-policy save. At least
one monthly rate is required; the calculation policy and selected rate revisions
append atomically. Other metals retain their prior rates. This selection controls
which revisions are written, not whether a metal is allowed in lending. Readiness
must resolve calculation, monthly rate and usable valuation evidence for the same
metal and series. Borrower creation belongs to the first loan, not configuration.

The final step presents bounded fictional cash examples using saved settings and
the native monthly-contract/fee arithmetic. It does not create drafts, consume
numbers, value collateral or post money. Simple-interest closing examples assume
no payments or concessions. Compound settlement requires actual capitalization
events and is deliberately not projected. Product repayment schedules and actual
printed output remain subject to real loan review. The inline ticket summary is
visibly an unissued illustration, with a link to the existing document settings.

No schema migration, generalized wizard framework, billing or entitlement change
is needed. Configuration can become unavailable as effective dates, licence
validity, numbering or quote freshness change. English and Hindi labels and a
responsive stepper are included.

See the [business setup flow](../flows/business-setup.md) and
[implementation and validation](../implementation/guided-business-setup.md).

The subsequent [initial-setup access decision](2026-10-10-initial-setup-before-activation.md)
adds an owner-only recovery configuration surface before commercial activation.
