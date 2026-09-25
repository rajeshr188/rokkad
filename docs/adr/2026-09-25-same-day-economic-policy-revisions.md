---
status: accepted
owner: project
updated: 2026-09-25
tags: [loans, policy, revisions, ltv]
related: [2026-08-09-loans-effective-dated-calculation-policy.md, ../flows/changing-loan-calculation-settings.md]
---

# Same-day calculation policy revisions

## Context

JSK's owner attempted to increase maximum LTV from 0.80 to 0.95. A configuration
already existed for the same date, so scope/date uniqueness rejected the whole
configuration save. Replacing the existing row would obscure which settings
earlier approvals used. The blank form also risked replacing saved choices with
starter values when an operator intended to change only LTV.

## Decision

- Economic policies and metal interest policies have a positive, sequential
  revision within their existing scope and effective start date. Existing rows
  become revision 1 without changes to their IDs, dates, values or references.
- Services append revisions under the Workspace row lock. Configuration, gold
  and silver remain one atomic command; an invalid value rolls back all three.
  The lock also serializes competing first saves in an empty scope. Database
  uniqueness remains enforced for scope/date/revision.
- Scope precedence is unchanged: economics uses licence then Workspace; metal
  rates use series, licence, then Workspace. Within scope, the latest applicable
  date wins, followed by the highest revision. Active/end-date filtering remains.
- The successful configuration command records its actor, policy IDs, revision,
  effective date, scope and LTV in the audit log. Previous rows are retained.
- Setup opens with the current Workspace default and applicable monthly rates.
  A history row's Use these settings link starts an explicitly scoped new version;
  GET makes no policy changes. Bound submissions retain their entered values.
- Approval/disbursal evidence, existing loans, fee policies, numbering, and RLS
  ownership remain unchanged. Reopening a loan is still an explicit workflow;
  a settings save never approves or disburses a loan.

## Consequences and deployment

Same-day revisions apply to subsequent draft evaluation and approvals resolving
that effective date, including backdated drafts. Already frozen approvals retain
their original complete policy. Repeated valid saves create another retained
version; they do not overwrite a previous version.

Migration 0025 changes two existing tables and their uniqueness constraints.
Stop the old web process for the schema transition, migrate using owner-only
settings, and start the new image under the restricted runtime role. Back up on
the server first. Once new revisions exist, fix forward; reversing to date-only
uniqueness can conflict with retained history.
