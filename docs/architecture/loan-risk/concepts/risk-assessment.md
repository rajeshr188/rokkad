---
status: proposed
owner: loans
updated: 2026-08-11
tags: [loans, risk, assessment, flags]
related: [loan-exposure.md, delinquency-dpd.md, ltv-monitoring.md]
---

# Loan Risk Assessment

Risk assessment is a pure interpretation layer. Facts are calculated first;
classifications and recommended actions are derived second.

## Inputs

- contract and lifecycle facts;
- loan exposure;
- repayment obligations and DPD;
- collateral valuation and LTV; and
- resolved monitoring policy/version.

## Output

Return tenure, exposure, delinquency, performance, collateral status,
composable flags, severity, recommended action, explanations, and every source
fingerprint. A useful result says why risk is high rather than returning one
opaque status.

## Boundary

The assessment performs no writes, sends no notices, starts no auction, and
posts nothing to DEA. Application services may project the result and detect
transitions. Workflows react to committed transitions but recheck their own
legal/business eligibility before acting.

## Initial flags

- maturity within 30 days and past maturity;
- payment overdue and configured DPD thresholds;
- valuation missing or stale;
- LTV warning, breach, and critical breach;
- performance-classification change; and
- accounting-reconciliation variance.

Overall severity is derived presentation data, never contractual state.
