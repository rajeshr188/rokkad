---
status: active
owner: project
updated: 2026-09-09
tags: [docs, navigation, architecture]
---

# Rokkad documentation

Rokkad is shared-schema pawn-lending SaaS built around Party, Loans, Rates and
Notify v2. Workspace-owned business data is isolated by PostgreSQL forced RLS.
Start with current guidance below. Retired accounting/ERP material is historical,
not an instruction to reintroduce it.

## Current work and decisions

- [Status](STATUS.md): checkpoint, validation and remaining acceptance.
- [Agent memory](AGENT_MEMORY.md): stable decisions and owner constraints.
- [Active delivery](plans/active.md) and [hardening plan](plans/project-hardening.md).
- [Roadmap](ROADMAP.md) and [Future work](plans/future-work.md): shelved ideas and resume conditions.
- [Project architecture review](architecture/2026-09-09-project-review.md): original findings and follow-ups.
- [Constitution](constitution.md), [control-plane contracts](architecture/control-plane-contracts.md)
  and [ADRs](adr/): domain invariants and accepted architecture.
- [Dependency policy](implementation/dependency-policy.md): supported ownership/import boundaries.

## Business and operator flows

- [Set up your business](flows/business-setup.md) and [first-loan setup](flows/first-loan-setup.md).
- [Enter, correct and withdraw metal prices](flows/metal-rate-entry.md).
- [Reassess collateral and review freshness](flows/collateral-reassessment.md).
- [Review loan health, amend monitoring limits and enable refresh](flows/loan-health-monitoring.md).
- [Choose simple or extended loan workflow](flows/loan-workflow-choice.md).
- [Browse collateral and releases](flows/collateral-and-release-browsing.md).
- [Release multiple loans](flows/multiple-loan-release.md).
- [Document layouts, exact overlays and print profiles](flows/loans-document-layout-operator-guide.md).
- [Pawn-loan financial read models](domain/pawn-loan-financial-read-models.md)
  and [regulatory/economic setup](domain/loans-regulatory-setup-and-policy.md).
- [Party](domain/party.md), [Notifications](domain/notifications.md),
  and [subscription checkout/recovery/reviews](flows/subscription-checkout.md).

## Development and operations

- [Containers, CI and runtime startup](implementation/container-and-ci.md).
- [Testing and migrations](implementation/testing-and-migrations.md).
- [Workspace operator commands](implementation/loans-operator-commands.md).
- [Action permissions](implementation/action-permission-review.md).
- [Private media](implementation/private-media-access.md).
- [Cache configuration and optional Redis](implementation/cache-configuration.md).
- [Document integrity and physical acceptance](implementation/loans-configurable-document-operations.md).

## History and interpretation

[Context snapshots](archive/context/README.md) preserve the previous long status,
memory, roadmap and obsolete current guides. [Archive](archive/README.md) contains
older app plans, migration investigations and retired Girvi/DEA/Contact material.
[Completed work](plans/completed.md) and [legacy backlog](plans/backlog.md) are
historical reference, not automatic current priorities. Old docs may still refer to
files or apps that no longer exist. Prefer the current contracts and active plan.

Keep this index curated. Run `python scripts/check_current_docs.py` after changing
current entry links; the CI check intentionally does not validate every archived
historical claim or external URL.
