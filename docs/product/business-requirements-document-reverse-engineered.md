---
status: active
owner: product
updated: 2026-07-04
tags: [brd, reverse-engineered, requirements, product]
related: [../AGENT_MEMORY.md, ../STATUS.md, ../constitution.md, workflows.md, userflows.md, page_hierarchy.md, ../implementation/django-tenants-architecture-audit.md]
---

# Business Requirements Document (Reverse-Engineered)

## 1. Document Purpose

This BRD is reverse-engineered from the currently implemented Rokkad codebase and live documentation.

It defines:

- What the system is expected to achieve for business users.
- What is already implemented versus what remains planned.
- Functional and non-functional requirements for current and near-term operations.
- Acceptance criteria that can be used by product, engineering, QA, and operations.

This document is intentionally implementation-aware and should be updated with each meaningful product phase.

## 2. Product Vision And Problem Statement

Rokkad is a multi-tenant SaaS mini ERP for small businesses (with strong jewellery and girvi focus) where accounting is the source of truth.

Business problem being solved:

- Small businesses need one system for operations (loans, inventory, party/customer management, notifications, and workspace administration) with reliable accounting outcomes.
- Operational teams need document-first workflows; they should not manually create accounting entries for every action.
- Business owners need tenant-isolated data, role-based access, and subscription-governed workspace operations.

Vision:

- A document-centric ERP where business events produce traceable accounting/commodity effects through controlled posting paths.
- Strong tenant isolation, auditability, and operational safety.

## 3. Business Objectives

1. Provide a secure workspace-per-tenant ERP platform with strict data isolation.
2. Ensure accounting integrity through immutable posting/reversal principles.
3. Support core daily workflows for:
   - Girvi loans.
   - Party/contact management.
   - Inventory/product operations.
   - Notifications.
   - Accounting events and reports.
4. Enable owner/admin control-plane workflows (workspace, team, onboarding, subscription).
5. Keep workflow continuity while modernizing architecture from legacy surfaces toward canonical business-event patterns.

## 4. Stakeholders

- Primary business users: Owner, Admin, Accountant, Member, Viewer.
- Workspace administrators: workspace owners and admins.
- Operations users: loan operators, inventory operators, finance/accounting operators.
- External-facing users: invited team members, portal-access customers (Party Portal MVP).
- Internal stakeholders: product, engineering, QA, support/operations.

## 5. Scope

### 5.1 In Scope (Implemented Baseline)

- Multi-tenant workspace model with schema-per-tenant architecture.
- Public control plane:
  - Authentication, onboarding, workspace creation/selection.
  - Memberships, invitations, role policy.
  - Subscriptions and seat/capacity enforcement paths.
- Tenant business modules:
  - Girvi loan lifecycle (GivenLoan/TakenLoan) with repayment/release/transition workflows.
  - Party model and compatibility bridge with legacy customer model.
  - Product/inventory management and stock operations.
  - Rates and notification management.
  - DEA accounting with posting, voucher, journal, ledgers, periods, reports.
  - Commodity accounting side-by-side model and business-event posting flows.
- Authorization hardening for multiple tenant modules.
- Read-only and posting-enabled business-event UI slices for major DEA events.

### 5.2 In Scope (Near-Term From Current Direction)

- Continue route and UI intent cleanup without breaking compatibility aliases.
- Continue deprecation of high-risk legacy accountant surfaces where canonical flows exist.
- Strengthen tenant safety in background jobs and commands.
- Improve workspace identity strategy (stop using schema_name as product-facing slug).

### 5.3 Out Of Scope (Current BRD Cycle)

- Big-bang migration from django-tenants to shared-schema RLS.
- Full rebuild of removed experimental sales/purchase runtime modules.
- Broad workflow redesign that ignores current compatibility constraints.

## 6. Business Rules And Principles

1. Accounting is central and non-negotiable.
2. Business documents are primary user artifacts.
3. Posted accounting entries are immutable.
4. Corrections happen via reversals/corrections, not in-place mutation.
5. Cross-module ledger effects must flow through DEA posting boundaries.
6. Tenant data must remain isolated by workspace.
7. Role-based permissions must be enforced server-side, not only in UI visibility.

## 7. Functional Requirements

Requirement IDs use format BR-FR-<domain>-<number>.

### 7.1 Workspace, Identity, And Tenancy

- BR-FR-TEN-001 (Must): System must support multi-workspace membership for a single global user account.
- BR-FR-TEN-002 (Must): System must resolve active workspace safely before tenant ERP access.
- BR-FR-TEN-003 (Must): System must enforce membership and subscription checks prior to tenant ERP workflows.
- BR-FR-TEN-004 (Must): Workspace onboarding must provision tenant schema and seed defaults with explicit success/failure handling.
- BR-FR-TEN-005 (Should): Workspace identity shown to users should be decoupled from internal schema_name compatibility slug.
- BR-FR-TEN-006 (Must): Unknown or mismatched tenant context must fail closed for protected tenant workflows.

### 7.2 Workspace Management, Team, And Invitations

- BR-FR-ORG-001 (Must): Owner/Admin users must manage workspace settings, team members, and invitations.
- BR-FR-ORG-002 (Must): Invitation accept flow must create membership through policy-controlled control-plane services.
- BR-FR-ORG-003 (Must): Role-change/removal operations must enforce sole-owner and privilege-escalation safeguards.
- BR-FR-ORG-004 (Must): Workspace manager and selector must allow safe workspace switching.
- BR-FR-ORG-005 (Should): Workspace setup checklist must surface readiness blockers and setup guidance.

### 7.3 Subscription And Entitlements

- BR-FR-SUB-001 (Must): Workspace access decisions must consider subscription activity and entitlement state.
- BR-FR-SUB-002 (Must): Seat capacity must be enforced in invitation and membership creation flows.
- BR-FR-SUB-003 (Should): Module discoverability should reflect entitlement-gated availability states.
- BR-FR-SUB-004 (Must): Billing and subscription management must remain accessible through owner-admin control-plane surfaces.

### 7.4 Party And Contact Domain

- BR-FR-PARTY-001 (Must): System must support Party as canonical external entity with multiple role support.
- BR-FR-PARTY-002 (Must): Party detail must support profile/contact/address/identifier/document maintenance with role-based authorization.
- BR-FR-PARTY-003 (Must): System must support compatibility bridge from legacy customer records.
- BR-FR-PARTY-004 (Should): Party merge must be guarded to prevent account/identifier linkage corruption.
- BR-FR-PARTY-005 (Should): Party export must support filtered business extracts for authorized roles.

### 7.5 Girvi Loan Operations

- BR-FR-GIRVI-001 (Must): Users must create and manage GivenLoan/TakenLoan workflows with canonical lifecycle states.
- BR-FR-GIRVI-002 (Must): Repayment workflows must use validated settlement read models and fail closed on posting failure.
- BR-FR-GIRVI-003 (Must): Release workflows must enforce settlement and custody readiness before mutation/posting.
- BR-FR-GIRVI-004 (Must): Loan transitions must be policy-gated and permission-gated.
- BR-FR-GIRVI-005 (Should): Loan detail must expose action-readiness and accounting linkage visibility.
- BR-FR-GIRVI-006 (Should): Notices and document generation should use centralized adapters/services.

### 7.6 Product And Inventory

- BR-FR-INV-001 (Must): Authorized users must manage product catalog, variants, attributes, and pricing structures.
- BR-FR-INV-002 (Must): Authorized users must perform stock operations (in/out/audit/split/merge/opening balance paths).
- BR-FR-INV-003 (Must): Inventory surfaces must be workspace-isolated and permission-guarded.
- BR-FR-INV-004 (Should): Inventory operations should align with document-centric posting/reporting traceability.

### 7.7 Rates And Notifications

- BR-FR-RATE-001 (Must): System must support rate and rate-source management for tenant workflows.
- BR-FR-RATE-002 (Must): Missing rate setup must be surfaced as actionable blocker for dependent workflows.
- BR-FR-NOTIFY-001 (Must): User-facing notification batch/settings workflows must be role-guarded.
- BR-FR-NOTIFY-002 (Must): Provider webhooks intended for external callbacks must remain publicly reachable and safely handled.

### 7.8 Accounting (DEA) Core

- BR-FR-DEA-001 (Must): Accounting posting must route through canonical posting command/service paths.
- BR-FR-DEA-002 (Must): Posting must be idempotent for duplicate source/economic payload submissions.
- BR-FR-DEA-003 (Must): Posted entries and dependent journal/account/ledger effects must be immutable.
- BR-FR-DEA-004 (Must): Reversal/correction flow must be service-governed with duplicate-reversal safety.
- BR-FR-DEA-005 (Must): Period lock/close rules must block prohibited posting operations.
- BR-FR-DEA-006 (Must): Trial balance and financial reports must remain monetary-accounting correct despite commodity records.
- BR-FR-DEA-007 (Must): High-risk manual accounting surfaces must be restricted to owner/admin/accountant users.
- BR-FR-DEA-008 (Should): Normal users should be guided to business events and report surfaces rather than legacy manual voucher screens.

### 7.9 Commodity And Business Event Layer

- BR-FR-COM-001 (Must): Commodity accounting records (movement, exposure, rate fixing) must remain side-by-side to monetary accounting.
- BR-FR-COM-002 (Must): Commodity events must not corrupt monetary trial balance boundaries.
- BR-FR-COM-003 (Must): Business-event flows must support preview, readiness, confirm posting, and idempotent duplicate submit behavior.
- BR-FR-COM-004 (Must): Event-specific impact boundaries must be preserved:
  - Fixed purchase/sale can create monetary plus commodity effects.
  - Unfixed purchase/sale creates commodity/exposure intent first; final monetary outcome occurs on fixing.
  - Monetary settlement creates monetary effects only.
  - Karigar custody events create commodity movement effects only.
- BR-FR-COM-005 (Should): Commodity master and account setup must be manageable through accountant-safe UX.

### 7.10 Customer Portal (Party Portal MVP)

- BR-FR-PORTAL-001 (Must): Portal identity must resolve through PartyPortalAccess grants without requiring workspace membership.
- BR-FR-PORTAL-002 (Must): Portal selectors must enforce strict party-scoped data visibility.
- BR-FR-PORTAL-003 (Should): Portal should remain tenant-path scoped until branded-domain strategy is production-ready.

## 8. Non-Functional Requirements

Requirement IDs use format BR-NFR-<number>.

- BR-NFR-001 Security (Must): Server-side authorization checks are required for all protected mutations and sensitive reads.
- BR-NFR-002 Tenant Isolation (Must): Data access must remain tenant-bounded by schema/workspace context; cross-workspace leakage is unacceptable.
- BR-NFR-003 Integrity (Must): Accounting and posting operations must preserve idempotency, immutability, and reversal correctness.
- BR-NFR-004 Auditability (Must): Critical business actions (workspace, invitations, posting, reversals, high-risk transitions) must be traceable.
- BR-NFR-005 Reliability (Must): Command/task flows that touch tenant data must run with explicit tenant context and fail closed on ambiguity.
- BR-NFR-006 Compatibility (Should): Route and template migrations should preserve compatibility aliases during staged cleanup.
- BR-NFR-007 Maintainability (Must): Cross-app interactions should go through facades/selectors/services instead of deep model coupling.
- BR-NFR-008 Operability (Should): Tenant provisioning, migrations, and seed parity checks must be executable via documented ops commands/runbooks.

## 9. Assumptions And Constraints

### Assumptions

- PostgreSQL with django-tenants is the active production architecture.
- Workspace data isolation remains schema-per-tenant during this BRD cycle.
- Current role model (Owner/Admin/Member/Viewer plus platform superuser) remains valid.

### Constraints

- Legacy route and UI compatibility must be preserved while canonical paths evolve.
- Existing seeded tenant schemas and production data require migration-safe changes.
- No big-bang architectural rewrite is allowed in this cycle.

## 10. Success Metrics

1. Tenant safety:
   - Zero confirmed cross-workspace data leaks.
2. Accounting integrity:
   - Zero confirmed posted-entry mutation incidents.
   - Duplicate submit does not create duplicate posting side effects.
3. Operational reliability:
   - Critical posting and transition paths show deterministic success/failure behavior.
4. Authorization quality:
   - Protected mutation paths enforce role and workspace checks in server code.
5. Product usability:
   - Owners/Admins can complete onboarding, team setup, and core workflows without undocumented manual intervention.

## 11. Acceptance Criteria (Release-Level)

### 11.1 Tenant And Control Plane

- AC-TEN-001: Workspace creation, membership, invitation acceptance, and workspace switching work through canonical service/policy paths.
- AC-TEN-002: Tenant-required routes reject unauthorized or unresolved tenant context.

### 11.2 Accounting And Business Events

- AC-DEA-001: Posting and reversal flows are idempotent and immutable by test coverage.
- AC-DEA-002: Period locks block prohibited postings with clear user feedback.
- AC-COM-001: Commodity movements/exposures/fixings do not alter monetary trial-balance correctness.
- AC-COM-002: Confirm endpoints for enabled business events are role-gated and duplicate-submit safe.

### 11.3 Operational Modules

- AC-GIRVI-001: Loan create, transition, repayment, and release paths enforce readiness and permission policies.
- AC-PARTY-001: Party create/read/update and profile child records are role-guarded and workspace-isolated.
- AC-INV-001: Product and stock workflows are role-guarded and tenant-isolated.

### 11.4 Subscription And Capacity

- AC-SUB-001: Invitation/membership operations enforce seat-capacity limits.
- AC-SUB-002: Entitlement-gated routes redirect to billing/upgrade paths when feature access is blocked.

## 12. Risks And Required Follow-Ups

1. Hard-delete safety risk:
   - Ensure production-safe default for company hard delete is disabled unless explicitly enabled.
2. Task/command tenant-context risk:
   - Background tasks and maintenance commands must require explicit schema/workspace context.
3. Workspace identity risk:
   - Replace schema_name as product-facing slug with stable business-facing workspace identity.
4. Legacy-surface confusion risk:
   - Continue guiding normal users away from manual accounting pages where business-event alternatives exist.

## 13. Traceability Map (High-Level)

- Tenancy and onboarding: apps.orgs, apps.onboarding, middleware_v2, tenant settings/URLConf split.
- Team and invitations: apps.orgs role policy, invitation accept adapters, workspace settings flows.
- Subscription and seats: apps.subscriptions services and orgs membership-capacity wrappers.
- Party and portal: apps.tenant_apps.party, PartyPortalAccess, portal selectors/routes.
- Girvi: apps.tenant_apps.girvi service/policy/selectors and transition workflows.
- Inventory/product: apps.tenant_apps.product access and stock/catalog surfaces.
- DEA accounting and commodity: apps.tenant_apps.dea posting/reversal/business_event services and report surfaces.

## 14. Document Maintenance Policy

- Update this BRD when a meaningful product phase lands or major behavior changes.
- Keep requirement IDs stable; append new IDs for new scope.
- Reflect implemented reality first, then clearly mark near-term target changes.
- Synchronize with status and architecture docs after major updates.
