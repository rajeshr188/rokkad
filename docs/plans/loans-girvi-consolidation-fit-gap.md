---
status: active
owner: project
updated: 2026-08-08
tags: [loans, girvi, fit-gap, consolidation, funding-loan]
related:
  - ../adr/2026-08-08-loans-consolidation-and-girvi-retirement-evaluation.md
  - ../apps/loans/architecture-and-girvi-parity.md
  - loans-rewrite-roadmap.md
  - girvi-operational-core-rebuild.md
---

# Loans And Girvi Consolidation Fit-Gap Plan

## Goal

Determine through executable vertical slices whether Loans should become the
single operational loan platform and Girvi should be retired. Avoid both a
second application-core rebuild and an unstructured feature merge.

## Current Finding

Consolidation is favored but not yet authorized. Loans already owns the clean
PawnLoan lifecycle and most Girvi product value. The first pure-domain probe
shows that lender repledge custody fits as a separate FundingLoan aggregate
without changing PawnLoan or importing accounting.

The accepted temporary-coexistence and parity-selection ADR controls runtime
behavior until every gate in this plan passes, the pilot selects a winner, and
a later retirement ADR is accepted.

## Architectural Guardrails

1. Never add `loan_type` branches or FundingLoan-only nullable fields to
   `PawnLoan`.
2. Never make one generic repayment, lifecycle, or transition engine for both
   aggregates merely because names overlap.
3. Collateral remains owned by its originating PawnLoan. FundingLoan references
   selected items through immutable pledge evidence; it does not transfer item
   ownership.
4. Current custody derives from ordered custody evidence. A direct custody
   column may remain only as a database-protected projection.
5. One item may have at most one active funding pledge.
6. Borrower release, renewal, and recovery must fail while selected collateral
   is with a funding lender.
7. New workflows commit operational facts without requiring an accounting
   system. Accounting delivery is a later adapter and never owns balances,
   lifecycle, custody, or idempotency.
8. Port business outcomes, not Girvi classes, routes, statuses, or migration
   history.

## Fit-Gap Register

### Already Stronger In Loans

| Capability | Decision |
| --- | --- |
| Party borrower identity | Keep Loans implementation. |
| License, series, and bounded numbering | Keep Loans implementation; add approved license-document/renewal needs separately. |
| Collateral economics and policy snapshots | Keep Loans implementation. |
| Repayment, accrual, and event-folded balances | Keep Loans implementation; remove mandatory accounting availability in a separate hardening slice. |
| Partial/full release and custody evidence | Keep Loans implementation and extend lender-held blockers. |
| Renewal | Keep successor-loan implementation. |
| Notices and recovery/auction | Keep Loans implementation; finish shortfall/surplus decisions. |
| Versioned configurable documents | Keep Loans implementation and add funding document kinds. |
| Reversals and audit evidence | Keep compensating-event model. |

### Build As First-Class Loans Capabilities

| Capability | Target |
| --- | --- |
| Lender funding | Separate `FundingLoan` aggregate using lender `Party`. |
| Repledge | `FundingPledge` plus item rows linking existing PawnLoan collateral. |
| Funding custody | Immutable handoff/return events; projected current location. |
| Funding repayment | Immutable principal/interest/fee evidence and independent balance selector. |
| Funding closure | Zero balance plus every pledged item returned to branch vault. |
| Funding correction | Newest-first exact compensating events and custody restoration checks. |
| Funding documents | Funding agreement, repayment receipt, pledge handoff, return receipt, statement. |
| Lender reporting | Balance, due work, pledged inventory, returns, and Party exposure selectors. |

### Decide Before Girvi Retirement

| Girvi capability | Evaluation question |
| --- | --- |
| Bulk release and bulk servicing | Required operator workflow or removable convenience? |
| Loan split and merge | Genuine contract correction or unsafe historical mutation? |
| Storage boxes | Add explicit vault location/assignment module if physically used. |
| Physical verification | Add immutable verification session and discrepancy items if used. |
| Collateral photographs/labels | Add source-linked media and label document kind if required. |
| License documents/renewal | Add compliance evidence if required by operators/regulators. |
| Historical archives | Replace with filters and exports unless archive URLs are a real contract. |
| Detailed exports/reports | Identify statutory and daily operations reports from actual use. |
| Customer portal | Add Loans selector/facade contracts after operational core acceptance. |

## Execution Gates

### Gate A: Pure Funding Domain Probe

Status: complete on 2026-08-08. All 15 focused tests pass.

Completed proof:

- immutable, validated funding terms with principal, monthly simple interest,
   activation/maturity dates, maximum funding LTV, and currency rounding;
- a complete Draft, Active, Settlement Pending, Closed, and Cancelled lifecycle
   matrix, including reopening settlement when closure conditions no longer hold;
- multi-PawnLoan item selection;
- duplicate and active double-pledge rejection;
- active PawnLoan plus in-vault eligibility;
- lender handoff and branch return transitions;
- positive collateral valuation and funding LTV enforcement at pledge;
- partial item return only when retained collateral covers outstanding principal;
- independent activation, accrual, fee, repayment, and reversal event fold;
- funding repayment allocation in fees, interest, principal order;
- financial settlement plus complete branch-vault return for closure;
- exact newest-first financial and per-item custody corrections;
- no Django model, migration, route, runtime flag, or accounting dependency.

Gate A decision: FundingLoan fits as a separate Loans aggregate without adding
type branches to PawnLoan or sharing its accounting-coupled services. Proceed
to Gate B design. `FUNDING_LOAN_RUNTIME_SUPPORTED` remains false.

### Gate B: Persistence And Application Prototype

Status: complete on 2026-08-08. The canonical reviewed design is
`docs/implementation/funding-loan-gate-b-persistence-design.md`.

Schema slice 1 delivered:

- additive tenant models for FundingLoan sequence, aggregate, immutable terms,
   operational events, pledge/items, and return/items;
- nullable FundingPledge and FundingReturn sources on the canonical Pawn
   collateral custody stream, with synchronized model/database source checks;
- workspace numbering, event sequence/idempotency, value, ownership, and
   partial unique active-pledge constraints;
- reversible PostgreSQL guards for FundingLoan lifecycle/activation evidence,
   immutable evidence, exact newest-first financial reversals, active PawnLoan
   and vault pledge eligibility, return evidence, custody continuity, and final
   custody projection;
- eight focused persistence/guard tests, 15 pure Gate A tests, and existing
   auction/renewal/custody regression coverage;
- fresh tenant migration replay through `loans.0019` and `loans.0020` with no
   seeded FundingLoan rows.

Funding custody correction provenance is implemented through immutable
FundingPledgeReversal and FundingReturnReversal evidence. Runtime support
remains false.

Application slices 2-3 delivered:

- transaction-scoped workspace numbering with deterministic first-use
   advisory locking, row locking, no recycling, and bounded exhaustion;
- tenant-bound active-Party draft creation and idempotent draft cancellation;
- atomic multi-PawnLoan activation across terms, events, pledge evidence,
   shared custody movements, projections, and state transition;
- canonical request fingerprints, exact replay, changed-input rejection, and
   sorted lock acquisition independent of request item order;
- append-only interest accrual, fee assessment, and fee-interest-principal
   repayment allocation from the independent FundingLoan event fold;
- settlement transition, LTV-safe partial return, full return, custody
   projection, and financially/custodially gated closure;
- null outbound delivery with no DEA or standalone-accounting dependency;
- complete create-to-close, outbound rollback, and two-connection concurrent
   double-pledge tests with exactly one winner.

Correction slice 4 delivered:

- locked, idempotent, exact newest-first FundingLoan financial event reversal;
- immutable FundingPledgeReversal and FundingReturnReversal evidence;
- exact inverse custody movements on the canonical custody stream with matching
   funding correction provenance;
- atomic active-pledge membership and custody projection compensation;
- reversal-aware corrected re-return without mutating historical return rows;
- PostgreSQL guards for immutable correction evidence, matching base workflow,
   one compensating movement per item, exact inversion, latest-movement order,
   and one unreversed return per pledge item;
- focused replay/conflict, rollback, lifecycle, service, and database-bypass
   tests, with 40 FundingLoan tests plus one legacy custody regression passing.

Add only after Gate A is complete:

- `FundingLoan`, `FundingLoanTermsSnapshot`, `FundingPledge`, pledge items,
  funding repayments, custody evidence, and reversals;
- database exclusion/constraint for one active pledge per collateral item;
- locked, idempotent handlers for draft, activation, repayment, pledge, return,
  closure, and correction;
- repository/selectors for funding balance and custody;
- null accounting adapter as the default test dependency.

Do not add web routes or real accounting delivery in this gate.

Acceptance:

- one FundingLoan can atomically pledge items from several PawnLoans;
- concurrent double pledge has one winner;
- borrower release/renewal/recovery observes lender custody;
- funding repayment and closure do not query PawnLoan financial events;
- failure rolls back loan, pledge, and custody evidence together;
- tenant and workspace isolation are database-tested.

### Gate C: Operational Vertical Slice

Status: complete on 2026-08-08. FundingLoan remains an unlinked,
runtime-disabled Owner/Admin preview.

Read-only foundation delivered:

- tenant-scoped immutable list and detail projections;
- balances folded exclusively from FundingLoan operational events;
- terms, lender, active collateral, and source PawnLoan detail rows;
- a combined financial/custody timeline including correction evidence;
- non-mutating integrity findings for event sequence, activation evidence,
  event folding, pledge membership/custody projection, latest custody evidence,
  closed balance, and closed collateral;
- focused active-tenant, unknown-loan, corrected-lifecycle, clean-integrity,
  and deliberately corrupted-projection tests;
- no route, template, navigation, runtime flag, accounting query, Girvi change,
  or schema migration.

Internal read surface delivered:

- unlinked Owner/Admin-only overview and detail routes under Loans setup;
- list, event-derived balance, collateral, terms, correction timeline, and
   integrity rendering through the read selectors only;
- ordinary workspace members receive permission denied and unknown or
   cross-workspace FundingLoan identifiers return not found;
- the pages expose no forms or write actions and explicitly state that runtime
   and accounting delivery remain disabled;
- focused route, permission, render, disabled-runtime, and not-found tests pass.

Draft capture slice delivered:

- the hidden setup console offers an Owner/Admin-only create-draft action;
- the form lists only active tenant Party records as lenders;
- submission delegates to the existing transactional
   `CreateFundingLoanDraft` command, allocates the workspace FundingLoan number,
   records the real actor, and redirects to the read-only detail;
- invalid or inactive Party identifiers create no loan and consume no sequence;
- draft capture does not collect terms or collateral and does not activate,
   move custody, service balances, or emit accounting evidence;
- focused form, authorization, numbering, actor, redirect, and disabled-runtime
   tests pass.

Draft completion slice delivered:

- additive migration `loans.0026` stores mutable pre-activation terms and
   selected collateral separately from immutable activation evidence;
- the hidden Owner/Admin draft page captures principal, monthly rate,
   activation/maturity dates, maximum LTV, currency quantum, and eligible
   collateral from active PawnLoans in branch-vault custody with a current
   appraisal and no active funding pledge;
- selected values use the current Pawn collateral appraisal, and the existing
   FundingLoan terms and pledge policy validates the complete proposal before
   it is saved;
- detail renders readiness blockers, selected collateral value, and maximum
   funded amount without activating the loan or moving custody;
- draft cancellation requires a reason and records immutable actor/reason
   evidence before the state transition;
- focused service and tenant UI tests prove policy validation, failed-save
   rollback, eligibility filtering, role denial, readiness, cancellation
   evidence, zero pre-activation balances, unchanged custody, and disabled
   runtime.

Controlled activation slice delivered:

- the hidden Owner/Admin detail page requires exact `ACTIVATE` confirmation
   before lender handoff;
- `ActivateSavedFundingLoanDraft` locks and loads the saved proposal, delegates
   to the existing atomic activation handler, and therefore revalidates terms,
   LTV, active PawnLoan state, current vault custody, and active-pledge conflicts
   at execution time;
- successful activation creates immutable terms, activation event, pledge item,
   and shared custody evidence, updates custody projections, then removes the
   mutable draft inputs in the same transaction;
- stale collateral or outbound failure preserves the draft proposal and rolls
   back all activation evidence;
- detail displays the resulting lender custody evidence, while runtime,
  corrections, documents, and accounting remain disabled;
- hidden Owner/Admin repayment capture delegates allocation and replay to the
   existing transactional service, records the actor, rejects overpayment, and
   creates no duplicate event when the browser repeats the same request key;
- detail projects a financial statement solely from immutable FundingLoan
   events, including principal/interest/fee effects, reversal-aware signs,
    running balances, and actor evidence;
- hidden settlement review starts only after the event-derived balance reaches
   zero, and its detail projection separates financial settlement from custody
   completion;
- controlled returns are exposed only in settlement review, accept active
   pledged items, preserve exact request replay, append immutable return/custody
   evidence, restore branch-vault custody, and retain the operator identity;
- settlement initiation now enforces zero balance inside the locked service,
   and exact-confirmation closure recomputes both financial and custody
   readiness, records the closing actor, and is idempotent once closed.

Correction and document closeout delivered:

- detail exposes only the newest reversible non-activation financial event,
   eligible unreversed returns, and a whole-pledge reversal when its existing
   settlement and custody policy allows it;
- every correction requires effective date, reason, request key, and actor,
   delegates to the locked reversal services, appends compensating evidence,
   and preserves exact replay without mutating the original evidence;
- fixed preview PDFs cover agreement/handoff, repayment receipt, collateral
   return receipt, and the event-derived statement, each with a source-linked
   verification identifier and explicit `Operational accounting: Not posted`;
- preview PDFs create no document-issue records and do not extend configurable
   document kinds or layouts;
- the hidden create-to-close tenant workflow now proves correction replay,
   actor/reason evidence, restored statement balances, all four PDFs, role
   denial, settlement, return, and closure with runtime and accounting disabled.

Fresh migration replay cleanup also removed obsolete Girvi data-copy operations
for RepledgedLoanItem, legacy Loan to GivenLoan/TakenLoan, and LoanPayment to
draft DEA vouchers. Their migration graph nodes and schema operations remain,
already-migrated databases are unchanged, and fresh schemas no longer scan,
copy, or print counts for those retired records.

Build dedicated FundingLoan work surfaces:

- draft and lender/terms capture;
- eligible collateral selection grouped by PawnLoan;
- approval/activation and handoff receipt;
- repayment and statement;
- settlement readiness, item return, and closure;
- timeline, correction, and integrity findings.

Gate C is complete. Gate D, if authorized, should evaluate operator parity and
runtime readiness without assuming activation. Normal navigation, runtime
support, accounting delivery, persisted/configurable FundingLoan document
issuance, and Girvi changes remain outside this gate.

Acceptance: an operator completes create-to-close with accounting disabled and
cannot release borrower collateral while lender custody is active.

### Gate D: Operational Parity Decisions

Status: in progress. Owner direction on 2026-08-08 confirms that operators can
complete the core FundingLoan workflow, the current control surface is mostly
ready, only essential parity blocks the pilot, and temporary coexistence must
end with one application retired.

#### Current Readiness Assessment

| Area | Assessment | Gate D consequence |
| --- | --- | --- |
| FundingLoan lifecycle, balance, custody, correction, tenant isolation | Ready for controlled Owner/Admin pilot | Preserve Gate C commands and invariants. |
| FundingLoan discovery and routine staff operation | Partial | Do not enable runtime or normal navigation until pilot permissions and operator entry points are approved. |
| Regulatory license operations | Ready for pilot | Immutable revision evidence, renewal history, secure documents, expiry/readiness dashboard, exact PawnLoan revision links, register PDF, and origination blocking are complete. External expiry delivery stays in the OP5 Notify audit. |
| Collateral identity, photographs, labels, and QR | Ready for pilot | Immutable UUID identity, mandatory approval evidence, append-only photos, approval hashes, audited labels, and tenant-scoped QR navigation are implemented. |
| Hierarchical storage and physical verification | Ready for pilot | Required hierarchy, immutable movements, QR navigation, frozen verification scopes, immutable observations/resolutions, operational blockers, location correction, and lost-item compensation evidence are implemented. Damaged-collateral release policy remains deferred. |
| Notices | Partial | Audit existing Notify v2 intents and add only confirmed expiry and discrepancy gaps. |
| Essential reports and regulatory forms | Partial | Deliver only the essential set below from canonical selectors and document projections. |
| Accounting reconciliation | Deferred by policy | Use the null/deferred evidence pack below; do not replay or claim posting. |
| Retirement readiness | Not ready | Select a winner only after identical pilot scenarios and a separate accepted retirement ADR. |

#### Essential Parity Matrix

Classify each item as `PORT`, `REPLACE`, or `RETIRE`; no broad Girvi screen or
report-count parity is required.

| Capability | Decision | Pilot acceptance |
| --- | --- | --- |
| License documents, renewals, expiry | PORT | Versioned evidence, expiry visibility/notices, and expired-license origination block. |
| Collateral photos, item label, QR | PORT | At least one draft photo; append-only after approval; audited label print/reprint; QR opens owning item/loan. |
| Branch/Vault/Cabinet/Box/optional Slot | PORT | No skipped levels, one current location, immutable item/destination-scanned transfers. |
| Physical verification and discrepancy resolution | PORT | Frozen scope, immutable observations, blockers, and reasoned administrator resolution. |
| Active, daily disbursal/repayment, interest due, overdue, release/renewal, storage, license expiry, Party statement reports | PORT | Selector-backed filtered output with no independent balance calculations. |
| Loan ticket, repayment receipt, Form H/release memo, renewal agreement, notices, license register | PORT | Source-linked documents; required ticket/release signatures; Original/Duplicate ticket identity. |
| Bulk servicing and broad historical archives | RETIRE for first pilot | Single-record workflows and filtered exports are sufficient. Reassess only from measured operator failure. |
| Split/merge and mutable historical corrections | RETIRE | Use explicit successor/correction/reversal evidence instead. |
| Customer portal | REPLACE after winner selection | Build against the winning application's selector/facade contracts, not both ORMs. |

#### Minimum Reconciliation Evidence Pack

For every pilot scenario and both products, retain:

1. Source manifest: application owner, workspace, source identifiers, Party,
   series/license, effective dates, actor, and immutable request identity.
2. Financial fold: opening balance, every principal/interest/fee event and
   reversal, closing component balances, and zero-balance/closure proof.
3. Custody fold: every item, source PawnLoan, ordered custody/location events,
   current projection, funding pledge/return status, and unresolved blockers.
4. Document manifest: required document kind, source fingerprint, verification
   identity, issue/reprint actor and time, and expected copy/signature status.
5. Permission and isolation evidence: role used, allowed/denied actions,
   unknown/cross-workspace failures, and any administrator override evidence.
6. Accounting disposition: `DEFERRED` or `DEA`, outbox identity/status, linked
   voucher/journal identifiers only when actually posted, and explicit proof
   that deferred events were not represented as posted.
7. Exception register: validation failures, stale requests, retries, exact
   replay outcomes, correction reasons, reconciliation differences, and their
   resolution owner.
8. Backup/rollback rehearsal: backup identity, restore result, elapsed time,
   and post-restore financial/custody/document hash comparison.

Pilot acceptance requires zero unexplained financial or custody differences,
zero cross-tenant leakage, every required document traceable to its source,
and every expected accounting disposition matched exactly. Open operational
risks may remain only when explicitly accepted and unrelated to money, custody,
tenant isolation, or required regulatory evidence.

#### Winner And Retirement Decision

Run identical scenarios in Girvi and Loans. Score each application from 0-3 on
workflow completion, next-action clarity, operator time/error recovery,
document clarity, custody/location correctness, audit/correction evidence,
permission/tenant safety, and reconciliation quality. Architecture clarity,
documents, readable workflow, and ease of operation receive double weight.

An application is ineligible to win if it fails any money, custody, tenant,
required-document, backup/rollback, or unexplained-reconciliation criterion.
The owner selects the higher qualifying result; a tie triggers one focused
remediation pilot, not permanent coexistence. A separate accepted ADR must then
name the winner, stop new origination in the loser, define servicing/export or
retention for remaining records, define rollback, and only later authorize
destructive cleanup.

Classify remaining non-pilot Girvi capabilities through operator evidence:

- `PORT`: required and rebuilt in Loans;
- `REPLACE`: outcome retained through a simpler Loans workflow;
- `RETIRE`: intentionally removed with owner sign-off.

No item may disappear because it was absent from the Loans roadmap. Record
frequency, regulatory need, affected roles, documents, and failure impact.

Acceptance: all essential pilot rows pass, the reconciliation pack is complete,
the fit-gap register has no undecided production capability, and a scored pilot
result is ready for the owner's winner decision.

### Gate E: Accounting And External Contracts

Define versioned outbound events only after Gate C:

- funding activation/receipt;
- funding repayment;
- settlement/closure;
- correction/reversal.

Use the configured accounting adapter. Domain and application policies must
still pass unchanged with the null adapter. Replace external Girvi ORM imports
with Loans facade/selectors for Party history, active-loan checks, dashboard,
notifications, and period-close work.

### Gate F: Pilot And Retirement Decision

Run a selected-workspace pilot covering:

- customer PawnLoan create-to-release and create-to-recovery;
- renewal;
- FundingLoan create-to-close across multiple PawnLoans;
- custody verification and discrepancy handling;
- documents, notifications, reports, permissions, correction, integrity, and
  accounting reconciliation;
- backup and rollback rehearsal.

If the pilot passes, write a separate accepted ADR that supersedes permanent
coexistence, disables new Girvi origination, defines treatment of any remaining
records, and authorizes destructive Girvi schema removal. If it fails on a
fundamental product boundary, retain Girvi or resume its rebuild proposal with
the failure evidence.

## Explicitly Deferred

- Girvi schema or migration deletion.
- Girvi route removal.
- Copying or converting Girvi records into Loans.
- Enabling FundingLoan runtime support.
- Funding accounting payloads.
- Changing workspace module flags or navigation ownership.
- Accepting or rejecting permanent coexistence before the gates pass.

## Immediate Next Slice

Gate D is authorized and in progress. OP1 regulatory operations are complete.
OP2 collateral identity/media, OP3 hierarchical storage, and OP4 physical
verification are complete. The immediate next slices are only the confirmed
OP5 notice and OP6 report/document gaps. Do not enable
FundingLoan runtime or normal navigation until those pilot blockers and the
reconciliation pack pass.
