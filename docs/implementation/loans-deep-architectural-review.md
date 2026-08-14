---
status: review
owner: project
updated: 2026-08-14
tags: [loans, architecture, accounting, collateral, risk, tenancy]
related: [../adr/2026-07-15-loans-rewrite-domain-and-cutover-architecture.md, ../adr/2026-08-13-loan-application-boundaries-and-monitoring.md, ../constitution.md, ../domain/pawn-loan-financial-read-models.md]
---

# Deep Architectural Review of the Loans App

## A. Executive summary

**Verdict: Sound with targeted improvements.**

The PawnLoan architecture has the right fundamental shape for production financial software: explicit aggregates, command services, immutable append-oriented evidence, event-folded balances, policy snapshots, locked numbering, custody events, risk projections, deterministic accounting events, a durable outbox, and compensating reversals. It is not a rewrite candidate.

It is not production-safe without targeted hardening. The most serious gap is that important immutability claims are enforced by services or instance `save()` methods, not consistently by PostgreSQL. A direct ORM `update()`, admin/script mistake, or future write path can rewrite disbursed loan terms, collateral facts, and `PawnLoanAccountingEvent.payload`, changing historical balances or accounting meaning. The second major gap is architectural: FundingLoan is now a supported workflow but records lender borrowing, interest, fees, repayment, and settlement without PawnLoan's DEA event/outbox/reconciliation boundary. Finally, `DEFERRED` accounting is the default and deliberately permits a full operational lifecycle without journals; that is an acceptable development mode, but not a production accounting posture.

The central answer is therefore: **the app can preserve loan, money, collateral, and accounting truth when all writes pass through the canonical PawnLoan services in DEA mode, but the database does not yet make that truth unavoidable, and FundingLoan cannot yet preserve accounting truth.**

## B. Current architecture map

```text
HTTP / HTMX / management commands
              |
              v
      Loans application services
       /       |        \
      v        v         v
 PawnLoan   FundingLoan  Operational setup/evidence
 aggregate  aggregate    products, licences, documents,
      |          |        storage, verification, notices
      |          |
      v          v
 immutable    funding events +
 accounting   pledge/return evidence
 events +         |
 outbox            +---- no accounting adapter/outbox today
      |
      v
 DEA public facade -> vouchers -> immutable journals/reversals

 Read side: event-folded balance -> obligations/exposure ->
 collateral valuation -> delinquency -> persisted risk snapshot/alerts
```

### Entities and ownership

- Regulatory/configuration: `LoanLicense`, revisions/documents, `LoanSeries`, bounded `LoanNumberSequence`, versioned products, economic/rate/fee/monitoring policies (`models/core.py:35`, `models/products.py`, `models/regulatory.py`, `models/monitoring.py`).
- Pawn aggregate: `PawnLoan`, `PawnCollateralItem`, approval/disbursal/policy snapshots, accounting events/outbox, accrual and allocation lines, releases, custody events, auctions, renewals and reversals (`models/core.py:526-2410`).
- Contract/read evidence: versioned schedules, obligations and allocations (`models/obligations.py:24-222`); appraisals (`models/appraisals.py:9`); risk snapshot/events/alerts (`models/risk.py:6-122`).
- Physical operations: collateral intake, photos/labels, hierarchical storage, verification and operational notices in their dedicated model/service modules.
- Funding aggregate: `FundingLoan`, immutable terms/events, pledge items, returns and reversals (`models/funding.py:63-680`). Funding is a separate aggregate and correctly reuses Pawn collateral identity rather than copying it.
- Party owns borrower/lender identity. Loans stores protected Party references. DEA owns accounts, vouchers, period locks, journals and accounting reversal. Notify v2 owns provider dispatch; Loans owns notice intent and frozen economic/consent evidence.

### PawnLoan lifecycle and write paths

Stored lifecycle is `DRAFT -> APPROVED -> ACTIVE -> CLOSED`, with draft/approved cancellation and approved reopening (`domain/vocabulary.py:15-79`). Overdue, maturity, DPD, LTV and risk are derived rather than overloaded into lifecycle state.

Canonical writes are service-owned: draft/approval (`services/pawn_drafts.py`, `pawn_lifecycle.py`), disbursal (`pawn_disbursal.py:48`), repayment (`pawn_repayment.py`), accrual/capitalization (`pawn_interest.py:371,503`), release (`pawn_release.py`), auction (`pawn_auctions.py:85-378`), renewal (`pawn_renewals.py:382,995`) and reversal (`pawn_reversal.py:134`). These commands use atomic transactions and generally lock the aggregate row.

### Financial read path

`get_pawn_loan_balance()` folds finalized accounting events and reversals (`selectors/balances.py:71-350`). Obligations separately represent the contractual schedule; exposure composes recorded balance, projected interest and contractual payoff (`selectors/exposure.py:53-186`). Delinquency consumes obligations, valuation consumes rates/appraisals, and live risk is persisted as a labelled snapshot (`services/risk_snapshots.py:22-207`). This separation is correct.

### Background and scheduled behavior

Tenant commands reassess risk and dispatch notices. Batch risk refresh uses `select_for_update(skip_locked=True)` and records errors rather than silently dropping them (`services/risk_snapshots.py:107-157`). Risk invalidation signals only mark a projection stale after source changes (`risk_signals.py:28-86`); they do not perform financial writes and are appropriate.

## C. What is already good

1. PawnLoan and FundingLoan are separate aggregates with different economics and custody rules.
2. Lifecycle state, financial state and risk state are deliberately distinct.
3. Financial values use `Decimal`; rates, weights, purity and currency amounts have explicit precision and useful check constraints.
4. Approval, disbursal and policy snapshots preserve contract provenance; product versions are protected.
5. Repayment order is explicit: fees, overdue interest, current interest, principal. Item-level principal allocations are persisted.
6. Full release couples exact settlement, catch-up accrual, physical-verification clearance, custody evidence and closure in one atomic command. Partial release fails closed by product decision (`services/pawn_release.py:374-384`).
7. Renewal creates a successor instead of rewriting the source contract and preserves collateral lineage.
8. Auctions have explicit initiation/start/cancel/complete/reverse operations and custody evidence; unsupported shortfall/surplus cases fail closed (`services/pawn_auctions.py:214-363`).
9. Pawn accounting events and outbox rows commit atomically; delivery is deterministic and idempotent, and DEA is accessed through its public facade (`services/accounting_outbox.py:35-151`, `integrations/dea_delivery.py:19-123`).
10. Tenant services require an active schema and filter by the current tenant workspace. Numbering and major financial commands lock concrete critical rows.
11. The test suite includes number-allocation and FundingLoan double-pledge concurrency tests (`tests/test_number_allocation.py:124-190`, `tests/test_funding_services.py:947-1061`).

## D. Critical findings / gap analysis

### Finding 1 — Core PawnLoan history is mutable outside canonical services

- **Severity:** CRITICAL
- **Category:** historical integrity / database constraints
- **Evidence:** `PawnLoan.save()` only freezes `product_version_id`; principal, rate, date, tenure, borrower, licence and series remain updateable (`models/core.py:526-661`). `PawnCollateralItem.save()` validates relationships but does not freeze economic or identity fields after approval/disbursal (`models/core.py:664-798`). `PawnLoanAccountingEvent` has no immutable `save()`/`delete()` guard or database trigger (`models/core.py:967-1020`).
- **Current behavior:** canonical services avoid destructive edits, but `QuerySet.update()`, bulk operations, scripts, shell/admin code, or a future view can bypass model validation and rewrite source facts.
- **Why it matters:** the balance selector folds event payloads. Changing a payload, principal, rate, or collateral fact changes history without a reversal and may make Loans disagree with an already-posted DEA voucher.
- **Failure scenario:** a support script corrects `principal_amount` on an ACTIVE loan; the approval/disbursal event and journal still show the old amount while screens show mixed old/new facts. Or an event payload is edited and the Loans balance changes while its stored fingerprint and DEA journal do not.
- **Recommended architecture:** add PostgreSQL immutability guards for finalized accounting events, snapshots, accrual/allocation/custody/release/renewal/auction evidence; prohibit economic PawnLoan/collateral changes after approval except through explicit append-only correction/reversal commands. Add payload-fingerprint verification to reconciliation.
- **Affected:** core models/migrations, reconciliation selectors, admin/script boundaries.
- **Difficulty:** medium-high.
- **Priority:** P0.

### Finding 2 — FundingLoan has no accounting boundary

- **Severity:** CRITICAL for production enablement; HIGH while pilot-only
- **Category:** accounting divergence
- **Evidence:** Funding services record activation, accrual, fees, repayments, reversals and closure (`services/funding_loans.py:351-1086`) into `FundingLoanEvent`; the Funding models contain no accounting event/outbox/voucher reference, and the DEA delivery adapter only supports PawnLoan transaction kinds (`integrations/dea_delivery.py:19-123`). ADR `2026-08-13-loan-application-boundaries-and-monitoring.md` declares FundingLoan supported production-domain code.
- **Current behavior:** lender payable economics and custody are auditable inside Loans, but no journal consequence, posting idempotency, period lock, accounting reversal or reconciliation is guaranteed.
- **Failure scenario:** a lender repayment closes FundingLoan operationally while liabilities and cash remain unchanged in DEA.
- **Recommended architecture:** either feature-gate all Funding financial activation/servicing as non-production, or add a Funding accounting event/outbox contract and DEA facade methods before production use. Preserve the separate aggregate.
- **Difficulty:** high.
- **Priority:** P0.

### Finding 3 — Deferred accounting permits intentional Loans/ledger divergence

- **Severity:** HIGH
- **Category:** accounting policy / deployment safety
- **Evidence:** the default integration mode is `DEFERRED`; pending events do not block subsequent operations (`adr/2026-08-08-operational-accounting-integration-deferral.md:29-48`). `assert_pawn_loan_financial_actions_allowed()` excludes PENDING in deferred mode (`services/pawn_disbursal.py:182-207`). Activation design exists, but the repository status does not show its runtime implementation complete (`adr/2026-08-09-loans-deferred-to-dea-activation.md`).
- **Current behavior:** a loan may disburse, repay, renew, release and close with all outboxes PENDING and no accounting books.
- **Failure scenario:** a workspace is treated as production while still deferred, then cannot produce source-linked journals or safely switch to DEA.
- **Recommended architecture:** make production readiness fail unless mode is DEA or a formally accepted non-accounting pilot; implement the accepted activation/coverage workflow before allowing a workspace with deferred history to switch. Display the mode and unreconciled monetary total prominently.
- **Difficulty:** medium-high.
- **Priority:** P0 deployment gate / P1 implementation.

### Finding 4 — Outbox claims can remain permanently PROCESSING

- **Severity:** HIGH
- **Category:** retry/concurrency/operations
- **Evidence:** delivery changes PENDING/FAILED to PROCESSING and rejects another worker while PROCESSING (`services/accounting_outbox.py:72-106`). There is no lease timeout, stale-claim recovery command, worker identity, or scheduled due-row dispatcher in Loans.
- **Current behavior:** caught delivery exceptions become FAILED, but process death after the PROCESSING commit/state transition can strand a blocker indefinitely. Immediate `on_commit` delivery and manual failed retry are the principal paths.
- **Failure scenario:** worker termination during DEA posting leaves PROCESSING; all later financial commands block, and operators cannot use the failed-only retry service.
- **Recommended architecture:** add a bounded processing lease, stale-claim recovery with reconciliation-before-retry, a tenant-aware due-outbox dispatcher, and attempt audit evidence. Never blindly reset a claim if DEA may already have posted; query by idempotency key first.
- **Difficulty:** medium.
- **Priority:** P0/P1.

### Finding 5 — Cross-model workspace invariants are mostly application-only

- **Severity:** HIGH
- **Category:** tenant safety / database integrity
- **Evidence:** workspace matching is commonly enforced in `clean()` (`models/core.py:603-644`, `models/obligations.py:59-75`), which bulk/update paths bypass. Tenant schema isolation limits cross-tenant rows, but `orgs.Company` references and same-schema mismatches remain possible.
- **Current behavior:** canonical services filter the current workspace; direct ORM paths can pair a loan with the wrong workspace-owned licence/product/policy/document metadata.
- **Failure scenario:** an incorrectly scoped command under the correct tenant attaches another Company row available through shared/public relations, producing misleading ownership and reports.
- **Recommended architecture:** retain schema checks in services, eliminate unscoped mutation APIs, add feasible composite database constraints/triggers for workspace consistency, and add explicit command-level tenant arguments plus multi-schema tests.
- **Difficulty:** medium.
- **Priority:** P1.

### Finding 6 — Pawn lifecycle transitions are not database-enforced

- **Severity:** HIGH
- **Category:** lifecycle integrity
- **Evidence:** transition vocabulary is pure Python (`domain/vocabulary.py:59-79`) and services assign `loan.state` directly. FundingLoan has PostgreSQL transition guards in migration `0020`; PawnLoan has no equivalent lifecycle trigger.
- **Current behavior:** services enforce valid transitions and lock loans, but `QuerySet.update(state=...)` can jump DRAFT to CLOSED or reopen CLOSED.
- **Failure scenario:** maintenance code closes a financially unsettled loan without release/custody evidence.
- **Recommended architecture:** a narrow Pawn state-transition trigger plus evidence-dependent database/service checks. Keep risk classifications out of this state.
- **Difficulty:** medium.
- **Priority:** P1.

### Finding 7 — Financial and custody concurrency testing is uneven

- **Severity:** MEDIUM
- **Category:** testing
- **Evidence:** real concurrency coverage exists for numbering and Funding double-pledge, but repayment/release, repayment/auction, renewal/repayment, duplicate outbox delivery and risk-refresh/source-change races are mainly unit/service tests or mocks.
- **Current behavior:** aggregate row locks make the design likely safe, but the PostgreSQL behavior is not broadly proven.
- **Failure scenario:** two requests enter different service paths and deadlock, return inconsistent idempotent results, or observe stale related rows.
- **Recommended architecture:** PostgreSQL `TransactionTestCase` barriers for each conflicting pair and rollback-after-DEA/readiness failures.
- **Difficulty:** medium.
- **Priority:** P1.

### Finding 8 — Compatibility fallbacks weaken snapshot certainty

- **Severity:** MEDIUM
- **Category:** source of truth / legacy
- **Evidence:** disbursal accepts older approvals without collateral economics and may resolve current policy when frozen keys are absent (`services/pawn_disbursal.py:268-345`).
- **Current behavior:** development-era records can be disbursed using current policy rather than a complete approved contract snapshot.
- **Failure scenario:** changing workspace policy changes the economics selected for an already-approved legacy loan.
- **Recommended architecture:** before production cutover, inventory these records and require reopen/reapproval; then remove the fallback for newly enabled workspaces.
- **Difficulty:** low-medium.
- **Priority:** P1.

### Finding 9 — Documentation materially disagrees with runtime

- **Severity:** MEDIUM
- **Category:** architecture governance
- **Evidence:** `docs/apps/loans/architecture-and-girvi-parity.md` still says there is no FundingLoan model and lists storage, verification, media and regulatory features as missing, while migrations 0019-0056 and current code implement them. The later 2026-08-13 ADR supersedes part of that description.
- **Current behavior:** reviewers and implementers can choose an obsolete target boundary.
- **Recommended architecture:** mark the parity document historical or refresh it from current runtime; use accepted ADRs as decisions and this review/current code as status.
- **Difficulty:** low.
- **Priority:** P2.

### Finding 10 — Auction recovery deliberately excludes common settlement outcomes

- **Severity:** MEDIUM
- **Category:** missing domain capability
- **Evidence:** completion requires proceeds to equal debt and rejects shortfall write-off and borrower surplus distribution (`services/pawn_auctions.py:214-322`).
- **Current behavior:** the safe path fails closed; money is not silently lost, but real auctions cannot always complete.
- **Recommended architecture:** add explicit surplus payable and deficiency/write-off documents, approval policy, DEA postings and reversals before broad auction use.
- **Difficulty:** high.
- **Priority:** P2/required soon.

## E–I. Domain, lifecycle, finance, collateral and risk assessment

### Source classification

- **Authoritative input:** approved borrower, licence/series, product version, principal, collateral identity/weights/purity and approved economics.
- **Historical snapshots:** approval/disbursal/policy snapshots, appraisals, accounting events, accrual/allocation lines, releases, auctions, renewals, custody/verification/document evidence.
- **Derived state:** event-folded balance, obligation state, exposure, DPD, maturity proximity, LTV and risk classification.
- **Cached projection:** `LoanRiskSnapshot`; it is explicitly current/stale/error and is invalidated by signals.
- **Ambiguous legacy cache:** `PawnCollateralItem.latest_appraised_value` coexists with versioned `CollateralAppraisal`. Current valuation uses approved appraisals, so the legacy field should not be treated as authority and needs a removal inventory.

The calculation architecture is coherent: monthly percentage rates, policy-controlled partial periods, explicit simple/compound behavior, high-precision intermediate values and currency rounding are centralized in domain/services. Accrued/recorded interest is separated from projected exposure. Repayment allocation is deterministic and persisted. Backdating and allocation overrides are deliberately unsupported, which is safer than implicit behavior.

Collateral has stable UUID identity, custody state/events, valuation evidence, photos, labels, storage, physical verification and renewal lineage. Repledging is now naturally represented through FundingPledgeItem and the active-pledge uniqueness constraint. The remaining weakness is enforceability: collateral descriptive/economic columns remain mutable after approval, and custody correctness depends on services plus selected Funding triggers rather than one uniform database policy.

Risk design is appropriately a projection, not lifecycle. Current market rates do not rewrite origination facts; live valuation and approved appraisals feed dated snapshots. NPA/performance classification is policy-driven. Stale snapshots remain visible. This architecture should be preserved.

## J. Accounting integration review

PawnLoan owns business intent; DEA owns accounting. The dependency direction is `loans -> DEA facade`, with no direct journal creation in Loans. Events/outboxes are committed with domain mutations, and posting occurs after commit using deterministic keys. Reversals append compensating events. This is the correct boundary.

Two qualifications are decisive: event immutability is not database-enforced, and operational state commits before asynchronous posting. The latter is acceptable only because failed/pending DEA delivery blocks dependent commands and reconciliation is visible. It requires stale-processing recovery and production monitoring. FundingLoan must adopt the same boundary or remain non-production.

## K. Concrete transaction requirements

Existing aggregate row locks are correctly placed around disbursal, repayment, release, renewal, auction and Funding operations. Keep those critical sections. Add tests/protection for:

- repayment vs repayment: one loan lock, distinct request keys, second allocation sees first event;
- repayment vs full release/renewal/auction: one winner proceeds, the other recalculates or fails after lock;
- release/auction vs Funding return/pledge: lock collateral rows in deterministic ID order in addition to the PawnLoan/FundingLoan row;
- outbox dispatch: claim one due row with `skip_locked`, lease expiry, reconcile by idempotency key;
- risk refresh: source fingerprint must reject publication if sources changed between calculation and persistence;
- document/sequence issuance: existing locked sequence allocation and unique constraints should remain.

## L. Tenant safety review

The app is correctly installed as a tenant app, calls `current_tenant_workspace_id()`, rejects public-schema financial operations, and scopes canonical selectors/services by workspace. Tenant commands rely on execution inside a tenant schema, which is compatible with `migrate_schemas`/tenant command orchestration.

Remaining risk is wrong-context execution, not ordinary cross-schema querying. Every scheduled runner must enumerate tenants explicitly and enter `tenant_context`; commands should fail in public schema (as core services already do). Add real two-schema tests for commands, risk batches, notice dispatch and outbox recovery. Do not cache model/queryset objects across tenant loops.

## M. Testing gap analysis

### Domain/unit

- all interest boundary dates, leap/month-end anniversaries, slab cutoffs, capitalization and rounding reconciliation;
- auction surplus/deficiency policies when introduced;
- funding accounting payloads and reversal algebra;
- unchanged historical results after policy/rate/product changes.

### Service/integration

- atomic rollback for every operation after event creation, custody mutation, schedule allocation and DEA adapter failure;
- deferred-to-DEA activation or an explicit test that production readiness rejects deferred history;
- stale PROCESSING recovery and DEA already-posted reconciliation;
- immutable-field correction workflows.

### Database invariants/concurrency

- direct `update()` attempts against finalized loan, collateral and evidence rows;
- repayment/release, repayment/renewal, repayment/auction and pawn-release/funding-custody races;
- one active pledge, one effective reversal, one lifecycle transition, and cross-workspace relation guards.

### End-to-end

- draft -> approve -> disburse -> partial repayments -> exact release -> accounting reconciliation;
- auction and reversal;
- renewal and composite reversal;
- Funding activation -> repayment -> return -> close, once accounting exists;
- two-tenant scheduled risk/outbox/notice execution.

## N. Technical debt / legacy cleanup

### Safe to remove

- Nothing proven safe solely by static review.

### Needs verification

- `PawnCollateralItem.latest_appraised_value` after confirming no writer/report treats it as authority.
- pre-itemized approval/policy fallbacks after inventorying all tenant rows.
- schema-v1/v2 document and `print_profile=legacy` paths only after configured layouts, issued artifacts and printer acceptance show no dependency.
- `domain/future_funding.py` now that the persisted Funding implementation is authoritative; compare imports/tests before removal.

### Should retain

- Girvi source ownership until an explicit retirement ADR and operational acceptance.
- Loans/DEA facade and outbox boundary.
- source-labelled coexistence, versioned products/policies/documents, snapshots, custody history, obligation/exposure/risk separation and explicit reversal evidence.

## O. Recommended target architecture

```text
Requests / tenant commands / scheduled runners
                    |
          authorized application commands
                    |
       +------------+-------------+
       |                          |
  PawnLoan aggregate        FundingLoan aggregate
       |                          |
 immutable business + accounting events (DB guarded)
       |                          |
       +------------+-------------+
                    |
             durable outbox
          lease/retry/reconcile
                    |
              DEA facade
                    |
      vouchers / journals / reversals

 append-only evidence ---> canonical selectors ---> risk projections
 collateral identity/custody --^                 --> notices/reports
```

This needs no repository layer, CQRS framework, broker, event sourcing platform or microservice. Ordinary Django services, selectors, PostgreSQL constraints/triggers and focused workers are sufficient.

## Improvement roadmap

### Phase 0 — immediate correctness and deployment gates

1. Feature-gate Funding financial workflows until accounting is implemented.
2. Prevent production readiness in DEFERRED mode unless explicitly designated as a non-accounting pilot.
3. Add reconciliation checks for mutated event payload/fingerprint and stranded PROCESSING rows.
4. Establish real PostgreSQL concurrency and rollback baselines before modifying persistence.

### Phase 1 — domain integrity

1. ADR: define finalized-field immutability and allowed correction commands.
2. Add database guards for Pawn lifecycle, accounting evidence and post-approval economic/collateral facts.
3. Add outbox leases, tenant-aware dispatch and safe stale recovery.
4. Add Funding accounting event/outbox/DEA/reconciliation vertical slice.

### Phase 2 — consolidation

1. Remove verified legacy policy/appraisal fallbacks.
2. Refresh contradictory Loans/Girvi documentation.
3. Narrow generic `ValueError` classes into a small shared set only if UI/command handling benefits; do not build an exception framework.

### Phase 3 — risk and operations

1. Implement auction surplus/deficiency with accounting.
2. Operationalize scheduled risk/outbox processing with tenant-safe observability.
3. Add performance projections only after query measurement.

### Phase 4 — hardening

Run full multi-schema, concurrency, reconciliation, printer/document and real-provider pilot gates. Add database/query profiling for portfolio reports and event folds at representative tenant volumes.

### Phase 5 — cleanup

Remove only proven unused compatibility fields/modules and retire Girvi only through its accepted decision and data-ownership process.

## Prioritized action table

| Priority | Problem | Risk | Recommended change | Effort | Dependencies |
|---|---|---|---|---|---|
| P0 | Finalized Pawn facts/events remain ORM-mutable | Silent money/history/accounting corruption | ADR + DB immutability guards + fingerprint reconciliation | M–H | Baseline invariant tests |
| P0 | Funding has no accounting integration | Lender payable/cash divergence | Gate it or implement Funding event/outbox/DEA slice | H | DEA posting contracts |
| P0 | Deferred mode can be mistaken for production accounting | Entire lifecycle without books | Production readiness gate and activation workflow | M–H | Accounting policy decision |
| P0 | PROCESSING outbox has no recovery | Permanent financial blocker or unsafe duplicate retry | Lease, reconcile, recover, audit | M | DEA lookup by idempotency key |
| P1 | Pawn lifecycle lacks DB enforcement | Invalid closure/reopening | Narrow transition/evidence triggers | M | Immutability ADR |
| P1 | Workspace consistency relies on `clean()` | Mis-scoped tenant metadata | Composite/trigger guards and multi-schema tests | M | Schema model review |
| P1 | Major race pairs lack PostgreSQL proof | Double action/deadlock/stale settlement | Barrier-based TransactionTestCases | M | Stable test DB |
| P1 | Legacy disbursal fallbacks use current policy | Historical contract drift | Inventory, reapprove, remove fallback | S–M | Tenant data inventory |
| P2 | Auction requires exact proceeds | Workflow cannot settle real surplus/shortfall | Explicit payable/write-off documents + DEA rules | H | Product/accounting policy |
| P2 | Architecture docs contradict runtime | Wrong engineering decisions | Refresh/supersede stale parity docs | S | This review |
| P3 | Event-fold/report scale is unmeasured | Future latency | Measure, then add projections only if needed | M | Representative volume |

## Architectural verdict

### Keep

Separate aggregates, service-owned commands, selector-owned reads, event-folded balances, snapshots, obligations/exposure/risk separation, custody evidence, locked numbering, DEA facade/outbox and compensating reversals.

### Fix

Database-enforced immutability, Pawn lifecycle guards, stale outbox recovery, tenant cross-model constraints, production accounting gates and concurrency proof.

### Refactor

Funding financial workflow around the same explicit accounting contract used by PawnLoan; refresh the stale architecture/status narrative.

### Add

Funding accounting events/outbox/reconciliation, outbox leasing, immutable-field correction commands, auction surplus/deficiency documents and focused database invariants.

### Remove

Only verified appraisal/policy/future-funding compatibility code after inventory. No deletion is justified by this review alone.

### Defer

Repositories, CQRS, event sourcing, brokers, microservices, broad caching, generic audit packages and generalized workflow frameworks.

## Recommended next step

Start one bounded **Loans truth-preservation hardening** phase, not a feature phase:

1. Write an ADR defining which PawnLoan, collateral and accounting-event fields become immutable at approval/disbursal and how corrections append evidence.
2. Before changing schema, add failing database tests for direct mutation plus real concurrency tests for repayment/release and repayment/renewal.
3. Add a production-readiness check that reports Funding-without-accounting, DEFERRED accounting exposure, fingerprint mismatches and stale PROCESSING outboxes.
4. Implement the smallest database guards and safe outbox recovery needed to make those tests pass.

Postpone auction shortfall/surplus, performance projections, legacy cleanup and broad UI work until this safety gate is complete. Funding accounting should be the immediately following vertical slice unless Funding remains explicitly unavailable to production operators.
