---
status: awaiting-owner-acceptance
owner: loans
updated: 2026-08-11
tags: [loans, documents, reconciliation, adoption]
related: [roadmap.md, ../../../../docs/constitution.md]
---

# Phase 11: Documents, reconciliation, and workflow adoption

Migration `0046` registers the Key Facts and Repayment Schedule document type.
The document freezes ProductVersion identity, repayment structure, schedule
fingerprint, contractual totals, maturity, and every obligation row. Its first
fixed-renderer issue is stored through the existing immutable document-issue
ledger; later requests return the exact stored artifact for that schedule
fingerprint.

The loan detail now presents contractual due/overdue, DPD, exposure,
collateral value, LTV, performance, flags, severity, explanations, and an
explicit advisory warning. It also presents a read-only Loans-versus-DEA
receivable comparison.

DEA now exposes an aggregate read facade over posted PawnLoan source vouchers.
It calculates principal and recognized-interest control-ledger balances without
allowing Loans to import DEA models. Loans compares that result with its
accounting-receivable basis and reports match, variance, or error; it never
creates or repairs accounting evidence.

Existing notice, release, renewal, collection, and auction commands retain
their current authority and recalculate their own evidence. No workflow reads
the advisory snapshot as authorization. Retirement of legacy overdue authority
remains gated on zero unexplained parity differences and explicit Owner
acceptance.

## Remaining acceptance gate

Run and accept one browser/document/accounting walkthrough for each of the four
products, including stored KFS reprint, payment/reversal, renewal or closure,
and Loans/DEA reconciliation. Apply migrations to fresh and existing tenant
schemas with `migrate_schemas`. The architecture must not be called fully
complete until those owner and environment gates pass.
