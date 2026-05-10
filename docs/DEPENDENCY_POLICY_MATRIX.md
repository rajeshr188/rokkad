# Dependency Policy Matrix (Tenant Apps)

Date: 2026-05-03
Status: Proposed for immediate adoption

## Decisions This Matrix Enforces

1. DEA is mandatory and central for every tenant workspace.
2. notify_v2 fully replaces notify in this quarter.
3. Financial posting uses strong eventual consistency (transactional outbox + async consumers), not synchronous cross-app posting.

## Legend

- `A` = Allowed direct code dependency (import/call/FK string ref).
- `E` = Event/Fascade only. No direct domain-model import. Use outbox events, typed service ports, or application facades.
- `L` = Legacy transitional only. Allowed temporarily with deprecation ticket and sunset date.
- `X` = Forbidden.

## App Scope

- `approval`
- `contact`
- `dea`
- `girvi`
- `notify_v2`
- `notify` (legacy)
- `product`
- `purchase`
- `rates`
- `sales`
- `terms`
- `utils` (shared helpers)

## Matrix (From -> To)

| from \\ to | approval | contact | dea | girvi | notify_v2 | notify | product | purchase | rates | sales | terms | utils |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| approval | A | A | E | E | E | X | E | E | A | E | A | A |
| contact | X | A | E | X | E | X | X | X | X | X | X | A |
| dea | X | X | A | X | E | X | X | X | X | X | X | A |
| girvi | X | A | E | A | E | L | E | X | A | X | A | A |
| notify_v2 | X | E | E | E | A | X | E | E | X | E | X | A |
| notify (legacy) | X | L | L | L | X | A | X | X | X | X | X | A |
| product | X | X | E | X | E | X | A | E | A | E | A | A |
| purchase | E | A | E | X | E | X | E | A | A | X | A | A |
| rates | X | X | X | X | X | X | X | X | A | X | X | A |
| sales | E | A | E | X | E | X | E | X | A | A | A | A |
| terms | X | X | X | X | X | X | X | X | X | X | A | A |
| utils | X | X | X | X | X | X | X | X | X | X | X | A |

## Non-Negotiable Rules

1. No domain app may import DEA domain models for posting entries.
   - Replace with `E` edge: emit business event and let DEA consumer post asynchronously.

2. DEA must not import domain app models (`girvi`, `sales`, `purchase`, `product`, `contact`).
   - DEA consumes canonical event payloads and references source metadata only.

3. notify_v2 may subscribe to domain and DEA events but should not require domain model imports for core delivery.
   - Use event payload + lightweight read adapters/projections.

4. notify (legacy) is frozen.
   - Only bugfixes under `L` edges. No new features. All new delivery/event work goes to notify_v2.

5. `utils` must stay app-agnostic.
   - No imports from tenant domain apps in `utils`.

## Layer-Level Dependency Policy (Inside Each App)

1. `models` -> same-app `models/utils/constants` only.
2. `services` -> same-app `models`, same-app `services`, and `E` edges via facade/event interfaces.
3. `views/forms/filters` -> same-app services and selected `A` read dependencies only.
4. `signals` -> same-app side effects only. Cross-app side effects must be emitted as events.
5. `management/commands` may orchestrate across apps but cannot violate `X` edges in runtime domain paths.

## Required Integration Contracts (Because DEA Is Mandatory)

All financially relevant flows must emit events with idempotency keys:

1. `loan.disbursed`
2. `loan.payment_received`
3. `loan.payment_made`
4. `loan.released`
5. `sale.invoice_issued`
6. `sale.receipt_recorded`
7. `purchase.invoice_recorded`
8. `purchase.payment_recorded`
9. `inventory.valuation_adjusted` (if accounting impact)

Minimum event envelope:

- `event_id` (UUID)
- `event_type`
- `tenant_id`
- `occurred_at`
- `producer_app`
- `aggregate_type`
- `aggregate_id`
- `idempotency_key`
- `payload` (versioned)

## Immediate Remediation Backlog (Top Priority)

> **Updated 2026-05-03** — synchronous facade pattern adopted (outbox deferred).
> All cross-app DEA imports must go through `dea/facade.py` only.

1. ~~Remove direct `girvi <-> dea` model imports~~ ✅ **DONE** — `girvi/service_modules/payment.py` uses `dea.facade` only.
2. ~~Move `contact -> dea` signal~~ ✅ **DONE** — `contact/signals.py` uses `dea.facade.ensure_customer_account`.
3. ~~Remove direct `sales -> dea` model imports~~ ✅ **DONE** — `sales/models/sale.py` and `receipt.py` use `dea.facade` only.
4. ~~Remove direct `purchase -> dea` model imports~~ ✅ **DONE** — `purchase/models/purchase.py` and `payment.py` use `dea.facade` only.
5. ~~Fix `dea/models/payment.py` reverse import of `GivenLoan`/`TakenLoan`~~ ✅ **DONE** — `source_loan` uses existing `source_document` GenericForeignKey.
6. ~~Add CI import guardrail~~ ✅ **DONE** — `scripts/check_dea_boundary.py` (exits 1 on violations, run with `--list`).
7. Remaining 25 violations to fix in subsequent PRs *(tracked by guardrail)*:
   - `girvi/models/loan.py`, `loan_refactored.py` — `BusinessDoc` inheritance + inline PaymentVoucher imports
   - `girvi/service_modules/accrual.py` — interest accrual posting (needs facade extension)
   - `girvi/views/loanpayment.py` — view calls posting engine directly
   - `girvi/views/dashboard.py`, `girvi/selectors.py` — read-only PaymentVoucher queries
   - `approval/models/` — JournalEntry GenericRelation (→ string reference)
   - `product/models/stock.py` — JournalEntry GenericRelation (→ string reference)
   - `pages/views.py` — dashboard aggregation queries
   - `orgs/.../seed_tenant_defaults.py` — admin seeding (allowlist acceptable)
   - Test files — direct posting rule imports (test-only, low risk)
8. Stop new references to `notify`; route all new notification triggers to notify_v2.

## CI Guardrails (Suggested)

1. Add import-linter rules for forbidden edges.
2. Add architecture tests that fail on `X` edges and permit only approved `A` edges.
3. Add temporary allowlist for `L` edges with expiry date.

## Governance

1. Any new `A` edge requires ADR approval.
2. `L` edges require owner, migration task, and target removal date.
3. Review this matrix every sprint until notify legacy is removed and DEA async posting is fully cut over.
