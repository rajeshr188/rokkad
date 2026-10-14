---
status: verified-locally
owner: project
updated: 2026-10-14
tags: [loans, origination, correction, monitoring, portability]
related: [../adr/2026-10-14-origination-consolidation.md, ../plans/loan-origination-consolidation-20261014.md]
---

# Complete ordinary loan origination consolidation

The approved change completes common capabilities and customer correction for
supported existing agreements. It retains PawnLoan, original approvals, source
documents, financial events, obligation schedules and history boundaries. It
adds no loan model, ledger, workflow framework or new financial calculation.

Ordinary series setup now offers **Use an existing register**. An administrator
reviews the last counter and book reference before signed confirmation. The
existing reservation service advances the counter monotonically and audits it;
it creates no placeholder loans and certifies no missing history. Under licence
A / series AA, reserve through 5000 to issue AA05001 onward, then record earlier
paper loans with their original numbers. Earlier claims do not rewind the counter;
occupied numbers cannot be reused. Preview/confirmation bind actor, Workspace,
format, limits, counter and reference, with one-hour expiry and safe identical retry.

Completed monthly servicing eligibility reads frozen interest method, partial-month
rule, quantum, repayment structure, amortisation and anniversary behavior through
ServicingContract. The entry label does not determine this capability. Genuine
current advances still need current approval. Historical admission still needs
actual source facts; opening positions retain their cutover limits. Existing
recognition adapters continue reading their original immutable evidence rather
than converting earlier postings into a new format.

Active loan detail offers **Correct loan**. Its shared customer-correction command
supports direct, recorded paper, accepted history and reviewed opening agreements.
It changes a mistaken Party selection with signed review and an immutable audit,
without replaying money or reapproving the agreement. Existing financial correction
commands retain compensation and dependency rules. Renewal, auction, funding or
inconsistent custody dependencies hold customer correction for connected review.
Drafts continue ordinary editing. Customer reassignment is not debt assignment.

Opening readers validate a genuine customer correction chain against the original
mapping; they never rewrite the opening event. New tickets, schedules and receipts
bind their identity to correction evidence. Prior issued bytes remain addressable.
Native and paper notice payloads freeze Party/correction identity; send-time loan
locking prevents delivery of an earlier customer's notice, including shared contact
addresses and equal timestamps. Approved risk preview is rechecked against identity
under the loan lock. Older notice payloads conservatively check correction time.
Borrower-bound source coverage and monitoring invalidate through existing mechanisms.

Servicing bundle **version 5** wraps a published version 1–4 financial graph with
`financial_profile` and `agreement_parties`. It changes no published row schema:
only v5 accepts BORROWER_CORRECTED LoanChangeLog events. Exact source references
cover the current and every former Party. Destination preview resolves existing
accepted Party imports, rejects missing/foreign/collapsed identities, and holds
before any loan write. Original approval/opening borrower IDs map to the original
customer; the current association and correction endpoints map separately. Original
source packets and issued bytes remain retained. Re-export and retry are supported.
Fresh business packages include those dependencies through the same exchange path.
Old loan-history profiles still refuse this evidence and direct staff to v5 or exact
Workspace recovery. Migration portability/0027 extends the existing restore guard
and refuses downgrade with v5 evidence; no new tenant-owned table is introduced.

Verification uses real direct, paper, accepted-history and opening admission paths,
restricted-role restore, exact former/current mapping and once-only interest tests.
Risk parity compares balances/exposure, DPD/maturity, current valuation/LTV,
classification, severity, flags and operational alerts at equal evidence/policy/date.
Uncertainty and unavailable earlier history remain explicit. The 246-case baseline
and 322-case wider run were followed by a passing 205-case affected confirmation
and two final HTTP/capture checks. All observed failures are resolved. Initial
integration fixes covered the document registry, version-scoped enum vocabulary,
opening identity binding and JSON mapping retry. Later failures were fixtures:
reserved range versus the concurrency fixture's maximum counter, an expired series
label assertion, later-recorded photos under a backdated export clock, old Linux-only
capture paths enabled by the QA flag, and an obsolete closing-button assertion.
The latter now checks the common closing screen and its PAPER purpose. None was
resolved by weakening financial/source/isolation validation.

Restricted-role checks cover exact two-Party restore, missing/collapsed references,
source immutability/Party retention, restored original native approval identity,
fresh package opening identity and a later funding agreement. Version-5 staging,
retry and retained-evidence downgrade refusal pass. Number reservation is tested
with real competing PostgreSQL connections. Model/system checks, migration drift,
supported-app imports, local documentation links and Git whitespace checks pass.
Eight styled captures at 1440×1000 and 390×844 show register review, correction
navigation and customer form/review without horizontal overflow or page errors.
Logs/captures remain under the ignored `.tmp/origination-consolidation-20261014`
folder. No production configuration, migration, borrower edit, bulk conversion,
commit or deployment is performed by this implementation.

The exact owner-created local `test_rokkad_origination_consolidation_20261014`
database is removed after verification. No shared/development/production database
was migrated or removed. Local logs and captures remain available for review.

Compatible web/worker readers and the normal release migrations are delivered in
the [15 October production release](origination-production-release-20261015.md).
Actual register setup and customer corrections
remain explicit business actions. New lending products require their concrete
business/calculation rules; this change broadens entry paths for supported agreements.
