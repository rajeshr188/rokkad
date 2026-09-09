---
status: active
owner: project
updated: 2026-09-09
tags: [plans, active, retirement, girvi, contact, notify, dea, party, configuration]
related: [../domain/girvi.md, ../domain/accounting.md, ../domain/party.md, contact-girvi-legacy-notify-retirement.md, django-tenants-removal.md]
---

## Current checkpoint

Multiple-loan full release is implemented and the owner confirmed it works as
expected; see [the operator guide](../flows/multiple-loan-release.md) and validation
in [Status](../STATUS.md). The owner approved this checkpoint for commit and push,
including the future-work register. License scoping remains shelved.

The preceding checkpoint is published on `rls-mvp` in `4d15477`, including Workspace
permissions, private media and business setup. Earlier usability/photo checkpoints
are `8d70c75` and `6d27fa1`. See [current status](../STATUS.md)
for exact regression/browser evidence. Party, Loans, Notify v2 and Rates remain the
supported apps; Workspace membership, action authorization and forced PostgreSQL
RLS remain the foundation. Physical phone/camera and printer checks remain deferred.

## Current priority: SaaS access, private media and onboarding

Private business-media application work is verified (157 tests). See the
[media inventory](../implementation/private-media-access.md) for delivery boundaries
and the remaining production storage/CDN acceptance. Resumable business onboarding and single-option loan defaults are implemented and
verified (249 broad + 1 focused tests); see [the flow](../flows/business-setup.md).
Next review the live experience. License scoping is shelved as
[FW-001](future-work.md#fw-001-optional-owner-configurable-license-scope); it is not
automatically the next implementation task. It requires a fresh review and explicit
owner approval. Use [Future work](future-work.md) for newly shelved ideas.

Follow the [incremental delivery register](saas-access-media-and-onboarding.md).
The [accepted decision](../adr/2026-09-09-organization-tenant-and-license-access.md)
keeps organizations as tenants and licenses within them. License scope is optional and owner-configurable, deferred to the end and requiring
a fresh review and explicit owner approval. The earlier assigned-license rule is
not universal; current organization-wide access remains subject to action permissions.

1. Action/service fixes and AP-06 local stored grants are implemented, including
   the Owner permission editor and capability-based invitation checks. See the
   [role delivery record](workspace-role-migration.md). Keep future role presets separate.
2. Application media fixes are implemented; deployed serving verification remains
   a separate pre-production acceptance gate.
3. Resumable business setup and single-option defaults are implemented and verified.
4. Optional license scoping is parked in FW-001, with the existing SCP review
   criteria retained. Resume only when the owner chooses to revisit it.

Do not collapse these concerns into a single completion flag. Each work item has
its own acceptance evidence in the register. The entries below preserve historical
planning context and do not override the current checkpoint or accepted ADRs.

## Historical: control-plane Phase 9 app conformance

Party, Loans, Notify v2, and Rates are being converged on `WorkspaceAccess`
action-code authorization without changing domain workflows.

- [Phase 9 execution plan](control-plane-phase9-app-conformance.md)
- [Accepted contracts](../architecture/control-plane-contracts.md)

## Completed: control-plane Phase 8 contract tests

Phase 8 consolidated the accepted `CP-*` invariants into an executable CI
contract gate. Phase 9 audits Party, Loans, Notify v2, and Rates for
conformance next.

- [Phase 8 execution plan](control-plane-phase8-contract-tests.md)
- [Accepted contracts](../architecture/control-plane-contracts.md)

## Proposed: remove django-tenants

The `no-tenants` branch targets a clean development-stage replacement of
schema-per-tenant isolation with explicit Workspace ownership and PostgreSQL
RLS. The architecture remains planning-only until the proposed ADR is accepted.

- [Proposed ADR](../adr/2026-08-14-shared-schema-workspace-rls-tenancy.md)
- [Phased removal plan](django-tenants-removal.md)

## Active: retire Contact, Girvi, and legacy Notify

The target product keeps Party, Loans, Notify v2, and DEA while retiring the
legacy Contact, Girvi, and Notify applications. Execution is dependency-first:
Party replacement, external-consumer removal, Notify v2 Girvi cleanup, DEA
decoupling, physical app deletion, and finally a clean development migration
baseline/database rebuild.

- [Accepted retirement ADR](../adr/2026-08-16-retire-contact-girvi-and-legacy-notify.md)
- [Phased execution plan](contact-girvi-legacy-notify-retirement.md)

## Future: workspace WhatsApp Cloud acceptance

The tenant-owned credential boundary is implemented. The next deferred slice is
the controlled Meta identity, template-send, authenticated-callback, and
operational-acceptance workflow documented in
`workspace-whatsapp-cloud-integration-acceptance.md`. It remains future work;
saving or enabling credentials does not constitute operational acceptance.

## Future: legacy Notify retirement (absorbed by combined retirement plan)

Notify v2 is the target platform, but legacy `notify` remains supported while
Girvi and historical evidence depend on it. The staged retirement gates and
restart point are documented in `legacy-notify-to-notify-v2-retirement.md`.
Deletion is not authorized until tenant reconciliation, parity, retention, and
upgrade-safety gates pass.

# Historical active tracks pending retirement ADR

## Girvi Event-Driven DEA Posting

This track is cancelled if the proposed combined retirement ADR is accepted.
Until then, synchronous Girvi-to-DEA posting remains the runtime path and no
further event-driven investment is authorized.

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
- The prior Girvi pilot is no longer the proposed next phase. Under the combined
  retirement plan, Party becomes the complete replacement for Contact and
  Girvi-specific Party integration is removed.

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
