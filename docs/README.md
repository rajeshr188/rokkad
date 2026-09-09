---
status: active
owner: project
updated: 2026-08-17
tags: [docs, navigation, architecture]
related: [STATUS.md, ROADMAP.md, GLOSSARY.md, AGENT_MEMORY.md]
---

# Rokkad Documentation

Rokkad is a shared-schema Django SaaS application for operational pawn lending.
Its supported business applications are Party, Loans, Notify v2, and Rates.
PostgreSQL forced RLS isolates Workspace-owned data.

This folder is the living documentation system. Historical notes, audits, and superseded plans are preserved under [archive](archive/).

## Start Here

- [STATUS](STATUS.md) - current system status.
- [ROADMAP](ROADMAP.md) - prioritized future work.
- [GLOSSARY](GLOSSARY.md) - shared domain language.
- [AGENT_MEMORY](AGENT_MEMORY.md) - stable context for AI coding agents.
- [Active plan](plans/active.md) - current work in progress.
- [Future work](plans/future-work.md) - shelved ideas, decisions and restart points.
- [Legacy backlog](plans/backlog.md) - historical items requiring current-context review.
- [Completed work](plans/completed.md) - implementation history.

## Domain Docs

- [Accounting / DEA](domain/accounting.md)
- [Girvi](domain/girvi.md)
- [Contact](domain/contact.md)
- [Inventory, Sales, Purchase](domain/inventory.md)
- [Workspace, Auth, Authorization](domain/workspace-auth.md)
- [Subscriptions](domain/subscriptions.md)
- [Notifications](domain/notifications.md)

## App Internals

- [Canonical SaaS control-plane contracts](architecture/control-plane-contracts.md)
- [SaaS control-plane architecture audit](architecture/saas-control-plane-architecture-audit.md)
- [Current Workspace resolution and PostgreSQL RLS chain](architecture/current-workspace-resolution-chain-using-postgres-rls.md)
- [Loan exposure and risk architecture](architecture/loan-risk/README.md)
- [Loans architecture and Girvi parity review](apps/loans/architecture-and-girvi-parity.md)
- [Girvi app overview](apps/girvi/README.md)
- [Girvi architecture](apps/girvi/architecture.md)
- [Girvi models](apps/girvi/models.md)
- [Girvi workflows](apps/girvi/workflows.md)
- [Girvi userflows](apps/girvi/userflows.md)
- [Girvi refactor plan](apps/girvi/refactor-plan.md)

## Flow Docs

- [User flow](flows/user-flow.md)
- [Release multiple loans: selection, collectors and settlement](flows/multiple-loan-release.md)
- [Workspace onboarding](flows/workspace-onboarding.md)
- [Girvi loan lifecycle](flows/girvi-loan-lifecycle.md)
- [DEA posting flow](flows/dea-posting-flow.md)
- [Inventory, sales, purchase flow](flows/inventory-sales-purchase-flow.md)

## Implementation Docs

- [Django schema tenancy to PostgreSQL RLS migration guide](implementation/django-schema-tenancy-to-postgresql-rls-guide.md)
- [Dependency policy](implementation/dependency-policy.md)
- [DEA vouchers](implementation/dea-vouchers.md)
- [Girvi services](implementation/girvi-services.md)
- [Girvi query annotations](implementation/girvi-query-annotations.md)
- [Contact model migration](implementation/contact-model-migration.md)
- [Template system](implementation/template-system.md)
- [Tenant seeding](implementation/tenant-seeding.md)
- [Testing and migrations](implementation/testing-and-migrations.md)
- [Dynamic preferences](implementation/dynamic-preferences.md)
- [UI principles](implementation/ui-principles.md)
- [Workspace context](implementation/workspace-context.md)
- [Subscription architecture blueprint](implementation/subscription-architecture-blueprint.md)
- [Subscription implementation checklist](implementation/subscription-implementation-checklist.md)
- [Troubleshooting](implementation/troubleshooting.md)

## Product Docs

- [Reverse-engineered BRD](product/business-requirements-document-reverse-engineered.md)
- [Client and investor BRD](product/business-requirements-document-client-investor.md)
- [BRD gap report and phased delivery plan](plans/brd-gap-report-phased-delivery-plan.md)

## Decisions

Accepted architecture decisions live in [ADR](adr/).
