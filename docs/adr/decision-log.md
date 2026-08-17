---
status: accepted
owner: project
updated: 2026-06-27
tags: [adr]
related: []
---

# Decision Log

This is the live index of architecture decisions in docs/decisions.

## Entries

| Date | ADR File | Status | Owners | Affected Apps | Supersedes | Notes |
|---|---|---|---|---|---|---|
| 2026-05-01 | PLATFORM_ADMIN_OVERRIDE_POLICY.md | Accepted | Platform Architecture, Security, Tenant Framework | orgs, auth, tenant middleware | - | Platform override policy is superuser-only.
| 2026-05-01 | SIDEBAR_NAVIGATION_SOURCE_OF_TRUTH.md | Accepted | UI Architecture, Tenant Framework | templates, navigation, workspace UI | - | Template sidebar is active source of truth.
| 2026-05-03 | 2026-05-03_GIRVI_BUSINESSDOC_DECOUPLING.md | Accepted | Girvi Team, DEA Team, Platform Architecture | girvi, dea | - | Synchronous facade chosen over event-driven for financial posting. Facade implemented in dea/facade.py.
| 2026-05-03 | 2026-05-03_LOAN_DISBURSED_AND_RELEASED_EVENT_CONTRACT_ACCEPTANCE.md | Accepted | Girvi Team, DEA Team, Notify_v2 Team, Platform Architecture | girvi, dea, notify_v2 | - | Accepts v1 contracts for loan.disbursed and loan.released.
| 2026-05-03 | 2026-05-03_BUSINESSDOC_INHERITANCE_ANALYSIS.md | Accepted | Platform Architecture, Girvi, DEA | girvi, dea | - | BusinessDoc inheritance from girvi is wrong; BaseLoan/Loan/LoanPayment to be decoupled. PaymentVoucher/JournalEntryVoucher correctly inherit it.
| 2026-05-03 | (inline) DEA_FACADE_BOUNDARY | Accepted | Platform Architecture | girvi, contact, sales, purchase, dea | - | dea/facade.py is the only cross-app import point into DEA. girvi, contact, sales, purchase all migrated. 25 violations remain (tracked by scripts/check_dea_boundary.py).
| 2026-06-27 | 2026-06-27-girvi-release-accrual-lifecycle-boundary.md | Accepted | Girvi Team, DEA Team, Platform Architecture | girvi, dea, orgs | - | Accepts release as the owner of custody handoff and closure while keeping interest accrual as a separate event that may be invoked as a pre-release catch-up step. |
| 2026-08-17 | 2026-08-17-saas-control-plane-audit-baseline.md | Accepted | Project | control plane | - | Accepts the post-RLS audit as the incremental execution baseline. |
| 2026-08-17 | 2026-08-17-workspace-request-authority-and-rls-context.md | Accepted | Project | orgs, tenancy, accounts | - | Explicit domain/path identity establishes `request.workspace`; profile state is navigation-only. |
| 2026-08-17 | 2026-08-17-workspace-ownership-authority.md | Accepted | Project | orgs, accounts | - | `Company.owner_id` is the sole ownership authority with one mirrored Owner Membership. |
| 2026-08-17 | 2026-08-17-workspace-authorization-contract.md | Accepted | Project | orgs, supported business apps | - | One `WorkspaceAccess` policy and stable action codes will replace fragmented RBAC. |
| 2026-08-17 | 2026-08-17-workspace-lifecycle-and-billing-boundary.md | Accepted | Project | orgs, subscriptions | 2026-07-02-tenant-billed-subscription-architecture.md (part) | Workspace operational state and Subscription billing state are independent. |
| 2026-08-17 | 2026-08-17-workspace-entitlement-contract.md | Accepted | Project | subscriptions, supported business apps | 2026-07-02-tenant-billed-subscription-architecture.md (part) | One fail-closed typed entitlement service owns runtime feature and limit decisions. |

## Maintenance Rules

1. Add every new ADR here in the same PR.
2. Update status transitions (Proposed -> Accepted, etc.) promptly.
3. If superseded, update both old and new entries.
4. Keep one-line notes concise and factual.

