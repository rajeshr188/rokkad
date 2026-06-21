---
status: active
owner: project
updated: 2026-06-17
tags: [docs, navigation, architecture]
related: [STATUS.md, ROADMAP.md, GLOSSARY.md, AGENT_MEMORY.md]
---

# Rokkad Documentation

Rokkad is a SaaS mini ERP for small businesses. Accounting is the central core, with Girvi loan management, contacts, inventory, sales, purchase, commodity/rates, workspace management, authentication, authorization, subscriptions, invitations, onboarding, notifications, and team management around it.

This folder is the living documentation system. Historical notes, audits, and superseded plans are preserved under [archive](archive/).

## Start Here

- [STATUS](STATUS.md) - current system status.
- [ROADMAP](ROADMAP.md) - prioritized future work.
- [GLOSSARY](GLOSSARY.md) - shared domain language.
- [AGENT_MEMORY](AGENT_MEMORY.md) - stable context for AI coding agents.
- [Active plan](plans/active.md) - current work in progress.
- [Backlog](plans/backlog.md) - deferred ideas and risks.
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

- [Girvi app overview](apps/girvi/README.md)
- [Girvi architecture](apps/girvi/architecture.md)
- [Girvi models](apps/girvi/models.md)
- [Girvi workflows](apps/girvi/workflows.md)
- [Girvi userflows](apps/girvi/userflows.md)
- [Girvi refactor plan](apps/girvi/refactor-plan.md)

## Flow Docs

- [User flow](flows/user-flow.md)
- [Workspace onboarding](flows/workspace-onboarding.md)
- [Girvi loan lifecycle](flows/girvi-loan-lifecycle.md)
- [DEA posting flow](flows/dea-posting-flow.md)
- [Inventory, sales, purchase flow](flows/inventory-sales-purchase-flow.md)

## Implementation Docs

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
- [Troubleshooting](implementation/troubleshooting.md)

## Decisions

Accepted architecture decisions live in [ADR](adr/).
