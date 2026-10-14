---
status: accepted
owner: loans
updated: 2026-10-12
tags: [monitoring, valuation, policy, evidence]
---

# Current monitoring valuation is an independent policy choice

The owner accepted MR-05 in the [combined monitoring plan](../plans/combined-loan-monitoring-20261011.md).
The [JCL diagnosis](../implementation/financial-health-jcl-20261011.md) shows why
refreshing appraisal-based loans cannot itself produce adequate current coverage.

## Decision

Add one choice to the existing immutable, effective-dated monitoring policy:
preserve each loan's saved valuation method (default), current calculated metal
value, latest approved appraisal, or the lower of calculated value and appraisal.
For paper/imported loans the saved method may be an admitted monitoring basis,
not proof of the original lending valuation. Existing policies receive the preserving default. No imported, paper or direct
loan is silently reassigned to metal-only monitoring.

Use the existing authorized setup service, Workspace lock, licence override,
latest-predecessor review, actor and reason. Amendments apply today or later;
older versions remain immutable. A licence policy replaces the complete Workspace
policy; its preserving default means its loans use their saved loan
method, not a per-field inheritance of the Workspace's valuation choice. An older
caller omitting the new choice retains the predecessor's setting.

Current collateral selectors resolve this policy for the assessment date. They
retain existing currency quantum, custody, evidence freshness and exposure rules.
Metal-only needs usable fresh prices and recorded item weight/purity; appraisal
needs fresh approved evidence; lower-of needs both. Missing required evidence
means unknown coverage. An explicit policy choice does not prove the original
lending decision or authorize collateral disposal.

Approval/origination continues using its economic policy and frozen evidence.
Interest, debt, terms, schedules, approved origination values and original LTV are
unchanged. A paper/imported basis cannot supply missing historical approval.
Accepted opening financial positions and paper-book checks retain
their independent limits. Risk writes remain derivative internal evidence, with
no financial posting or borrower messaging.

Save selected method, original method, policy identity and freshness limits in
assessment provenance. V8 makes older projections outdated without rewriting
events. Effective amendments use existing transactional invalidation; pending
future amendments do not invalidate earlier current assessments. Dated selectors
remain read-only restatements using available knowledge, not captured past decisions.

## Presentation and compatibility

Show assessment freshness, financial calculation support, transaction/book
coverage and valuation availability separately. A CURRENT assessment can have
unknown valuation or provisional paper-book coverage. Removing a misleading
monitoring-grace input leaves saved policy values intact: actual grace comes
from the loan's frozen product or accepted opening agreement and never shifts
contractual DPD. Severity remains derived from the actual risk condition; its
legacy JSON is preserved rather than exposed as configurable behavior.

Published fresh-business setup profiles 1 and 2 have no valuation-choice field.
Preserving policies remain compatible; restoring those profiles uses the new
preserving default. Export of an explicit choice is held with a specific error
until a newer profile can retain it. Do not silently omit or rewrite this choice,
or change a published contract. Ordinary supported loan-file exchange remains
independent of this wider setup package limitation.

## Release

Migration 0073 adds the defaulted field and a permitted-value database check on
the existing forced-RLS policy table. Existing UPDATE/DELETE protection remains
active. Apply only with owner migration settings during coordinated MR-06;
web and workers must share V8. Local delivery makes no production policy choice
and starts no worker. See [MR-05 validation](../implementation/current-monitoring-valuation-mr05.md).
