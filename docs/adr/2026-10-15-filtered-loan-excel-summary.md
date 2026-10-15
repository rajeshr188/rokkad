---
status: accepted
owner: project
updated: 2026-10-15
tags: [loans, reports, party, excel]
related: [2026-08-09-loans-pilot-report-and-document-boundary.md, ../domain/pawn-loan-financial-read-models.md, ../domain/party.md]
---

# Filtered loan Excel summaries

The owner requests a reusable Excel export of the filtered loan list, with a
customer shortcut, outstanding breakdown and separate loan-age/unpaid-interest
month columns. Screen and export share the directory's validated filters,
ordering and retained-source admission checks. Export includes every matching
page and requires `data.view` plus `report.export`. It is a private, read-only
download through the existing loan-list route, also available during normal
subscription read-only access. It performs no posting, risk refresh or mutation.

Active loan amounts use the existing servicing position, including supported
eligible interest awaiting recognition. Party totals use that same read, with
Khata's existing accrued-interest summary composed separately. Principal, interest
and fees remain distinct; all three sum to outstanding. Legacy contracts retain
their recorded-debt interpretation. No financial formulas or risk definitions
are changed. Incomplete balances make the complete total unavailable; an export
can separately disclose a clearly labelled known subtotal.

Loan age means completed calendar months since the original loan date, clamping
month ends. It does not describe interest coverage. Unpaid months means **monthly
charge coverage on an oldest-first reporting convention**: apply covered interest
to the oldest charges and count positive monthly charges remaining partly or
fully unpaid. Use the agreement calculator's actual varying monthly charges,
including advance coverage, reductions and reversals; do not divide by today's
monthly charge. This is a reporting convention, not evidence that a receipt was
explicitly allocated to those months. The workbook discloses that meaning.

Supported complete recorded monthly histories and reconciled native monthly
accruals can establish that count. Aggregate opening debt, unsupported monthly
profiles and incomplete attribution remain `Unavailable`, even when the current
interest amount is known. Zero unpaid interest establishes zero unpaid months.
The export does not replay or invent pre-cutover monthly history. A positive
partial monthly charge counts as one month; this is not an interest-rate period
fraction or a delinquency classification.

Drafts/approvals have no disbursed debt. Unadmitted retained source claims keep
their own row type and unavailable current amounts and never enter debt totals.
Khata remains in its own register/export; the customer shortcut exports active
ordinary loans. Customer names/references are literal Excel text, not formulas.
The workbook has Loans and Summary sheets with numeric money and dated context.

The collateral follow-up appends an item summary (description, recorded quantity,
current custody) and separate held gross/net grams for Gold, Silver, Bronze and
Other. It uses current canonical items, with export-only bounded prefetching;
it does not reinterpret original collateral snapshots or change valuation/risk.
Held means in vault or with funding lender. Returned, auction-disposed and
renewal-transferred/reversed rows remain visible in descriptions but do not
inflate holdings. PAPER_CLOSED does not prove handover: that metal's holdings
remain unavailable. Missing gross makes the complete gross total unavailable
without hiding known net; absent evidence and undisbursed records are unavailable.
Known absent metals are zero. Item weights already represent their recorded
quantity and must not be multiplied by it. Gram cells preserve four decimals,
money keeps two, and the workbook documents the current-holdings basis.
