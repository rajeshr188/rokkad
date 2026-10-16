---
status: accepted
owner: loans
updated: 2026-10-16
tags: [loans, financial-reads, monitoring, compatibility]
related: [2026-10-06-loan-continuation-read-boundary.md, ../plans/loan-boundary-simplification-20261016.md]
---

# Supported loan financial inputs

LS-03 promotes the existing per-calculation prepared financial reads into a
supported Loans-internal interface. Monitoring previously imported a private
exposure helper; standalone delinquency also decoded migration evidence itself.
The owner approved simplifying these boundaries without changing financial facts.

## Decision

`selectors.financial_inputs.get_pawn_loan_financial_inputs` returns frozen
`PawnLoanFinancialInputs`: scoped loan/date, recorded balance, compatible
continuation and recognition preview, active schedule, dated unpaid obligations,
operational grace and normalized principal-history metadata. It composes the
existing continuation, balance and obligation readers. It adds no calculator,
persisted balance or generic workflow engine.

`get_pawn_loan_obligation_inputs` provides the narrower recorded-balance and
obligation capability used by standalone delinquency. The full financial result
extends that same frozen obligation container. DPD must remain readable when an
interest projection is unsupported; consolidating reads must not add a forecast
requirement to an obligation calculation. Prepared full inputs also satisfy DPD,
so monitoring does not read sources twice.

Exposure, delinquency and risk accept the public `financial_inputs` keyword.
Each checks active Workspace, loan and date before using prepared data. The risk
snapshot writer uses the supported factory, retaining its source fingerprint,
locks, live evidence instant and pre-commit expiry checks. Live risk calculations
also prepare financial sources once rather than separately reading each amount.

Opening schedule lineage, correction-aware source selection and saved grace
are decoded in the input reader. Existing native/recorded/opening calculation
profiles remain inside continuation and its compatibility services. Exposure
consumes normalized principal basis and terminal-position meaning; DPD consumes
normalized obligations and grace. Neither decodes a financial-origin payload.

## Meanings and limits

Recorded debt, unrecognized economic exposure and supported collection debt are
distinct existing results. A legacy daily projection does not become collectible
interest. Unknown pre-cutover history and unknown original principal remain
unknown. Verified closed positions need no invented policy, schedule or product.
Book coverage remains optional metadata, separate from financial support.

Frozen containers are shallow: retained ORM references and compatibility preview
objects are not durable snapshots. Treat them as read-only within one calculation;
never cache them across requests or reuse them after source changes. The reader
grants no posting authority and supplies no lock. Existing atomic commands retain
all permission, chronology, source-recheck and recognition responsibilities.

No schema, exchange profile, original agreement, posting rule, interest boundary,
rounding, valuation formula or risk-snapshot version changes. This is an internal
interface: the private `_inputs` keyword/helper are replaced in all current callers.
Published HTTP reviews and portability contracts are unaffected. See the
[implementation record](../implementation/loan-boundary-ls03-20261016.md).
