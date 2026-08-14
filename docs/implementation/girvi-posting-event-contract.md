---
status: active
owner: project
updated: 2026-06-22
tags: [girvi, dea, accounting, events]
related: [../roadmaps/girvi_refactor_plan.md, ../constitution.md, ../adr/2026-05-03-girvi-businessdoc-decoupling.md]
---

# Girvi Posting Event Contract

Girvi accounting effects currently post synchronously through `apps.tenant_apps.girvi.integrations.dea_adapter`. The adapter is also the only supported contract boundary for the future outbox-backed DEA cutover.

Girvi owns loan lifecycle state, source document identity, collateral/custody state, notices, and workflow decisions. DEA owns voucher creation, posting, journal entries, period locks, reversals, idempotency enforcement for accounting records, and ledger/accounting reports.

## Contract Shape

Every Girvi posting event payload must include:

| Field | Meaning |
| --- | --- |
| `contract_version` | Versioned Girvi-to-DEA contract. Current value: `2`. |
| `event_type` / `event_key` | Canonical accounting event identity. |
| `idempotency_key` | Deterministic key: `girvi:<version>:<event_type>:<source_app>:<source_model>:<source_pk>`, unless an explicit source-document key is passed. |
| `source` | Source app, model, primary key, and expected source model class. |
| `economic_payload` | Principal, interest, party/account, date, payment/recovery/write-off values needed by DEA rules. |
| `expected_dea_rule` | The DEA posting/reversal rule that should consume the event. |
| `required_economic_fields` | Field names Girvi must supply before the event is published. |
| `posting_boundary` | Explicit Girvi-vs-DEA ownership reminder. |
| `adapter_mode` | Current runtime mode. Today: `sync_runtime_outbox_ready`. |

`payload` is kept as a compatibility alias for `economic_payload` while the paused outbox scaffolding remains in place.

## Event Types

| Event key | Event type | Source model | Expected DEA rule |
| --- | --- | --- | --- |
| `disbursal` | `DISBURSAL` | `GivenLoan` | `given_loan_disbursal` |
| `taken_loan_activation` | `TAKEN_LOAN_ACTIVATION` | `TakenLoan` | `taken_loan_activation` |
| `repayment` | `REPAYMENT` | `PaymentVoucher` | `given_loan_receipt` |
| `taken_loan_repayment` | `TAKEN_LOAN_REPAYMENT` | `PaymentVoucher` | `taken_loan_payment` |
| `release` | `RELEASE` | `Release` | `given_loan_release` |
| `accrual` | `ACCRUAL` | `LoanInterestAccrual` | `given_loan_interest_accrual` |
| `auction_recovery` | `AUCTION_RECOVERY` | `GivenLoan` | `girvi_auction_recovery` |
| `sale_recovery` | `SALE_RECOVERY` | `GivenLoan` | `girvi_sale_recovery` |
| `renewal` | `RENEWAL` | `LoanRenewal` | `girvi_renewal` |
| `write_off` | `WRITE_OFF` | `GivenLoan` | `girvi_write_off` |
| `reversal` | `REVERSAL` | `PaymentVoucher` | `dea_reversal` |

## Boundary Rules

- Girvi services must call `integrations.dea_adapter`; they must not import DEA models, posting rules, or posting engine modules directly.
- `service_modules.posting_adapter` is only a compatibility import path that re-exports the canonical adapter.
- Period-lock checks and reversal accounting must remain inside DEA.
- Girvi may validate that a loan event is allowed, but it must not create or mutate journal entries.
- Future async posting should publish the same payload shape through the Girvi outbox without changing views or workflow services.

## Read Models

`get_source_posting_status(source_document)` is the canonical Girvi read boundary for source-document accounting state. It returns:

| Field | Meaning |
| --- | --- |
| `label` | `Failed`, `Pending`, `Posted`, or `Not started`. |
| `badge_class` | Display hint for server-rendered UI. |
| `posted_payment_count` | Posted DEA payment vouchers linked to the source document. |
| `pending_payment_count` | Unposted DEA payment vouchers linked to the source document. |
| `failed_outbox_count` | Failed/dead-letter Girvi posting outbox rows. |
| `pending_outbox_count` | Pending/processing Girvi posting outbox rows. |

Loan detail readiness consumes this adapter read model. It must not query DEA models or journal rows directly.
