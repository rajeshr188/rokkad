---
status: active
owner: product
updated: 2026-07-04
tags: [brd, investor, client, non-technical]
related: [business-requirements-document-reverse-engineered.md, workflows.md, userflows.md, page_hierarchy.md, ../STATUS.md]
---

# Business Requirements Document (Client And Investor Version)

## 1. Executive Summary

Rokkad is a SaaS ERP platform designed for small and growing businesses, with strong fit for jewellery and loan-oriented operations.

Its core value is simple:

- Teams run daily business operations in one place.
- Every financial impact is traceable and auditable.
- Workspace data remains isolated and secure.

Rokkad combines operations and accounting so business owners can move faster without losing control.

## 2. Business Need

Small businesses often run operations across spreadsheets, messaging apps, and disconnected accounting tools. This causes:

- Data mismatch between operations and finance.
- Slow reconciliations and difficult audits.
- Limited control over team access and process discipline.

Rokkad addresses this by connecting operational workflows to controlled financial records in a single multi-workspace platform.

## 3. Product Vision

Build a document-first ERP where real business actions (for example loan disbursal, settlement, purchase, sale) produce reliable and visible business and accounting outcomes.

Long-term product direction:

- Workflow clarity for operators.
- Financial integrity for owners and accountants.
- Scalable multi-tenant architecture for SaaS growth.

## 4. Target Customers And Users

### Customer Profile

- Small and medium businesses.
- Multi-user operations with owner/admin control needs.
- High need for operational-financial traceability.

### User Roles

- Owner: full business control, policy and billing oversight.
- Admin: team and workflow administration.
- Accountant: accounting and reporting control.
- Member: day-to-day operations.
- Viewer: read-only visibility.

## 5. Business Outcomes

1. Increase operational speed by standardizing workflows.
2. Reduce accounting risk through controlled posting and reversal discipline.
3. Improve business visibility with module and report-level insights.
4. Support growth with workspace-level user and subscription management.
5. Lower audit and correction cost through traceability.

## 6. Scope Of Delivered Capability (Current)

Rokkad already provides meaningful production-grade capabilities across:

- Workspace lifecycle and team management.
- User onboarding, invitations, and role-driven access.
- Subscription-aware control-plane logic.
- Party/contact workflows and controlled portal access.
- Girvi loan lifecycle operations (create, transition, repayment, release).
- Inventory and product operations.
- Accounting engine with vouchers, journals, ledgers, periods, and reports.
- Commodity and business-event workflows for modern accounting-operational alignment.

## 7. Key Value Propositions

- Trustworthy financial outcomes:
  Business actions and finance are linked.
- Strong control and governance:
  Role-based access and workspace boundaries are enforced.
- Lower operational chaos:
  Structured workflows replace ad hoc manual processes.
- Scalable architecture:
  Tenant-aware SaaS design supports multiple independent workspaces.

## 8. Product Principles

1. Accounting integrity over convenience.
2. Clear workflow over technical complexity.
3. Security and tenant isolation by default.
4. Controlled corrections (reverse/correct) instead of hidden edits.
5. Backward-safe modernization with phased rollout.

## 9. Success Metrics (Business Lens)

1. Workflow adoption:
   - Share of core business operations executed inside Rokkad.
2. Financial control:
   - Reduction in duplicate/incorrect posting incidents.
3. Operational efficiency:
   - Time-to-complete key workflows (loan, settlement, posting).
4. Governance:
   - Role and permission violations prevented by system checks.
5. Customer readiness:
   - Onboarding completion and setup checklist closure rates.

## 10. Risks And Mitigation Themes

1. Legacy surface complexity:
   - Mitigate through phased route and UI consolidation.
2. Tenant safety in background tasks:
   - Mitigate with explicit tenant-context contracts.
3. Product identity versus internal schema naming:
   - Mitigate with user-facing workspace identity model separation.
4. Change management for users:
   - Mitigate with compatibility paths and gradual migration.

## 11. Investment Rationale

Rokkad has a strong implementation base, not just concept validation. The platform already demonstrates:

- Deep domain coverage.
- Multi-tenant SaaS foundations.
- Strong accounting safety principles.
- Structured modernization roadmap.

This positions Rokkad for disciplined growth from a technically credible foundation.

## 12. Next Milestone Focus

Near-term business milestones:

1. Consolidate user-facing workflows around canonical paths.
2. Close implementation gaps in tenant safety and product identity.
3. Expand KPI instrumentation and adoption reporting.
4. Continue phased modernization with compatibility protection.
