---
status: active
owner: project
updated: 2026-06-17
tags: [status, architecture]
related: [ROADMAP.md, plans/completed.md, plans/active.md]
---

# Status

## Current Shape

Rokkad is moving toward a layered architecture:

- Domain apps own their business concepts.
- DEA owns accounting documents, vouchers, voucher lines, journal entries, posting rules, and period locking.
- Cross-app integrations should go through facades, selectors, or use-case services rather than direct model imports.
- Girvi loan operations are being moved toward command/use-case classes, with accounting effects delegated to DEA.
- Contacts are being separated from loan-specific reads through summary selectors and Girvi facades.

## Recently Stabilized

- Contact stale loan references were removed or routed behind selectors/facades.
- Girvi dashboard and loan list now target `GivenLoan` / `TakenLoan` instead of legacy loan models.
- DEA facade boundaries were split internally and protected with architecture import tests.
- Girvi introduced a facade for cross-app reads.
- Rates are exposed in navigation/dashboard paths, with visible rate-source setup.
- Girvi disbursal can self-heal missing voucher types and ensure customer accounts before posting.
- Dashboard numeric values such as pure weight and current value are formatted to two decimal places.
- Agent-facing documentation was split by purpose: root `AGENTS.md` now contains operating rules, `docs/AGENT_MEMORY.md` contains durable project context, and `docs/constitution.md` contains non-negotiable accounting principles.
- Orgs now has a centralized role policy for membership and invitation changes, named integrity constraints for workspace membership/invitations, corrected sidebar permission codenames, and dashboard reads routed through app facades/selectors.

## Known Pressure Points

- Girvi still needs one canonical lifecycle language across UI, tests, and transitions.
- Event-driven Girvi-to-DEA posting remains active work, not completed architecture.
- Some archived docs contain older naming, model shapes, and implementation assumptions.
- More cross-app reads should be audited and moved behind facades/selectors.
- Period-lock validation should remain inside the posting engine for all accounting paths.
- Orgs service extraction is started but not complete; workspace/team mutation views should continue moving toward thin request/response coordinators.

Historical assessments are preserved in [archive/root](archive/root/).
