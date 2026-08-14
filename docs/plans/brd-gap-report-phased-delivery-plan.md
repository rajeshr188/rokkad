---
status: active
owner: product
updated: 2026-07-04
tags: [gap-report, brd, delivery-plan, roadmap]
related: [../product/business-requirements-document-reverse-engineered.md, ../product/business-requirements-document-client-investor.md, ../STATUS.md, active.md, backlog.md]
---

# BRD Gap Report And Phased Delivery Plan

## 1. Purpose

This report compares the reverse-engineered BRD baseline against current implementation maturity and defines a phased delivery plan for remaining high-value gaps.

## 2. Overall Readout

Current maturity summary:

- Strong implementation base in tenancy, control plane, Girvi, Party, inventory/product, and DEA accounting.
- Meaningful progress on commodity/business-event workflows.
- Remaining gaps are mostly consolidation, safety hardening, and usability simplification, not foundational capability absence.

## 3. Implemented Vs Missing (High-Level)

| Domain | Implemented (Now) | Missing / Gap | Priority |
|---|---|---|---:|
| Tenancy and workspace isolation | Schema-per-tenant isolation, middleware enforcement, workspace selection | Product-facing workspace identity still tied to compatibility schema slug in places | High |
| Onboarding and provisioning | Workspace creation + schema + seeding + checklist surfaces | Stronger all-or-nothing provisioning state visibility and failure recovery UX | High |
| Team/invitations/roles | Role policy, invitation acceptance controls, seat-capacity enforcement | Further consistency polish across all invite edge-case UX | Medium |
| Subscription/entitlements | Access service and route-level entitlement enforcement started | Full route-level feature coverage and reporting instrumentation | Medium |
| Party model rollout | Canonical Party model + bridge + portal MVP + guarded mutations | Complete retirement path of legacy customer-first UX and dependencies | High |
| Girvi operations | Lifecycle, repayment/release policy hardening, service extraction, permissions | Final simplification of legacy aliases and remaining UX consistency cleanup | Medium |
| Inventory/product | Catalog/stock operational coverage with authorization hardening | Deeper cross-linking of inventory impact from all business documents | Medium |
| DEA accounting core | Canonical posting path, reversal service, immutability and idempotency | Continue migration away from legacy manual surfaces where canonical flow exists | High |
| Commodity/business events | Event preview/readiness/confirm flows across major event types | Additional operator UX polish, consolidated operational guidance, KPI telemetry | Medium |
| Background jobs/commands safety | Significant command structure and runbook maturity | Strict explicit tenant-context contract across all tenant-touching tasks/commands | Critical |

## 4. Gap Details By Theme

### 4.1 Critical Gap A: Tenant Context Hardening Outside Request Cycle

Problem:

- Background jobs and some command paths can still be vulnerable to ambiguous tenant context assumptions.

Impact:

- Data safety and correctness risk in asynchronous or bulk operations.

Required outcome:

- Every tenant-touching background or command path must require explicit tenant identity and fail closed otherwise.

### 4.2 Critical Gap B: Workspace Identity Decoupling

Problem:

- Internal schema identifiers are still exposed as user-facing workspace identity in parts of the product.

Impact:

- Product UX and future architecture flexibility are constrained.

Required outcome:

- Stable product-facing workspace slug/identity independent from schema_name compatibility fields.

### 4.3 High Gap C: Legacy-To-Canonical Surface Consolidation

Problem:

- Legacy accountant/manual routes and compatibility aliases still add cognitive load.

Impact:

- Operators can choose less-safe or less-guided routes.

Required outcome:

- Canonical workflows are primary; legacy surfaces become clearly restricted, relabeled, or retired by plan.

### 4.4 High Gap D: Onboarding And Provisioning Transparency

Problem:

- Provisioning failure/partial success visibility and guided recovery can be improved.

Impact:

- Setup friction and support dependency during workspace bootstrap.

Required outcome:

- Clear provisioning states, actionable remediation steps, and consistent setup completion UX.

## 5. Phased Delivery Plan

## Phase 1: Safety And Identity Foundation (0-4 weeks)

Goals:

- Eliminate highest data-safety and product-identity risks.

Scope:

1. Enforce explicit tenant-context contract for tenant-touching tasks/commands.
2. Introduce/normalize product-facing workspace slug strategy.
3. Add regression tests for fail-closed tenant context behavior.

Exit criteria:

- No approved tenant task/command runs without explicit tenant identity.
- Workspace-facing URLs and UI use product-facing slug where planned.
- Safety tests pass for representative task/command paths.

## Phase 2: Canonical Workflow Consolidation (4-8 weeks)

Goals:

- Make canonical paths the operational default and reduce legacy confusion.

Scope:

1. Continue DEA legacy surface gating and selective retirement.
2. Continue Girvi and Party UX simplification on canonical flows.
3. Tighten navigation/discoverability around business-event and report-first operations.

Exit criteria:

- Normal users default to canonical business workflows.
- Legacy/manual surfaces are clearly role-restricted and labeled.
- Documented compatibility matrix updated.

## Phase 3: Onboarding And Adoption Acceleration (8-12 weeks)

Goals:

- Improve activation speed and reduce setup friction.

Scope:

1. Provisioning state and recovery UX hardening.
2. Setup checklist completion guidance refinement.
3. KPI instrumentation for onboarding completion and first-value actions.

Exit criteria:

- Workspace setup blockers are explicit and actionable.
- Measurable improvement in setup completion and first operation success rates.

## Phase 4: Scale Readiness And Operational Excellence (12+ weeks)

Goals:

- Strengthen platform operability for growth.

Scope:

1. Migration and tenant operations observability.
2. Reporting and audit telemetry maturity.
3. Cleanup of remaining low-value compatibility debt.

Exit criteria:

- Repeatable ops runbooks and diagnostics for tenant lifecycle at scale.
- Improved confidence in deploy/migration outcomes across tenants.

## 6. Recommended Ownership Model

- Product owner: prioritization, scope gating, KPI target definition.
- Engineering owner: architecture and implementation execution.
- QA owner: test strategy and release acceptance gates.
- Ops owner: runbook and environment readiness.

## 7. KPI Set For Tracking Plan Success

1. Tenant safety KPI:
   - Count of tenant-context violations in tests/production incidents.
2. Workflow adoption KPI:
   - Ratio of canonical workflow usage versus legacy surfaces.
3. Onboarding KPI:
   - Workspace setup completion rate within target timeframe.
4. Posting reliability KPI:
   - Duplicate-submit side-effect incidents.
5. Support KPI:
   - Setup and workflow support ticket reduction trend.

## 8. Decision Log Inputs

Before each phase start, confirm:

1. Scope freeze for that phase.
2. Acceptance test list.
3. Rollback and compatibility policy.
4. Documentation update obligations.

## 9. Immediate Next Steps

1. Prioritize Phase 1 tasks into executable engineering tickets.
2. Mark critical tenant-context hardening items with release-blocker status.
3. Finalize workspace identity migration sequencing with compatibility checkpoints.
