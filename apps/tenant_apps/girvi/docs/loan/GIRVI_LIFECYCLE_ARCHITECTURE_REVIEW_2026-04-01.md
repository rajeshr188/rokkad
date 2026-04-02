# Girvi Lifecycle Architecture Review

Date: 2026-04-01
Scope: GivenLoan and TakenLoan lifecycle architecture, transition wiring, reversal safety, and domain-service patterns.

## Executive Summary

The Girvi app has moved in the right direction with explicit FSM transitions (`LoanFlow`), service orchestration (`LoanTransitionService`), selector read models, and command-style renewal service. The foundation is strong.

The main remaining gap is consistency: some lifecycle paths are still split across model `save()`, view functions, and ad-hoc operations, while only renewal is command-centric and deterministic end-to-end. This makes behavior harder to reason about under concurrency, failures, and future feature additions.

## Current Architecture (Observed)

1. Domain models:
- `GivenLoan`, `TakenLoan` inherit from `BaseLoan` and share `LoanStatus` enum.
- Financial behavior is mostly model-backed (calculated properties, payment helpers).

2. Lifecycle FSM:
- `LoanFlow` defines status transitions and transition metadata.
- Transition logs are written in `LoanChangeLog` on success.

3. Write orchestration:
- `LoanTransitionService` executes transition + accounting side-effects for common actions.
- Renewal uses command pattern (`LoanRenewalCommand`) and atomic execute flow.
- Release uses model-side orchestration in `Release.save()`.

4. Read orchestration:
- Selector layer composes cross-domain read model for loan detail tabs.

5. Accounting:
- PaymentVoucher + DEA posting rules (`record_loan_disbursal`, `record_loan_release`).
- Some transitions intentionally return warning when accounting path is missing.

## Why Flow Transitions Matter

Flow transitions are the source of truth for legal state movement. They are significant because they:

- prevent illegal state changes,
- capture audit metadata (`LoanChangeLog`),
- make reversal paths explicit,
- give deterministic behavior for APIs/UI,
- provide stable integration points for accounting events.

When transitions are bypassed or not uniformly orchestrated, invariants become implicit and fragile.

## Findings (Prioritized)

### P0 - Transition wiring drift (flow and UI/service wiring not fully synchronized)

- `LoanFlow` includes transitions that are not fully represented in `loan_transition_view` form mapping.
- Transition handling is manually wired in `form_classes`, making drift likely whenever transitions change.

Evidence:
- `apps/tenant_apps/girvi/flows.py`
- `apps/tenant_apps/girvi/views/loan.py` (`form_classes` mapping and `loan_transition_view`)
- `templates/girvi/loan/loan_detail_1.html` transition buttons depend on outgoing transition labels

Risk:
- Valid flow transitions may fail at UI/service layer with "Invalid transition".
- Future transitions can be introduced in FSM but silently unusable in UI.

### P1 - TakenLoan lifecycle is not modeled with the same rigor as GivenLoan

- GivenLoan has formal FSM + transition service.
- TakenLoan operations are largely operational (collateral methods + view logic) without a dedicated `TakenLoanFlow`/service transition policy.

Evidence:
- `apps/tenant_apps/girvi/models/loan_refactored.py` (`TakenLoan` has status field but no explicit transition graph)
- `apps/tenant_apps/girvi/views/custody_views.py` (direct create/repledge flows)
- `apps/tenant_apps/girvi/models/custody_tracking.py` (`TakenLoanCollateralMixin` contains workflow-like operations)

Risk:
- weaker determinism and reversibility for taken-loan lifecycle,
- harder permission policy enforcement and audit consistency.

### P1 - Lifecycle side-effects are split across service and model save hooks

- `Release.save()` performs transition + accounting side-effects.
- Other transitions are orchestrated through `LoanTransitionService`.

Evidence:
- `apps/tenant_apps/girvi/models/release.py` (`save()` calls flow + accounting)
- `apps/tenant_apps/girvi/services.py` (`LoanTransitionService`)

Risk:
- multiple write entry points with different behavior,
- surprise side-effects for callers using model APIs directly.

### P1 - Accounting consistency model is mixed (sync warnings vs atomic state+money semantics)

- For some transitions, status updates can succeed while accounting posting fails (warning result).
- This is operationally acceptable but not fully deterministic from accounting perspective.

Evidence:
- `apps/tenant_apps/girvi/services.py` (`_post_disbursal` warning path)
- docs already note auction/sold accounting gaps

Risk:
- temporary or permanent state/ledger divergence,
- manual reconciliation burden.

### P2 - Documentation drift from active transition model

- Lifecycle docs can lag behind flow changes and become partially incorrect.

Evidence:
- `apps/tenant_apps/girvi/docs/LOAN_LIFECYCLE_TRANSITIONS.md` state diagram and transition notes

Risk:
- implementation and runbook mismatch,
- incorrect assumptions by developers/operators.

### P2 - Service layer packaging is too broad

- `services.py` contains many unrelated concerns (ID generation, analytics, transitions, renewal).

Evidence:
- `apps/tenant_apps/girvi/services.py` (highly multi-purpose module)

Risk:
- regression risk during edits,
- difficult ownership/testing boundaries.

## Recommended Design Patterns and Improvements

### 1) Transition Command Pattern (standardize beyond renewal)

Adopt command DTO + result DTO for all state-changing actions:

- `ApproveLoanCommand`, `DisburseLoanCommand`, `ReleaseLoanCommand`, `UndoReleaseCommand`, etc.
- each command validates preconditions and executes atomically.
- normalize outcome object (`success`, `message`, `warnings`, `effects`).

Benefit:
- uniform deterministic write-path,
- easier testing and policy checks,
- less UI/service drift.

### 2) Transition Registry (single mapping source)

Create a registry that binds transition key -> form class -> command/service handler -> permission hint.

Benefit:
- eliminates scattered mapping (`flow`, `form_classes`, template special-casing),
- prevents missing wiring when adding transitions.

### 3) TakenLoanFlow parity

Introduce `TakenLoanFlow` with explicit states and reversible transitions (create/disburse/repay/close, plus collateral return steps).

Benefit:
- architecture parity with GivenLoan,
- legal transition graph for repledge/collateral operations.

### 4) Domain Events + Outbox for accounting

Emit domain events from successful transitions and process posting via reliable outbox worker.

Benefit:
- preserves deterministic state transitions while ensuring eventual posting reliability,
- retries and observability for posting failures.

### 5) Invariant guards and policy checks

Add explicit invariant checks in command layer:

- no release if collateral with lender,
- no repledge if source not disbursed,
- no delete on active/reconciled financial artifacts,
- reversal preconditions with clear operator messages.

### 6) Modular service boundaries

Split `services.py` into focused modules:

- `services/transitions.py`
- `services/renewal.py`
- `services/id_generation.py`
- `services/analytics.py`

Benefit:
- smaller blast radius,
- easier test scoping and code review.

## Hardening Roadmap

Phase 1 (short):
- Introduce transition registry and remove manual transition drift.
- Add missing transition tests (valid/invalid/reversal per state).
- Align docs with current flow behavior.

Phase 2 (medium):
- Extract command handlers for all GivenLoan transitions.
- Keep model `save()` side-effects minimal; route all lifecycle writes through commands.

Phase 3 (medium+):
- Implement `TakenLoanFlow` + `TakenLoanTransitionService`.
- Add parity tests for TakenLoan lifecycle and collateral return lifecycle.

Phase 4 (long):
- Add outbox/event-based posting and retry monitors.
- Add reconciliation dashboard for transition status vs posting status.

## Test Strategy Suggestions

- State-transition matrix tests (allowed/blocked) for every status.
- Reversal tests that verify both status and accounting artifacts.
- Concurrency tests with `select_for_update` contention.
- Property-based tests for renewal arithmetic invariants.

## Closing

Renewal architecture is a good reference implementation. The next major architecture gain will come from applying the same command-driven determinism to all GivenLoan transitions and introducing lifecycle parity for TakenLoan.

## Addendum - Transition Registry Clarification

### What it is

A transition registry is an application-layer routing table that maps a transition key to its runtime wiring:

- form class,
- handler/command entrypoint,
- endpoint availability rules,
- optional UI metadata.

### How it differs from LoanFlow

`LoanFlow` in `apps/tenant_apps/girvi/flows.py` defines legal state movement.

It answers: "Can this status move from source to target?"

A transition registry answers: "If the move is legal, how does the app execute it?"

That includes form binding and endpoint/service execution wiring.

### Why both are needed

Without a registry, transition wiring can drift across:

- flow definitions,
- view `form_classes` maps,
- template transition buttons,
- service dispatch logic.

With a registry, flow remains the domain source of truth while app wiring becomes centralized and testable.

## Phase 1 Kickoff (Started)

Implemented in this cycle:

1. Added centralized registry module:
- `apps/tenant_apps/girvi/transition_registry.py`

2. Refactored loan transition endpoint to use registry:
- `apps/tenant_apps/girvi/views/loan.py`

3. Added missing transition forms to close mapping gaps:
- `RepledgeLoanForm`
- `UndoRepledgeLoanForm`
- file: `apps/tenant_apps/girvi/forms.py`

4. Added guard tests for registry behavior:
- `apps/tenant_apps/girvi/tests/test_transition_registry.py`

Notes:
- `deliver` remains intentionally excluded from generic transition endpoint; release must continue through Release flow for custody/accounting safeguards.
- alias normalization now handles `mark sold` -> `mark_sold` to reduce label/key mismatch risk.

## Phase 2 Progress (Started)

Implemented in this cycle:

1. Extracted transition command layer:
- `apps/tenant_apps/girvi/transition_commands.py`
- `apps/tenant_apps/girvi/transition_types.py`

2. Refactored `LoanTransitionService` to delegate execution to transition command classes instead of inline transition branching.

3. Bound command classes into transition registry so application wiring now covers:
- form class
- command handler
- transition action metadata
- transition form metadata

4. Added tests for command binding/lookup:
- `apps/tenant_apps/girvi/tests/test_transition_commands.py`

Current scope of command extraction:
- `approve`
- `cancel`
- `mark_defaulted`
- `repledge`
- `disburse`
- `mark_auctioned`
- `mark_sold`
- `undo_disburse`
- `undo_release`
- `undo_repledge`

Current limitation:
- commands are extracted but still live in one module; next step is to separate command classes by domain and add direct behavior tests for each command execution path.

## Phase 2 Progress (Incremental Update)

Completed after initial extraction:

1. Moved transition command implementation into dedicated package:
- `apps/tenant_apps/girvi/transitions/commands.py`
- `apps/tenant_apps/girvi/transitions/types.py`
- `apps/tenant_apps/girvi/transitions/__init__.py`

2. Kept backward-compatible shims to avoid import breakage:
- `apps/tenant_apps/girvi/transition_commands.py` (re-export)
- `apps/tenant_apps/girvi/transition_types.py` (re-export)

3. Added behavior tests for command execution paths:
- `apps/tenant_apps/girvi/tests/test_transition_command_behaviors.py`
	- disburse success path (new voucher)
	- disburse idempotent path (existing voucher)
	- disburse rollback path (posting exception)
	- warning transition behavior (`mark_auctioned`)
	- reversal error handling (`undo_release` validation error)

Outcome:
- transition architecture is now package-structured and directly behavior-tested,
- disburse semantics are now atomic (no state transition on posting failure),
- next step is command-by-command extraction of richer domain validation into dedicated command DTOs.

### Phase 2 Typed Payload Update

Implemented:

1. Added typed transition payload DTOs:
- `apps/tenant_apps/girvi/transitions/payloads.py`

2. Transition registry now binds payload DTO class per transition and builds typed payload objects from form cleaned data.

3. `LoanTransitionService` now dispatches commands with typed payload objects rather than raw `**payload`.

4. Commands support typed payload objects while remaining backward-compatible with dict payloads.

5. Added tests validating typed payload construction and command execution with DTO payloads.

### Phase 2 Finalization Update

Completed:

1. Release lifecycle creation moved from model `save()` side-effects to explicit service orchestration:
- `apps/tenant_apps/girvi/services.py` (`ReleaseLifecycleService.create_release`)
- `apps/tenant_apps/girvi/views/release.py` (create path now calls service)
- `apps/tenant_apps/girvi/models/release.py` (save now persistence-focused)

2. Strict typed payload enforcement is now active for transition commands:
- transition commands only accept dataclass payload DTOs,
- payload construction fails fast if a transition has no configured DTO.

3. Transition compatibility shims removed:
- removed `apps/tenant_apps/girvi/transition_commands.py`
- removed `apps/tenant_apps/girvi/transition_types.py`

### Phase 2 Service Packaging Update

Completed:

1. Split broad service responsibilities into focused modules:
- `apps/tenant_apps/girvi/service_modules/release_lifecycle.py`
- `apps/tenant_apps/girvi/service_modules/id_generation.py`
- `apps/tenant_apps/girvi/service_modules/transitions.py`
- `apps/tenant_apps/girvi/service_modules/renewal.py`

2. Added package exports for stable import surface:
- `apps/tenant_apps/girvi/service_modules/__init__.py`

3. Updated `apps/tenant_apps/girvi/services.py` to act as a compatibility facade that re-exports the extracted lifecycle/ID/transition/renewal services.

Outcome:
- P2 finding "Service layer packaging is too broad" is now addressed for lifecycle-critical paths,
- service ownership and test scope are clearer,
- existing call sites importing from `services.py` remain compatible.

Phase 2 status: complete for GivenLoan transition commandization and typed payload hardening.
