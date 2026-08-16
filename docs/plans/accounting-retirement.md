---
status: active
owner: project
updated: 2026-08-16
tags: [plan, loans, accounting, retirement]
related: [../adr/2026-08-16-retire-accounting.md, ../constitution.md]
---

# Accounting Retirement Plan

## Target

Supported tenant business apps are Party, Loans, Notify v2, and Rates. DEA,
tenant Accounting, Standalone Accounting, Product, Terms, and tenant Utils are
retirement candidates. This plan first removes all accounting while preserving
Loans-owned operational truth.

## Phase 1 — Freeze Loans Operational Evidence

- Inventory every use of `PawnLoanAccountingEvent`, its outbox, allocation lines,
  accruals, releases, renewals, auctions, reversals, balances, and reports.
- Characterize disbursal, repayment, accrual, release, renewal, auction, and
  reversal balances without relying on DEA assertions.
- Classify fields as operational evidence, delivery-only metadata, or obsolete
  accounting terminology.
- Do not rename or delete the event spine until these tests pass.

## Phase 2 — Remove External Accounting Gates

- Remove DEA readiness checks from Loans workflows.
- Remove borrower-account setup and Party account mapping requirements.
- Remove accounting integration configuration and cutover blockers.
- Loan actions must succeed based solely on Loans domain validation.

Status: substantially complete. DEA-backed readiness, borrower-account setup,
accounting integration mode, and operational/cutover accounting setup blockers
are removed as runtime requirements. Delivery state no longer blocks normal
balances or actions, and automatic delivery requires an explicit handler.
Delete the compatibility readiness API and stale call-site scaffolding while
Phase 3 removes the remaining delivery/reconciliation implementation.

## Phase 3 — Retire Delivery And Reconciliation

- Remove DEA payloads, delivery adapter, retry dispatcher, and delivery outbox.
- Remove voucher/journal identifiers and DEA inspection.
- Remove accounting reconciliation reports and health indicators.
- Preserve operational idempotency independently of delivery state.

Status: active. Direct Loans-to-DEA imports, the delivery adapter, receivable
reconciliation selector, posting-health UI, DEA report inspection, and cutover
delivery/reconciliation checks are removed. Next remove outbox creation and
return-type coupling from lifecycle services, then remove its model/schema.

Outbox creation and retry are now removed. A non-persistent compatibility value
temporarily satisfies existing lifecycle result shapes; the next slice removes
those fields and all dormant outbox UI/model references before schema deletion.

Lifecycle result fields and supported web/document references are now removed.
The dormant outbox model can be deleted after removing residual dead report
helpers and replacing accounting-era tests with Loans-native lifecycle tests.

The outbox model/schema and delivery-status vocabulary are now deleted through
`loans.0057`. Remaining Phase 3 work is removal of dead accounting-era report
helpers and conversion/removal of mixed legacy tests that still construct
outbox/DEA evidence.

Dead report helpers and pure DEA test modules are removed. Phase 3 runtime work
is complete; mixed legacy lifecycle/UI tests remain a test-conversion task and
must retain their Loans-domain assertions.

## Phase 4 — Reframe The Loans Event Spine

- Rename or replace `PawnLoanAccountingEvent` with a Loans operational-event
  model and update related fields to operational terminology.
- Preserve frozen payloads, effective dates, fingerprints, reversal links,
  allocation ordering, and immutability guards.
- Rename document payload fields and operator messages.

Status: active. The canonical model is renamed to `PawnLoanEvent` through
`loans.0058`; runtime imports are converted and the old alias is removed. The
reverse relation is now `loan_events` through `loans.0059`, lifecycle services
call `record_loan_event`, and canonical `event_recording`/`event_payloads`
entry points are active. Their implementations have been moved into those
canonical modules and the legacy `accounting_outbox`/`dea_payloads` files are
deleted. Mixed accounting-era lifecycle tests and remaining persisted
field/operator terminology still require neutral conversion without changing
event evidence.

The ignored accounting delivery-handler signature is now removed across all
PawnLoan financial lifecycle services; Notify v2 delivery remains intentionally
separate.

The uncollectible monolithic disbursal suite is now retired. Existing focused
Loans tests preserve the main operational event/balance/allocation/reversal/
release behavior. Document layout contracts now require Loans event and
document evidence rather than accounting delivery/reference bindings.

Renewal idempotency and source/successor event ownership are now covered by a
real tenant test. Auction initiation, Notify v2 notice evidence, idempotency,
and reasoned cancellation are also covered.

The completion/reversal test is now added and passing. It covers recovery and
inverse obligation allocations, closure/reopening, and collateral disposal/
restoration entirely from Loans-owned evidence. The former auction integration
coverage gap is closed.

All nine persisted `accounting_event` relationships are renamed to `loan_event`
through `loans.0060`, with ordering and uniqueness state refreshed by `0061`.
Current runtime code and tests contain no old field references.

The always-ready readiness API is now deleted from services, exports, callers,
and tests. Interest recognition is cash-only through `loans.0062`: existing
development policy/snapshot rows are normalized to `CASH`, `ACCRUAL` is removed
from the domain contract and model choices, and the setup UI no longer exposes
a recognition-basis choice. Operational monthly accrual rows still calculate
borrower amounts due, and contractual compound capitalization remains a Loans
operation. Migration `loans.0063` removes the now-constant persisted recognition
columns. Current enum, policy, snapshot, selector, form, service, and payload
contracts contain no recognition field; historical migrations retain the old
values only until the development baseline is rebuilt.

Current Loans runtime and operational tests are also DEA-free: stale queueing
messages, the unused report `dea_inspector` argument, voucher/journal fixture
arguments, document outboxes, and integration-mode test preferences are
removed. DEA names remain only in historical migrations and retirement boundary
guards until the clean development baseline replaces that history.

The always-ready posting contract is also retired. Balance, release-readiness,
portfolio, reversal-preflight, detail-page, and document paths no longer carry
posting blockers, accounting mode, or delivery/reconciliation UI. Immutable
event ordering, settlement validation, and custody safeguards remain intact.

Risk/exposure and reporting contracts are neutralized as well. Cash receivable
basis, overdue-interpretation variance, operational integrity findings, and
correction evidence replace accounting receivable/variance, reconciliation,
delivery status, and posting-health terminology.

The accounting-era PawnLoan cutover selector/command/test surface is retired.
Party portal and merge behavior is Loans/Party-native, so all four surviving
business apps now have a clean runtime import boundary from DEA and both
accounting implementations.

## Phase 5 — Remove Party Accounting Dependencies

- Remove Party account mappings and DEA invoice/payment portal reads.
- Keep Party merge, portal, and history behavior Loans-native.
- Remove accounting setup actions and permissions from Party surfaces.

## Phase 6 — Remove Accounting Surfaces

- Remove DEA, tenant Accounting, and Standalone Accounting URLs, navigation,
  templates, commands, jobs, configuration, seeds, tests, and documentation.
- Add project-owned redirects only where a safe supported destination exists.

## Phase 7 — Development Migration Baseline

- Rewrite surviving migration histories so they never depend on or create
  accounting apps.
- Rebuild a guarded empty rehearsal database.
- Verify zero accounting tables, views, triggers, ContentTypes, and permissions.

## Phase 8 — Physical Retirement And Verification

- Delete DEA, tenant Accounting, and Standalone Accounting packages.
- Run Django checks, migration checks, focused lifecycle suites, route tests,
  full tests, and source searches.
- Update status and agent memory after every meaningful slice.

## Gates

- Loans lifecycle actions have no imports from a retiring accounting app.
- Loan balances and reversals remain deterministic from Loans-owned evidence.
- Party, Notify v2, and Rates have no accounting dependencies.
- A fresh database migrates successfully with only supported target behavior.
