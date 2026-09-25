---
status: accepted
owner: project
updated: 2026-09-25
tags: [loans, collateral, origination, interest]
---

# Collateral quantity and agreed item interest

The owner requested a 75% new-row purity default, piece counts, visible interest
rates, and collateral-level interest overrides. The owner explicitly chose staff
with loan approval permission as the override authority.

- New form rows default to quantity 1 and purity 75%. Quantity is a piece count
  from 1 to 10,000. Weights, appraisal and allocated principal are totals for the
  row; quantity never multiplies financial or valuation inputs. A grouped row
  remains one collateral unit for release; separate rows support separate returns.
- Migration 0026 adds nullable quantity and interest override plus a reason on
  the existing RLS-owned collateral table. Existing quantities remain unknown;
  no historical counts, purity values or agreed interest rates are invented.
- A blank override follows existing series/licence/Workspace policy precedence.
  Explicit overrides, including 0%, require a reason and `loan.approve` at the
  service boundary. Changing or clearing an override needs the same permission.
  Ordinary draft editors may preserve an existing authorized override.
- Creation/update logs record the actor and item terms. The policy reference is
  retained alongside the actual rate. Approval freezes quantity, override/reason,
  actual monthly rate and baseline policy rate; disbursal and accrual use frozen
  evidence. Policy changes still require an unapproved draft to be reviewed/saved.
- Splits retain item quantities/overrides and require override authority for the
  new draft. Renewals retain quantities but resolve retained items against the
  successor policy; a previous loan's rate exception is not implicitly renewed.
- The existing price-preflight request also supplies policy-rate hints. It reads
  stored Workspace rates, not an external market feed. A manual recheck is useful
  after updating Rates in another tab. Browser hints never set override values.
- Loan detail prominently displays the effective monthly rate and per-item rates.
  Printed whole-rupee amounts omit `.00`, while genuine paise remain. Issued PDF
  bytes and financial values are unchanged. Quantity appears in newly generated
  ticket descriptions using approval evidence.

The existing `loan-history/1` profile preserves the agreed financial rate but
does not represent piece counts or override provenance. It remains a partial
financial history profile; do not claim that it round-trips these new fields.
Their full evidence is retained in database backups. A versioned profile extension
is tracked in the implementation plan.
