---
status: active
owner: project
updated: 2026-10-03
tags: [adr, decisions]
related: [../README.md, decision-log.md]
---

# Architecture Decision Records

Accepted and historical architecture decisions live here.

## Proposed ADRs

- [Khata agreements](2026-10-01-khata-agreement-design.md): confirmed rules and accepted local backend slices; integration and pilot gates remain under review.

## Current ADRs

- [Independent paper loans and renewal](2026-10-03-independent-paper-loans-and-renewal.md): one paper loan at a time, closing evidence without invented handovers, and ordinary subsequent renewal.

- [Loan transaction coverage](2026-10-03-loan-transaction-completeness.md): scoped paper confirmations, provisional monitoring and guarded reminder delivery.

- [Archive admission](2026-10-03-archive-admission.md): reconciled closed history through ordinary Loans, immutable archive links and shared source-identity protection.

- [Unified loan recording](2026-10-02-unified-loan-recording.md): accepted ordinary real-time/paper-entry design; initial dated receipt slice local, broader history/archive admission pending.
- [Khata operational reports](2026-10-02-khata-operational-report-semantics.md): current corrected-knowledge cash, current custody, dated refunds and bounded source-linked CSV.

- [Khata labels and pilot review](2026-10-02-khata-labels-and-pilot-review.md): immutable held-item labels, authenticated UUID scans and separate software/manual pilot gates.
- [Khata operator forms and native recovery](2026-10-01-khata-operator-forms-and-native-recovery.md): signed servicing reviews and offline exact-identity recovery with immutable source/media preservation.
- [Khata summaries and documents](2026-10-01-khata-summaries-and-documents.md): typed shared reads, distinct debt/limit fields and immutable private source PDFs.

- [Khata bounded corrections](2026-10-01-khata-bounded-corrections.md): immutable compensation, supported/refused sources and actual cash/custody safeguards.
- [BusinessDoc inheritance analysis](2026-05-03-businessdoc-inheritance-analysis.md)
- [Girvi BusinessDoc decoupling](2026-05-03-girvi-businessdoc-decoupling.md)
- [Loan disbursed/released event contract](2026-05-03-loan-disbursed-and-released-event-contract.md)
- [Platform admin override policy](platform-admin-override-policy.md)
- [Sidebar navigation source of truth](sidebar-navigation-source-of-truth.md)
- [Dynamic sidebar rendering](dynamic-sidebar-rendering.md)
- [Girvi flow boundaries with DEA](girvi-flow-boundaries-with-dea.md)
- [Girvi release and interest accrual lifecycle boundary](2026-06-27-girvi-release-accrual-lifecycle-boundary.md)
- [Tenant-billed subscription architecture (superseded)](2026-07-02-tenant-billed-subscription-architecture.md)
- [SaaS control-plane audit baseline](2026-08-17-saas-control-plane-audit-baseline.md)
- [Workspace request authority and RLS context](2026-08-17-workspace-request-authority-and-rls-context.md)
- [Workspace ownership authority](2026-08-17-workspace-ownership-authority.md)
- [Workspace authorization contract](2026-08-17-workspace-authorization-contract.md)
- [Workspace lifecycle and billing boundary](2026-08-17-workspace-lifecycle-and-billing-boundary.md)
- [Workspace entitlement contract](2026-08-17-workspace-entitlement-contract.md)
- [Loans rewrite domain and cutover architecture](2026-07-15-loans-rewrite-domain-and-cutover-architecture.md)
- [Pawn-loan collateral tranche economics](2026-08-05-pawn-loan-collateral-tranche-economics.md)
- [Pawn-loan release-and-renew-only boundary](2026-08-05-pawn-loan-release-and-renew-only.md)
- [Loans versioned configurable documents](2026-08-06-loans-versioned-configurable-documents.md)
- [Loans logical-layout and print-profile separation](2026-08-09-loans-logical-layout-and-print-profile-separation.md)
- [Loans product, obligation, exposure, and risk architecture](2026-08-11-loans-product-obligation-and-risk-architecture.md)

Older decision index files were preserved as [old decisions README](old-decisions-readme.md) and [decision log](decision-log.md).
