---
status: active
owner: project
updated: 2026-09-24
tags: [navigation, usability, loans]
---

# Workspace feature map

Navigation is permission-filtered; visibility does not grant access. Loan state
and approval evidence also determine available actions.

| Operator task | Entry point |
|---|---|
| Find customer or their loans | Dashboard search at the top; Work > Parties; Work > Loans search |
| All loans for one borrower | Customer > View all loans; loan heading or loan-list borrower name > All borrower loans; Loans also has a dedicated borrower name/code/phone filter |
| Create a loan | Work > New loan; selected series shows its expected number (allocated only on save) |
| Check loan date / creation time | Directly beneath the loan number on loan details; import time is separately labelled for imported loans |
| Review, approve or disburse | Draft/approved loan > Recommended next step |
| Print ticket | Approved/active loan heading > Print loan ticket |
| Interest payment, partial repayment, full release | Active loan > payment/release actions; imported openings keep their supported servicing path |
| View collateral photographs, labels, custody or appraisal | Work > Collateral; loan > Collateral and photographs |
| Print a payment receipt | Loan > Payment receipts; reversed payments keep clearly labelled original evidence |
| Read ticket/KFS or release documents | Loan > Loan documents; Release documents section link when present |
| Find release records | Work > Releases |
| Release several loans / inspect a batch | Records & reports > Release batches; loan-list tools > Release multiple loans |
| Reports and reconciliation | Records & reports > Reports > choose a report and date; record lists have 50 records per page |
| Find borrower statement | Reports > Borrower statements > search by name, code or phone |
| Whole-Workspace totals / exports | Reports > Portfolio summary / Download full reports |
| Active totals by licence or series | Reports > Active loans by licence / Active loans by series; select a table group to open its active loans |
| Collateral weights and recorded appraisal values | Reports > Collateral by metal; grouped by metal and current custody, with missing-evidence counts |
| Loans past maturity | Reports > Maturity profile; principal chart and counts in age bands |
| Loans by original year | Reports > Loans by year; state counts and active principal, with year links to the corresponding loan list |
| Imported closed-loan history | Records & reports > Historical loans |
| Metal prices | Reference & communication > Rates |
| Notification workflow | Reference & communication > Notifications |
| Business/team/billing | Settings > Business profile / Team / Billing |
| Check expiry, grace or temporary access | Workspace access banner; Settings > Billing |
| Extend or restrict commercial access | Billing > Platform access controls, platform administrators only; expiry and reason required |
| Lending rules, products, licences and numbering | Settings > Loan setup; its labelled setup navigation |
| Choose lending products | Loan setup > Products; standard drafts are prepared during Workspace creation; review and Enable for new loans only those offered |
| Combined or separate approval/disbursal | Settings > Loan workflow (owner) |
| Ticket templates and paper profiles | Settings > Documents & printing |
| Imports and portability | Settings > Data tools |

Loan details keep balances, terms, printing and next actions visible. Valuation
details, collateral and history use keyboard-operable disclosures styled with
Bootstrap cards. Collateral opens initially for drafts/approved loans; history
opens initially for closed loans. Section links and old fragment bookmarks open
the containing disclosure and focus the target. The disclosures work without JS;
the small script provides fragment navigation/focus convenience.

The former Preferences entries are retired. Existing bookmarks explain the change
and link to the real settings; they cannot save ineffective values.

September 24 validation covers desktop and 390px phone layout, mobile offcanvas
navigation, keyboard history expansion and collateral/history fragment links.
Ordinary-owner HTTP probes cover 12 pages without submitting financial actions.
This is not staff acceptance of every supported workflow or a complete accessibility
audit. Existing accepted financial rehearsal results remain separate evidence.

The staff review moves dashboard work queues above financial summaries; Business
overview links directly to analytics. Read-only customer pages keep records visible
and hide mutation controls. Their routes still enforce canonical permissions.
Operational reports now use focused selection and pagination, with searchable
borrower statements. Dates persist across pages. Full summaries and downloads
cover the complete Workspace. Integrity findings explicitly cover only the loans
checked on the current page; an empty page does not certify the whole portfolio.
