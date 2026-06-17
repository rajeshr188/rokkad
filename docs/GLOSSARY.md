---
status: active
owner: project
updated: 2026-06-17
tags: [glossary, domain-language]
related: [domain/accounting.md, domain/girvi.md, domain/contact.md]
---

# Glossary

- **DEA**: Double Entry Accounting app. The accounting core.
- **Business document**: Operational document such as a payment voucher, expense voucher, journal entry voucher, Girvi loan event, sale, or purchase.
- **Voucher**: Accounting-layer posting document created from a business document.
- **Voucher line**: Debit or credit line inside a voucher.
- **Journal entry**: Ledger effect produced by posting a voucher.
- **Posting rule**: Registered accounting rule that validates and posts a voucher type.
- **Period lock**: Accounting control that prevents posting into closed periods.
- **Girvi**: Pledge/loan domain handling given loans, taken loans, pledged collateral, custody, release, renewal, repayment, auction, and sale.
- **GivenLoan**: Loan given to a customer/borrower against collateral.
- **TakenLoan**: Loan taken from another lender, commonly involving repledged collateral.
- **Loan item**: Collateral item attached to a Girvi loan.
- **Pure weight**: Metal content weight after purity adjustment.
- **Current value**: Collateral valuation using current commodity/rate data.
- **Contact**: Customer, supplier, lender, borrower, staff, or other business party.
- **Workspace/company**: Tenant-scoped operating entity.
- **Rate source**: Source/master record used for commodity rate entry.
- **Facade**: Public app boundary used by other apps instead of importing internals.
- **Selector**: Read-only query/service object used to centralize cross-model reads.
- **Command/use case**: Application service that performs a business operation transactionally.
