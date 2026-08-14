---
status: active
owner: project
updated: 2026-07-05
tags: [plans, active, girvi, dea, party, configuration]
related: [../domain/girvi.md, ../domain/accounting.md, ../domain/party.md, ../flows/dea-posting-flow.md, ../archive/girvi/GIRVI_EVENT_DRIVEN_DEA_POSTING_SPEC.md, party-rollout.md, centralized-preferences-architecture-plan.md]
---

## Future: workspace WhatsApp Cloud acceptance

The tenant-owned credential boundary is implemented. The next deferred slice is
the controlled Meta identity, template-send, authenticated-callback, and
operational-acceptance workflow documented in
`workspace-whatsapp-cloud-integration-acceptance.md`. It remains future work;
saving or enabling credentials does not constitute operational acceptance.

## Future: legacy Notify retirement

Notify v2 is the target platform, but legacy `notify` remains supported while
Girvi and historical evidence depend on it. The staged retirement gates and
restart point are documented in `legacy-notify-to-notify-v2-retirement.md`.
Deletion is not authorized until tenant reconciliation, parity, retention, and
upgrade-safety gates pass.

# Active Plan

## Girvi Event-Driven DEA Posting

The current active architecture track is to make Girvi lifecycle accounting effects explicit, reliable, and idempotent.

Current execution state (2026-06-21):

- P7 async cutover execution is explicitly paused for now.
- Existing synchronous Girvi to DEA posting remains the runtime path.
- Outbox/event scaffolding already added in Girvi is retained but not being wired further until unpaused.

Source spec:

- [Archived full spec](../archive/girvi/GIRVI_EVENT_DRIVEN_DEA_POSTING_SPEC.md)

Current direction:

- Girvi emits explicit business events for disbursal, repayment, release, renewal, auction, sale, undo, and adjustments.
- DEA owns posting rules, period-lock validation, voucher creation, voucher line creation, and journal entry creation.
- Each event/posting path needs an idempotency marker so retries do not double-post.
- Existing command/use-case services should remain the primary place for Girvi lifecycle behavior.
- Views should orchestrate requests and responses, not accounting effects.

Implementation guardrails:

- Use [DEA posting flow](../flows/dea-posting-flow.md) for ledger behavior.
- Use [Girvi loan lifecycle](../flows/girvi-loan-lifecycle.md) for domain state behavior.
- Respect [dependency policy](../implementation/dependency-policy.md).

## Party Rollout

The active Party rollout introduces `apps.tenant_apps.party` as the long-term external/internal business entity model while keeping `contact.Customer` as the compatibility bridge.

Current status:

- Phases 0-4 are complete.
- Phase 5, Girvi pilot integration for borrower/lender account resolution, is next.

Plan:

- [Party rollout plan](party-rollout.md)

## Girvi Release And Accrual Hardening

The accepted release/accrual boundary ADR is now tracked as an execution plan with ordered slices, acceptance criteria, and test gates.

Plan:

- [Girvi release and accrual hardening plan](girvi-release-accrual-hardening.md)

## Centralized Preferences Architecture

The first configuration foundation is live in `apps.configuration`, but runtime replacement, central workspace UI, migration from legacy Girvi preference keys, and audit snapshot hardening remain active follow-up work.

Plan:

- [Centralized preferences architecture plan](centralized-preferences-architecture-plan.md)
