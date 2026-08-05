---
status: active
owner: project
updated: 2026-08-04
tags: [loans, girvi, rewrite, roadmap, planning]
related: [../STATUS.md, ../adr/2026-07-15-loans-rewrite-domain-and-cutover-architecture.md, ../apps/loans/architecture-and-girvi-parity.md, ../apps/girvi/README.md, ../domain/girvi.md, ../domain/accounting.md, girvi-release-accrual-hardening.md, girvi-number-sequence-migration-plan.md]
---

# Loans Rewrite Roadmap

This document is the implementation source of truth for replacing the current
`girvi` loan module with a clean side-by-side `loans` app.

The rewrite must be incremental, PR-sized, and reversible. The current `girvi`
runtime remains active until the new app proves data, workflow, accounting, and
reporting parity.

## Target

- New app: `apps.tenant_apps.loans`
- Existing app: `apps.tenant_apps.girvi` remains production runtime until explicit cutover.
- Core replacement concepts: use `PawnLoan` for customer pawn/gold loans and `FundingLoan` for lender/repledge funding loans. Do not collapse these into one over-generic `Loan` model.
- Accounting owner: DEA remains the only owner of vouchers, posting rules, journal entries, period locks, and reversals.
- Loan app responsibility: create loan-domain source documents and emit explicit accounting events or adapter calls.
- Tenant migration rule: tenant app schema changes use `migrate_schemas`.

## Non-Negotiable Boundaries

1. Do not refactor `girvi` in place as part of the rewrite foundation.
2. Do not remove or rename existing `girvi` routes during the side-by-side build.
3. Do not create journal entries directly from the new loan app.
4. Do not use signals for loan workflow side effects.
5. Do not store safely derivable statuses such as overdue, partially paid, notice sent, or partially released.
6. Do not import old Girvi models outside explicit import and parallel-validation modules.
7. Keep every step independently mergeable, testable, and reversible.

## Implementation Defaults

- Use service functions/classes for every write.
- Use selectors for dashboard, detail, balance, and report reads.
- Use `party.Party` as the borrower identity in the new app.
- Keep `PawnLoan` and `FundingLoan` explicit at model and workflow boundaries; share helpers only for genuinely common concerns such as numbering, audit, documents, and adapter payload construction.
- Use explicit adapters for DEA and notifications.
- Prefer fixed/simple PDFs in the first version over configurable Girvi-style frame templates.
- Preserve legacy Girvi as read/write production runtime until the cutover phase.

## Accepted Architecture Decisions

These decisions were clarified with the product owner on 2026-07-15 and are
the defaults for later implementation steps.

### License, Series, And Numbering

- A regulatory loan license belongs to exactly one workspace. A workspace may
  have several simultaneously active licenses.
- Existing loans remain permanently linked to their issuing license. License
  expiry blocks new drafts and disbursements, but not repayments, accruals,
  releases, reversals, reports, or document reprints for existing loans.
- An approved but undisbursed loan under an expired license must move to an
  active license/series and be approved again before disbursal.
- A license owns multiple numbering series. Each series has independent locked
  sequences for pawn loans and pawn-loan releases.
- A series never wraps or reuses numbers. At its configured maximum, allocation
  stops until the user selects or creates another series.
- The official pawn-loan number is allocated at draft creation. Cancelled drafts
  retain it, gaps are valid, and preview remains non-consuming.
- Future FundingLoans use a separate workspace-wide sequence such as
  `FL-000001`, without a regulatory license or pawn-loan series dependency.
- Staff-to-license assignment is desired future behavior, not an MVP dependency.

### Policy Scope And Loan Immutability

- Workspace preferences provide loan-policy defaults. A license may override
  selected defaults. A numbering series controls identifiers only.
- Resolved economic policy is snapshotted when the loan is disbursed.
- Drafts are editable with audit history. Approval freezes borrower, license and
  series, principal, interest policy, valuation, and collateral.
- An approved undisbursed loan may return to draft only with a reason and must
  be approved again. Disbursed economic facts require explicit reversals.

### Interest And Accounting Policy

- Interest rates are monthly. The workspace chooses simple or compound interest
  and the resolved method is snapshotted on disbursal.
- Rate changes after disbursal are forbidden for the MVP.
- Calculations retain high precision while each finalized monthly accrual row
  stores a currency-rounded recognized amount.
- Default partial-month policy charges a full month. A workspace may define a
  slab such as up to 15 days equals half a month and above 15 equals a full
  month; the resolved slab is snapshotted on disbursal.
- Compound interest capitalizes unpaid accrued interest after a configurable
  number of periods, defaulting to 12. Capitalization is an auditable event.
- A workspace chooses cash or accrual interest accounting; cash is the default.
  Cash policy recognizes interest when collected. Accrual policy posts finalized
  accrual receivable/income through DEA. The policy is snapshotted on disbursal.

### Repayment, Release, And Closure

- MVP repayments use the current business date only. Backdating is deferred.
- Default allocation order is fees and charges, overdue interest, current
  interest, then principal. Staff split override is deferred.
- Partial repayment reduces dues without returning collateral. Full release
  settles the complete loan, returns every remaining item, and closes it.
- Release and renew closes the source loan, returns selected items, transfers
  retained items, accepts optional additional collateral, and creates a newly
  numbered successor with fresh item economics.
- Net weight excludes stones/non-metal material and purity is stored per item.
  Workspace valuation policy may use calculated metal value (`current rate *
  net weight * purity`), latest staff appraisal, or the lower of both. Release
  snapshots policy, inputs, values, LTV, and settlement.
- Zero balance is closure-ready; `CLOSED` requires every item to be returned
  through a release document.
- An item held under an active FundingLoan cannot be released to its borrower.
  A future FundingLoan may contain items from multiple PawnLoans, with each
  item's pledge and return custody tracked independently.

### Reversals And DEA Delivery

- Disbursal, repayment, interest accrual/capitalization, and release require
  explicit reversal workflows. Original records are never edited or deleted.
- Dependent later events must be reversed first in reverse chronological order.
  Every reversal requires administrator permission and a mandatory reason.
- A loan event and durable accounting outbox row commit atomically. DEA posting
  is attempted immediately with a deterministic idempotency key.
- Failure leaves a visible pending/failed accounting state and blocks dependent
  financial actions until retry succeeds; it does not discard the loan event.

### Rollout And Coexistence

- Production MVP is the complete PawnLoan lifecycle: license/series setup,
  Party and collateral capture, approval/cancellation/disbursal, repayment,
  accrual, full release, release and renew, reversals, reports,
  reconciliation, and PDFs.
- Notices, auctions, renewals, FundingLoans/repledging, and portal integration
  are essential post-MVP capabilities, not abandoned scope.
- New PawnLoans may launch before FundingLoan servicing. New-app collateral
  cannot be repledged until that workflow exists.
- Legacy Girvi loans remain writable in Girvi until they close; the new app owns
  only loans created after enablement. Imported legacy data is not a second
  writable operational copy.
- One read-only aggregation layer combines both systems' dashboards/reports,
  labels record source, and sends mutations to the owning app.
- Accounting setup does not block license, series, Party, draft, or collateral
  capture. Disbursal requires an open period, funding account, borrower
  receivable, interest income, and applicable fee mappings, with actionable UI
  readiness links.

## Authoritative Execution Plan

Execute phases in order. Each numbered slice is a separate, independently
mergeable change unless two adjacent documentation-only slices are deliberately
combined. A later phase may not start until its gate passes.

### Phase 0: Architecture Baseline

#### E0.1 Accept Planning Baseline

- Keep this roadmap, the accepted architecture ADR, `docs/STATUS.md`, and
  `docs/AGENT_MEMORY.md` aligned.
- Make no Python, schema, URL, settings, or runtime changes.

Acceptance:

- The ADR is accepted and linked.
- All product decisions used by the MVP appear in this plan.
- The dependency review below has no unresolved MVP blocker.

Rollback: documentation only.

### Phase 1: Package And Pure Domain Foundation

#### E1.1 Create Empty App Skeleton — Completed 2026-07-17

- Create `apps.tenant_apps.loans` with packages for domain, models, services,
  selectors, integrations, management commands, and tests.
- Do not register the app or create models.

Acceptance: `LoansConfig` imports without database access and existing tests are
unchanged.

#### E1.2 Register Model-Free Tenant App — Completed 2026-07-17

- Add `loans` to tenant installed apps with an empty model package.
- Add app-registry and `makemigrations --check` coverage.

Acceptance: Django starts, no loans migration is generated, and Girvi behavior
is unchanged.

#### E1.3 Define Pure Domain Vocabulary — Completed 2026-07-17

- Define PawnLoan lifecycle, transaction/event kinds, custody states, document
  kinds, posting states, reversal types, and stored-versus-derived state rules.
- Keep future FundingLoan vocabulary in a clearly marked post-MVP namespace or
  compatibility mapping; do not imply runtime support.

Acceptance: pure modules import without Django/database access and transition
matrix tests cover every stored PawnLoan state.

#### E1.4 Define Policy Contracts — Completed 2026-07-17

- Define typed policy values for interest method, partial-month slab,
  capitalization interval, accounting recognition, valuation method, maximum
  LTV, and rounding.
- Define workspace-default plus license-override resolution and the immutable
  disbursal snapshot contract.

Acceptance: resolution, validation, override precedence, and snapshot
serialization are pure and test-covered.

Phase 1 gate: no schema or runtime UI exists; vocabulary and policy contracts
are stable enough to design fields without guessing.

### Phase 2: Core Schema, Setup, And Drafting

#### E2.1 Add Core Models And Tenant Migration — Completed 2026-07-17

- Add `LoanLicense`, `LoanSeries`, `LoanNumberSequence`, `PawnLoan`,
  `PawnCollateralItem`, `LoanPolicySnapshot`, and `LoanChangeLog`.
- Use `party.Party` for the borrower.
- Add workspace/license/series ownership, expiry, activation, uniqueness, and
  tenant-safe constraints.
- Do not add FundingLoan, repayment, accrual, release, or outbox models yet.

Acceptance: tenant migrations apply with `migrate_schemas`; constraints and
cross-workspace rejection are tested; no runtime route uses the models.

#### E2.2 Implement License And Series Services — Completed 2026-07-17

- Add service-owned create/update/activate/expire operations.
- Keep expired licenses readable and block new issuance.
- Audit guarded sequence configuration changes.

Acceptance: multiple active licenses per workspace work; license/series cannot
cross workspaces; expiry rules match the ADR.

#### E2.3 Implement Locked Number Allocation — Completed 2026-07-17

- Add non-consuming preview and atomic allocation for pawn loan and release
  sequences.
- Allocate the official loan number during draft creation.
- Preserve gaps and fail closed at the configured maximum.

Acceptance: concurrency, uniqueness, cancellation gaps, non-reuse, and maximum
exhaustion are tested.

#### E2.4 Add License/Series Setup UI — Completed 2026-07-17

- Add permission-gated list, detail, create, update, expiry, and series setup.
- Show active/exhausted/expired readiness and the next non-consuming preview.

Acceptance: a workspace owner can complete regulatory setup without admin-site
access; unauthorized and cross-workspace access fail closed.

#### E2.5 Implement PawnLoan Draft Service — Completed 2026-07-18

- Create the draft, number, borrower link, valuation inputs, and collateral in
  one transaction.
- Keep drafts editable through services and audit every economic/collateral edit.

Acceptance: invalid Party, license, series, principal, purity, weight, or
collateral fails atomically; number allocation never produces duplicates.

#### E2.6 Add Draft/List/Detail UI — Completed 2026-07-18

- Expose internal feature-hidden list, create, edit, and detail screens.
- Show setup blockers and a clear primary next action.

Acceptance: staff can create and correct a draft without entering an incomplete
lifecycle; Girvi navigation remains primary.

#### E2.7 Implement Approval, Reopen, And Cancellation — Completed 2026-07-18

- Approve `DRAFT -> APPROVED`; return approved/undisbursed loans to draft only
  with a reason; cancel draft/approved loans with a reason.
- Freeze the approved economic payload and require reapproval after reopening or
  expired-license transfer.

Acceptance: transition matrix, immutable approval snapshot, audit trail, and
invalid transitions are tested.

Phase 2 gate — **Passed 2026-07-18**: a user can complete license/series setup
and create, edit, approve, reopen, and cancel loans without accounting or
production navigation changes.

### Phase 3: DEA Delivery And Financial Servicing

#### E3.1 Add Durable Accounting Outbox — Completed 2026-07-30

- Add a loan accounting-event source record and outbox delivery record with
  deterministic idempotency key, payload fingerprint, attempts, status, error,
  and DEA references.
- Provide service-owned immediate delivery and permission-gated retry.

Acceptance: domain event plus outbox commit atomically; repeated delivery cannot
duplicate DEA effects; failure remains observable and retryable.

#### E3.2 Define And Implement DEA Adapter Contracts — Completed 2026-08-03

- Implement PawnLoan payloads for disbursal, repayment, accrual,
  capitalization, release receipt, and reversal.
- Resolve accounts by Party role and purpose through the DEA facade.
- Keep period locking and voucher/journal creation inside DEA.

Acceptance: every payload has source identity, effective date, economic values,
fingerprint, and idempotency key; direct DEA model/posting imports are guarded.

#### E3.3 Add Accounting Readiness Selector — Completed 2026-08-03

- Check open period, funding cash/bank account, borrower receivable mapping,
  interest-income mapping, and applicable fee mappings.
- Return actionable missing-setup links.

Acceptance: drafting remains available when incomplete; disbursal fails closed
with precise blockers.

#### E3.4 Implement Disbursal — Completed 2026-08-03

- Add transaction/source records, resolve and persist the policy snapshot, move
  `APPROVED -> ACTIVE`, and enqueue `PAWN_LOAN_DISBURSED` atomically.
- Attempt immediate posting and block dependent financial actions while pending
  or failed.
- Deliver disbursal through the public DEA facade to a dedicated
  `PAWN_LOAN_DISBURSAL` posting rule; the DEA voucher remains linked to the
  immutable loan accounting event and repeated delivery reuses the same effect.

Acceptance: disbursal is once-only; expired-license and readiness failures are
blocked; retry is idempotent; accounting and operational state reconcile.

#### E3.5 Implement Balance And Settlement Selectors — Completed 2026-08-03

- Centralize principal, fees, paid/unpaid interest, total due, overdue, closure
  readiness, and posting readiness.

Acceptance: no view or later service duplicates balance math; representative
simple/compound and cash/accrual cases are covered.

#### E3.6 Implement Repayment — Completed 2026-08-03

- Use current business date and allocate fees, overdue interest, current
  interest, then principal.
- Persist the split and enqueue repayment accounting atomically.
- Never release collateral automatically.

Acceptance: overpayment fails or is explicitly represented; duplicate submit is
idempotent; pending posting blocks dependent events; balances reconcile.

#### E3.7 Implement Accrual And Capitalization — Completed 2026-08-03

- Preview and finalize high-precision monthly periods with rounded accrual rows.
- Under accrual policy, enqueue DEA accrual posting; under cash policy, retain
  operational accruals and recognize income on collection.
- Create explicit capitalization events at the snapshotted interval.

Acceptance: period generation, partial-month slabs, rounding, simple/compound
behavior, cash/accrual behavior, and idempotency are covered.

#### E3.8 Implement Reversal Foundation — Completed 2026-08-03

- Add administrator-only, reason-required reversal source records and services
  for disbursal, repayment, accrual, and capitalization.
- Enforce newest-first dependency reversal and enqueue compensating DEA events.

Acceptance: originals remain immutable; blocked dependency order and successful
domain/accounting restoration are integration-tested.

Phase 3 gate: disbursal, repayment, accrual/capitalization, retry, and their
reversals reconcile with DEA under failure and duplicate-delivery tests.

### Phase 4: Release, Custody, And Closure

#### E4.1 Implement Valuation And Release Readiness — Completed 2026-08-03

- Resolve calculated metal value, latest appraisal, or lower-of-both policy.
- Calculate partial-release minimum settlement from fees/interest plus the
  principal reduction required by retained-collateral maximum LTV.
- Reject lender-held collateral.

Acceptance: purity/net-weight/rate/appraisal snapshots and LTV boundary cases are
test-covered.

#### E4.2 Add Release Models And Full Release — Completed 2026-08-03

- Add release/header items and custody history.
- Run catch-up accrual integrity, collect final settlement when needed, transfer
  all custody, and close only after every item is returned.
- Commit release and accounting outbox work atomically.

Acceptance: release fails closed on settlement, accrual, custody, or posting
preconditions; zero balance alone never closes a loan.

#### E4.3 Implement Partial Release — Superseded 2026-08-05

- Release selected items after the calculated minimum settlement succeeds.
- Keep the loan active and derive partial-release state from custody.

Acceptance: retained collateral remains within LTV policy and released items
cannot be released twice.

Superseded on 2026-08-05: this implemented path is historical only. ADR
`2026-08-05-pawn-loan-release-and-renew-only.md` prohibits new same-loan partial
collateral releases and replaces it with release and renew.

#### E4.4 Implement Release Reversal — Completed 2026-08-03

- Add administrator-only reverse-order release reversal with custody restoration
  and compensating DEA events.
- Reject reversal when later dependent events or incompatible physical custody
  facts exist.

Acceptance: original release remains immutable and custody/accounting/lifecycle
return to a reconciled state.

Phase 4's original gate passed on 2026-08-03. Its partial-release capability was
later superseded; full release, closure, catch-up accrual, custody, and reversal
infrastructure remain active.

### Phase 5: Complete Staff MVP And Operational Proof

#### E5.1 Add Controlled Lifecycle UI — Completed 2026-08-03

- Add approval/reopen/cancel, disbursal, repayment, accrual, full release,
  release and renew, retry, and reversal screens with permissions and primary-next-action
  guidance.
- Surface setup and pending-accounting blockers directly.

Acceptance: a representative staff user can traverse the complete lifecycle
without admin-site or manual database intervention.

Result: the feature-hidden staff detail now recommends the next valid action and
links every implemented lifecycle command: approval/reopen/cancel, disbursal,
repayment, accrual/capitalization, full release, two-step partial-release quote
and confirmation, failed-posting retry, and administrator reversal. Current
balances, custody, setup failures, accrual availability, release-readiness
blockers, and pending/failed accounting are visible on the workflow screens.

#### E5.2 Add Reports And Reconciliation — Completed 2026-08-03

- Add active, due/overdue, accrual, repayment, release, custody, posting-health,
  and accounting-reconciliation reports from selectors.

Acceptance: missing/failed/duplicate accounting, impossible custody, and
balance-voucher mismatches are categorized and actionable.

Result: a tenant-scoped report selector and feature-hidden staff report now
cover active/due/overdue balances, finalized accruals, repayments, releases,
collateral custody, and outbox posting health. Reconciliation categorizes
missing or failed delivery records, duplicate source intent or DEA documents,
source/outbox drift, invalid DEA references, source-link and journal-link
mismatches, unbalanced/non-final vouchers, source-total versus voucher-total
drift, impossible custody, and closed-loan inconsistencies. DEA evidence is
read only through its public facade, and every finding links back to its loan
with a corrective action; eligible failed deliveries expose controlled retry.

#### E5.3 Add Essential PDFs — Completed 2026-08-03

- Add fixed loan ticket, repayment receipt, and release memo/Form H equivalent.

Acceptance: documents contain stable source IDs, workspace/license identity,
amount splits, and verification fixtures.

Result: workspace-scoped PDF routes and one document service generate the fixed
loan ticket, repayment receipt, and release memo/Form H equivalent. The ticket
refuses editable drafts and reads economics/collateral from the latest immutable
approval snapshot. Receipts read immutable repayment-event splits; release
memos read immutable release headers and item valuation snapshots. Every PDF
contains workspace, regulatory license, loan and source-record IDs, source
fingerprints, relevant accounting/reversal state, amount splits, signatures,
and a deterministic verification ID also returned as a response header.

#### E5.4 Add Operations Diagnostics And Runbook — Completed 2026-08-03

- Add permission-gated outbox health/retry, series readiness, accounting setup,
  recent reversals, and audit visibility.
- Document tenant migration, enablement, rollback, reconciliation, and support.

Acceptance: operators can diagnose every known blocked state without shell or
database access.

Result: Owner/Admin users have a tenant-scoped operations console for outbox
counts, failed-event retry, stale processing claims, regulatory sequence
readiness, serviceable-loan accounting prerequisites, recent reversals, and
lifecycle audit evidence. A linked in-product guide and the canonical
operations runbook document tenant-aware deployment, hidden-MVP enablement,
rollback, reconciliation, and support procedures. The focused nine-test setup
and diagnostics suite passes without a Loans schema change.

#### E5.5 Run MVP End-To-End And Tenant-Isolation Suite — Completed 2026-08-03

- Cover setup through closure for simple/compound and cash/accrual policies,
  posting failure/retry, every reversal, partial release, expired license,
  sequence exhaustion, and cross-workspace denial.

Acceptance: the full suite passes using tenant-aware migrations and real DEA
posting fixtures.

Result: the complete 134-test Loans suite passes while provisioning isolated
tenant schemas and exercising real DEA posting fixtures. Together the gate
covers setup through closure for cash/accrual and simple/compound policies,
failed delivery and retry, disbursal/repayment/accrual/capitalization/release
reversals, partial then full release, expired licenses, exhausted sequences,
and cross-workspace denial. The gate corrected the registered-model inventory
and made release PDFs represent operational events that legitimately require
no accounting outbox.

Post-gate usability hardening: the borrower-receivable readiness blocker now
links Owner/Admin users to an idempotent setup workflow that composes the Party
compatibility bridge with DEA's public account resolver. It creates no posting
effect and removes the need for Django admin or database access before
disbursement.

Phase 5 gate: **passed 2026-08-03.** The PawnLoan MVP is operationally complete
but still hidden from production navigation.

### Phase 6: Girvi Coexistence And Controlled Cutover

The durable architecture comparison and missing-work inventory is maintained in
[Loans Architecture And Girvi Parity Review](../apps/loans/architecture-and-girvi-parity.md).
Its P0 items are Phase 6 cutover requirements. Its P1 items are essential
post-MVP vertical slices. Every P2 parity item must be implemented or explicitly
rejected through a recorded product decision before Girvi retirement; it must
not disappear merely because it was outside the PawnLoan MVP gate.

#### E6.1 Add Unified Read Contracts — Completed 2026-08-04

- Aggregate Girvi and Loans dashboards/reports without dual writes.
- Label source system and provide owner-app action URLs.

Acceptance: totals reconcile to each source and no Loans mutation is offered for
a Girvi-owned loan or vice versa.

Result: Girvi now exposes stable read-only GivenLoan and TakenLoan coexistence
rows through its public facade. Loans adapts those rows beside tenant-scoped
PawnLoans into one immutable source-labelled contract with explicit product
kind, lifecycle bucket, financial availability, custody summary, source key,
per-source totals, and owner-app action identity/URL. Contract validation rejects
rows whose action namespace does not match their owner. A feature-hidden
read-only portfolio renders both sources and links each record only to its
owning app. Four focused contract/tenant/UI tests pass, and the complete
140-test Loans suite passes with tenant-aware migrations and real DEA fixtures.
No migration is required.

#### E6.2 Add Read-Only Comparison Command — Completed 2026-08-04

- Compare counts, active/closed totals, principal, interest, balances, custody,
  release, and DEA visibility.
- Optional historical snapshots must remain immutable validation artifacts.

Acceptance: deterministic zero-mismatch fixtures and categorized deliberate
mismatches are covered.

Result: the tenant-only `compare_loan_coexistence` command now compares the
source-owned Girvi and Loans projections with the unified coexistence contract
without writing either system. Its deterministic report covers row and
active/closed/pending/cancelled counts, original and outstanding principal,
interest and total due, collateral and custody summaries, release state, and
DEA-reference visibility. Mismatches are categorized as count, lifecycle,
money, custody, release, or DEA visibility and include the affected source key
when record-level evidence exists. Text and machine-readable JSON output are
available, and `--fail-on-mismatch` turns the same read-only check into a
deployment/pilot gate. Matching and deliberately altered fixtures plus a real
tenant Girvi/Loans command run are covered by seven focused tests. The complete
143-test tenant-aware Loans suite passes; Django checks, migration drift, and
whitespace checks are clean, and no migration is required.
Historical validation snapshots remain optional and were not introduced.

#### E6.3 Add Workspace Feature Gate And Pilot — Completed 2026-08-04

- When disabled, preserve current Girvi behavior.
- When enabled, route new-loan creation to Loans, prevent new Girvi loans, and
  retain Girvi servicing for its existing active loans.

Acceptance: flag rollback restores navigation without losing new Loans records;
ownership rules cannot be bypassed by direct URL.

Result: the central audited workspace preference
`loan__new_module_enabled` now controls new-pawn-loan ownership and defaults to
Girvi. Owner/Admin users manage it through `/loans/setup/cutover/`. Enabling it
routes the canonical workspace Loans entry and all known new-loan links to
Loans, exposes Legacy Girvi for continued servicing, and guards Girvi create,
customer-create, preview, GET, POST, and HTMX entrypoints with a server-side
redirect to Loans. Customer-originated links preserve the shared Party when
available. Disabling the flag restores Girvi navigation and origination without
deleting, migrating, or changing ownership of any PawnLoan record. The setting
is tenant-bound and audited; non-administrators cannot change it through the
direct URL. Five focused tenant tests cover enable, disable, retained records,
canonical routing, direct Girvi blocking, Party handoff, coexistence navigation,
and administration denial. No migration is required.
The complete 148-test tenant-aware Loans suite passes, together with central
preference tests, route/navigation intent checks, Django checks, migration-drift,
compile, and whitespace checks.

#### E6.4 Complete Production Hardening — Engineering Gate Implemented 2026-08-04; Live Sign-Off Pending

- Run tenant migration checks, reconciliation, support rehearsal, permissions,
  monitoring, backup/rollback checks, and pilot acceptance with a real workflow.

Acceptance: explicit go/no-go checklist is signed off and no unexplained
reconciliation mismatch remains.

Result so far: tenant command `check_pawn_loan_cutover_readiness` combines six
automated gates—Loans migrations, numbering, outbox/stale delivery, accounting
setup, Loans-to-DEA reconciliation, and Girvi/Loans comparison—with six explicit
manual acknowledgements for backup, rollback, support, monitoring, permissions,
and real pilot acceptance. `--fail-on-blocker` makes NO-GO enforceable in
deployment; JSON output is retainable evidence. Five pure/command tests prove
all checks fail closed and that GO requires every acknowledgement. Local `jcl1`
passes every automated check with zero unexplained reconciliation mismatch;
`jsk` and `test` correctly block on missing numbering. A reconciliation
hardening fix now excludes one-sided Party account attribution from balanced GL
totals, matching DEA journal materialization semantics and removing three false
findings on unchanged `jcl1` data. The engineering gate is implemented, but E6.4
remains live NO-GO until a target workspace completes the six human sign-offs
recorded in the production-readiness document.
The expanded 153-test tenant-aware Loans suite passes with real DEA fixtures.

#### E6.5 Make Loans Primary For New Loans

- Enable selected workspaces, keep legacy Girvi servicing and history visible,
  and monitor outbox, lifecycle completion, and support failures.

Acceptance: users create new loans only in Loans while both source systems remain
correctly represented in unified reads.

Development execution on 2026-08-04: `jcl1` is enabled through the audited
workspace preference and now routes canonical new-loan navigation to Loans.
Direct Girvi origination redirects to Loans, while the Girvi list and existing
record servicing, the Loans operations console, and the unified coexistence
view remain available. Coexistence comparison reports zero mismatches and all
six automated readiness checks pass. Because `jcl1` is a development workspace
with no production-data recovery requirement, the product owner explicitly
accepted skipping formal backup-restore, support/monitoring ownership, and
operator sign-off for this development cutover. Those controls remain mandatory
before enabling any workspace containing production data.

Phase 6 gate: controlled production cutover succeeds and remains reversible by
feature flag without changing record ownership.

### Phase 7: Essential Post-MVP Capabilities

Execute as separately planned vertical slices after MVP stability:

#### E7.1 Add PawnLoan Notices And Scheduled Delivery — Completed 2026-08-04

- Persist the Loans-owned customer-notice intent, recipient and financial
  snapshots, request idempotency key, schedule, and Notify references.
- Support repayment reminders, interest-due notices, overdue notices, and
  release confirmations through Email, SMS, and WhatsApp.
- Keep templates, provider dispatch, attempts, delivery status, external
  references, and failures owned by Notify v2; Loans must derive this delivery
  state rather than duplicate a `notice sent` flag.
- Provide staff create/retry UI and a tenant-scoped scheduled dispatch command.
- Reject auction notices until E7.2 owns the auction/recovery source workflow.

Acceptance: eligibility and contact rules fail closed; request keys are
idempotent; due jobs dispatch against an explicit clock; the loan detail reads
delivery state from Notify; no provider concern or derivable sent status is
stored in Loans.

Result: tenant migration `loans.0009` adds `PawnLoanNotice` as the durable
intent/snapshot record without copying Notify delivery state. Four supported
notice types create deterministic Notify v2 events, recipients, templates,
policies, and jobs through an adapter. Immediate dispatch runs after commit;
future jobs run through tenant command `dispatch_pawn_loan_notices`. The
PawnLoan detail exposes creation, status, provider reference, error, and failed
job retry using a joined read model. Auction notice selection is absent and the
service rejects direct attempts. Six focused domain/service/command tests and
two UI regressions pass; the complete 160-test tenant-aware Loans suite passes,
and the migration is applied to local tenant schemas.

#### E7.2 Add Auction And Recovery — Completed 2026-08-04

- Add auction/recovery documents, custody, and DEA recovery posting.

Acceptance: only an active overdue PawnLoan with all collateral in the vault can
enter auction. Its Loans-owned auction notice must be sent before the scheduled
auction starts. Completion snapshots the buyer, exact debt allocation, and every
disposed collateral item; posts recovery through the Loans outbox and DEA; and
closes the loan. Administrator-only, reason-required reversal restores both the
accounting and custody evidence. Dependent operations remain newest-first.

Result: tenant migration `loans.0010` adds the `PawnLoanAuction`, immutable
auction-item snapshot, auction reversal, auction-linked notice, and generalized
custody-source evidence. The detail UI supports initiate, start, cancel,
complete, reverse, auction notice PDF, and recovery memo PDF. `AUCTION_RECOVERY`
has a stable Loans payload, durable outbox delivery, dedicated DEA posting rule,
voucher type, and reversal path. The safe first boundary accepts only a recovery
that exactly equals the canonical debt. Shortfall write-off and borrower-surplus
distribution are explicitly deferred because each needs its own accounting
document and authorization workflow; neither amount may be hidden in recovery.
Migration `loans.0010` is applied to local tenant schemas and the complete
164-test tenant-aware Loans suite passes.

#### E7.3 Add Renewal Workflows — Completed 2026-08-04

- Add pay-and-renew and top-up renewal with successor-loan audit links.

Acceptance: renewal uses the current business date, settles all interest and
fees, carries a positive principal into exactly one newly numbered successor,
and either accepts a principal paydown or a top-up but never both. Current
collateral valuation and the source policy's maximum LTV cap the successor.
Every source collateral item must remain in the vault and gains an explicit
one-to-one successor lineage. Accounting posts only the real net principal cash
movement plus collected interest and fees. Reversal is administrator-only,
reason-required, newest-first, and restores both loans and custody together.

Result: tenant migration `loans.0011` adds immutable renewal and renewal-
reversal aggregates, collateral lineage, and renewal custody states. The
service supports pay-and-renew and top-up modes, catch-up accrual dependencies,
idempotent request keys, snapshotted valuation/LTV evidence, source closure,
and successor activation. `RENEWAL_SETTLEMENT` posts through a dedicated DEA
rule using the net source-to-successor principal change; `RENEWAL_OPENING` is an
operational balance-establishment event that can complete only after settlement
posts. The loan UI exposes renewal, lineage, a verification PDF, and composite
reversal. Reconciliation understands operational openings and renewal custody
without weakening missing-voucher checks for economic events. The complete
170-test tenant-aware Loans suite passes in three exhaustive groups.

#### E7.3A Correct Collateral-Tranche Economics — Active 2026-08-05

- Move principal allocation and monthly interest calculation to individual
  collateral items using effective-dated metal-rate policies.
- Enforce item valuation/LTV in draft preview, draft service, and approval.
- Derive loan principal and effective display rate from item allocations.
- Withhold a configurable number of advance-interest periods (default one) and
  configured fees while preserving gross principal and net cash separately.
- Persist immutable disbursal, accrual-line, repayment-allocation, release, and
  renewal evidence and update DEA cash/accrual accounting accordingly.

Acceptance: every aggregate total reconciles exactly to immutable item lines;
no form or API can exceed item LTV; advance interest is never charged twice;
cash paid plus deductions equals gross principal; existing posted history is
not silently reinterpreted; all dependent lifecycle and reversal tests pass.

E7.4 FundingLoan/repledging must wait for this corrective slice because it
depends on trustworthy collateral-level principal and custody economics.

Execution status: E7.3A.1 through E7.3A.7.3 are complete. The accepted ADR and
database-free calculator define the economics. Tenant migration `loans.0012`
adds effective-dated workspace policies with optional license overrides for
valuation/LTV/advance interest, metal-specific interest rates, and fees. It
also adds nullable item allocation, frozen rate, and source-policy fields so
legacy development rows are not assigned invented facts. Tested resolvers use
deterministic license-over-workspace precedence and fail closed when required
policy is missing. The administrator setup UI now creates effective-dated
economic, gold/silver rate, and fee policies. Browser draft creation/editing
requires per-item allocations, previews gross/monthly/advance/fee/net totals
without consuming a number, derives aggregate principal/effective rate, and
enforces current-rate/appraisal valuation plus item LTV in both draft and
approval services. Approval snapshots preserve policy and item provenance.
Legacy internal command inputs remain readable without fabricated allocation
only until their owning renewal/test paths are converted. Tenant migration
`loans.0013` adds immutable gross/net disbursal evidence linked to the exact
approval, policy snapshot, source event, item calculations, and fee deductions.
DEA posts gross borrower principal against net cash plus exact deductions;
advance interest goes to income under cash accounting and Unearned Revenue
under accrual accounting. Aggregate-only legacy development approvals keep
their old contract without invented evidence. Tenant migration `loans.0014`
adds immutable item-level accrual lines and consumes frozen advance interest as
a per-item monetary balance. Cash accounting does not charge the covered
period again; accrual accounting reclassifies covered interest from Unearned
Revenue to income and creates receivable only for any uncovered amount. Every
catch-up accrual uses the same evidence. Tenant migration `loans.0015` adds
immutable repayment allocation lines for original principal, applied by
highest frozen item rate first with collateral ID as tie-breaker. Later accrual
bases are reconstructed from the disbursal snapshot and active allocation
lines; reversal excludes the reversed event without mutating evidence.
Capitalized-interest principal remains separate. The accepted release-and-renew
ADR disables new same-loan partial collateral release. E7.3A.7.1 is complete:
release and renew selects retained source items, returns omitted items, accepts
additional collateral, creates explicit lineage, and runs fresh successor item
allocation/rate/valuation/LTV validation. Tenant migration `loans.0016`
completes E7.3A.7.2 with immutable source closing lines for itemized full
release and renewal, and immutable successor opening lines carrying fresh item
principal/rate plus optional predecessor lineage. Renewal successors reconstruct
repayment and accrual tranche bases from active opening evidence. Legacy
aggregate loans receive no fabricated lines, and explicit renewal rejects
unattributed carried capitalized interest. E7.3A.7.3 makes mixed-collateral
composite reversal restore each source item's evidence-backed prior custody,
adds fail-closed opening/closing reconciliation, lists release-and-renew in
operational reports, and exposes item movement and principal evidence in
release/renewal verification PDFs. Auction item allocation remains the final
collateral-principal evidence gap and may stay deferred when auction is outside
the limited MVP pilot.

#### E7.3A.8 Add Auction Item-Principal Evidence — Deferred Post-MVP

This slice is explicitly deferred from the initial limited MVP pilot, not
cancelled. The existing auction workflow may not be enabled in that pilot.
Before auction is enabled for itemized PawnLoans, implement all of the
following:

- Freeze immutable allocation lines linking every disposed collateral item to
  its principal recovered, remaining item principal, frozen monthly rate, and
  deterministic allocation order.
- Define and document how auction proceeds are allocated among fees, interest,
  capitalized-interest principal, and original item principal. Original
  principal allocation must never be guessed or distributed proportionally
  without an accepted domain rule.
- Reconcile auction item lines exactly to the aggregate recovery event and to
  the pre-auction tranche balances reconstructed from disbursal or renewal
  opening plus active repayments.
- Extend auction reversal so evidence remains immutable and the compensating
  event restores balances and custody/disposal state in strict reverse order.
- Expose item allocation in auction recovery PDFs, operational reports, and
  reconciliation, while preserving legacy aggregate auction history without
  fabricated rows.
- Add focused service, DEA payload, reversal, report, PDF, reconciliation, and
  tenant-isolation tests.

Acceptance: an itemized auction cannot complete without exact immutable item
allocation; aggregate recovered original principal equals the sum of item
lines; no item is allocated more than its pre-auction outstanding principal;
reversal changes active interpretation without mutating evidence; and all
source-to-DEA and custody totals reconcile.

Reactivation trigger: move E7.3A.8 back into active execution before enabling
auction routes, permissions, or operational pilot use for the Loans app. It is
not a blocker while auction remains outside the pilot boundary.

#### E7.4 Add FundingLoan And Repledging

- Add the FundingLoan model, workspace numbering, lender payable accounting,
  multi-loan collateral pledge/return, servicing, settlement, reversals,
  reports, and UI.

#### E7.5 Integrate The Customer Portal

- Expose PawnLoan statements, receipts, notices, and releases to explicitly
  linked portal Parties.

#### E7.6 Add Deferred Repayment Controls

- Define backdated repayment/correction policy and staff allocation overrides.

#### E7.6A Add Auditable Collateral Appraisals

- Replace the MVP's manually entered `latest_appraised_value` with a dedicated,
  immutable appraisal history that records the appraiser, appraisal time,
  method, notes, supporting media/tests, value, approval status, and any later
  reappraisal. Add appraisal-specific permissions and keep every loan decision
  linked to the exact appraisal version it used.

The first-class appraisal workflow is intentionally deferred, not discarded.
Until it is implemented, the MVP treats the value frozen on each collateral
item and approval/disbursal snapshot as staff-supplied appraisal evidence.

#### E7.7 Add License-Scoped Authorization

- Add staff-to-license or future branch-scoped authorization.

#### E7.8 Plan Girvi Retirement

- Plan retirement after Girvi's final active loan closes or after a separate
  active-loan migration ADR is accepted.

Post-MVP guardrail: none of these items may be represented by a partial model or
UI stub that suggests an unsupported operational workflow.

## Dependency Review

| Consumer | Required predecessor |
|---|---|
| Draft creation | License/series models, policy contracts, number allocation |
| Approval | Draft service, audit, frozen economic payload |
| Disbursal | Policy snapshot, outbox, DEA adapter, accounting readiness |
| Repayment | Successful disbursal posting, balances, outbox |
| Accrual/capitalization | Policy snapshot, balances, outbox |
| Full release | Balances, accrual catch-up, custody, outbox |
| Release and renew | Source balances, current valuation/LTV, item economics, custody, outbox |
| Reversal | Original event, dependency graph, compensating DEA contract |
| Staff lifecycle UI | Corresponding service, selector, permissions, failure states |
| Cutover | E2-E5 gates, unified reads, comparison, runbook, feature flag |

No MVP step depends on FundingLoan, notices, auctions, renewals, portal
integration, repayment backdating, or staff allocation overrides.

## Execution Readiness

Status: **E6.5 development cutover is active for `jcl1`; Loans is primary for new loans and Girvi remains legacy-servicing only. The Phase 6 production gate remains pending until the complete E6.4 manual readiness register is satisfied for a production workspace.**

The plan is not authorization to combine phases or bypass gates. Each tenant
schema slice must use `migrate_schemas`, each accounting path must preserve DEA
ownership and reversal rules, and each cutover action must remain feature-gated.

## Capability Reference (Superseded Ordering)

The older numbered steps below are retained temporarily as detailed capability
notes. Their numeric order is superseded by the authoritative `E0-E7` plan
above. Implementation issue/PR names must use the authoritative identifiers.

### Step 1: Rewrite Planning Docs Only

Objective: create the official execution source of truth before code starts.

Scope:

- Create this roadmap.
- Update `docs/STATUS.md`.
- Link from Girvi app docs.
- No Python, migration, template, settings, URL, or runtime behavior changes.

Acceptance criteria:

- Roadmap exists under `docs/plans/`.
- Status records that the rewrite is planning-only.
- Existing runtime is untouched.

Rollback risk: very low; revert documentation only.

### Step 2: Empty `loans` App Skeleton

Objective: introduce the new package without enabling runtime behavior.

Scope:

- Create `apps/tenant_apps/loans/`.
- Add `apps.py` and empty package folders for models, services, selectors, integrations, and tests.
- Do not add the app to installed apps yet.
- Do not create models or migrations.

Acceptance criteria:

- `LoansConfig` imports cleanly.
- No database tables are created.
- Existing tests are unaffected.

Rollback risk: very low; remove the new package.

### Step 3: Register App With No Models

Objective: enable the app safely while it has no database footprint.

Scope:

- Add the app to tenant installed apps.
- Keep `models/__init__.py` empty.
- Add app-registry smoke coverage.
- No URLs, admin, permissions, or migrations.

Acceptance criteria:

- Django starts with `loans` installed.
- `makemigrations --check` has no model changes for `loans`.
- Existing Girvi behavior is unchanged.

Rollback risk: low; remove the app from settings.

### Step 4: Domain Constants And Pure Types

Objective: define stable vocabulary before schema work.

Scope:

- Add pure enums/constants for pawn-loan status, funding-loan status, transaction type, collateral custody, notice type, auction status, and document kind.
- Add compatibility vocabulary mapping old `GivenLoan` to `PawnLoan` and old `TakenLoan` to `FundingLoan`.
- Add tests for stored versus derived statuses.
- No models.

Acceptance criteria:

- Pure domain module imports without database access.
- Status vocabulary matches this roadmap.

Rollback risk: low.

### Step 5: Core PawnLoan Models Without Runtime URLs

Objective: create the minimal database foundation.

Scope:

- Add `LoanLicense`, `LoanSeries`, `PawnLoan`, `PawnCollateralItem`,
  `LoanNumberSequence`, and `LoanChangeLog`.
- Use Party FK directly for `PawnLoan.borrower`.
- Do not add `FundingLoan` until its first complete workflow slice is planned.
- Add initial tenant migration and model tests.
- Model only accepted regulatory license, series, expiry, and numbering duties;
  do not copy unrelated Girvi `License` complexity.
- No repayments, releases, accruals, notices, auctions, UI, or admin workflow actions.

Acceptance criteria:

- Tenant migration applies cleanly.
- No runtime route uses new models.
- Existing Girvi behavior remains unchanged.

Rollback risk: medium because schema is introduced.

### Step 6: Number Allocation Service

Objective: implement safe locked document numbering before create workflows.

Scope:

- Add preview/allocation for `PAWN_LOAN` and `PAWN_LOAN_RELEASE`, scoped to a
  series. Add other document kinds only with their workflows.
- Allocation locks `LoanNumberSequence`.
- Preview is non-consuming.
- Allocate at draft creation, never recycle, and fail closed at series maximum.
- Manual numbers require an explicit import flag.

Acceptance criteria:

- Preview does not increment.
- Allocation increments atomically.
- Duplicate generated numbers fail closed.

Rollback risk: low; unused service.

### Step 7: PawnLoan Creation Service

Objective: create draft customer pawn loans with collateral through one explicit service.

Scope:

- Create `PawnLoan` in `DRAFT`.
- Create collateral rows in one transaction.
- Snapshot principal, rate, and valuation inputs.
- Write `LoanChangeLog`.
- No accounting event.

Acceptance criteria:

- Valid draft pawn loan and collateral can be created through the service.
- Invalid borrower/collateral/principal input fails.
- No views, forms, URLs, or DEA calls.

Rollback risk: low to medium.

### Step 8: Approval And Cancellation Services

Objective: implement the simplest lifecycle mutation services.

Scope:

- `approve_loan`: `DRAFT -> APPROVED`.
- `cancel_loan`: `DRAFT/APPROVED -> CANCELLED`.
- Audit every transition.
- Enforce collateral and principal before approval.
- First implementation targets `PawnLoan`; `FundingLoan` lifecycle services are added later when funding/repledge workflows are implemented.

Acceptance criteria:

- Valid transitions succeed.
- Invalid transitions fail.
- Cancellation requires a reason.

Rollback risk: low.

### Step 9: Accounting Adapter Contract

Objective: define how the new loan app talks to DEA.

Scope:

- Add payload builders and deterministic idempotency keys for disbursal, repayment, accrual, release, auction recovery, and reversal.
- Payloads must identify whether the source is `PawnLoan` or `FundingLoan`; DEA account resolution must remain role/purpose based.
- No direct journal or voucher creation outside the adapter.
- No live posting unless later services call the adapter.

Acceptance criteria:

- Contract is explicit and tested.
- Required economic fields are present.

Rollback risk: low.

### Step 10: Disbursement Service

Objective: activate an approved loan and emit disbursement through the accounting adapter.

Scope:

- Add `PawnLoanTransaction`.
- Record one `PawnLoan` disbursement transaction.
- Move `PawnLoan` from `APPROVED -> ACTIVE`.
- Call accounting adapter with `PAWN_LOAN_DISBURSED`.

Acceptance criteria:

- Approved pawn loan disburses once.
- Draft/cancelled pawn loans cannot disburse.
- Persist disbursal and its durable outbox row atomically, attempt DEA posting
  immediately, and expose pending/failed posting for safe idempotent retry.
- Block dependent financial actions until posting succeeds.

Rollback risk: medium.

### Step 11: Repayment Service

Objective: record borrower repayments with clear allocation.

Scope:

- Use the fixed allocation order: fees/charges, overdue interest, current
  interest, then principal. Staff override and backdating are deferred.
- Record principal/interest/fee split on `PawnLoanTransaction`.
- Emit `PAWN_LOAN_REPAYMENT_RECEIVED` accounting event.
- Do not release collateral automatically.

Acceptance criteria:

- Transaction totals drive outstanding balance selectors.
- Pawn loan remains `ACTIVE`; partially paid is derived.

Rollback risk: medium.

### Step 12: Balance Selectors

Objective: centralize read-side balances and derived status.

Scope:

- Compute principal paid, interest paid, outstanding principal, outstanding interest, and total outstanding.
- Derive partially paid, overdue, and closure ready.
- First selector implementation targets `PawnLoan`; funding-loan payable balances get separate selectors when `FundingLoan` transactions are added.
- No mutation.

Acceptance criteria:

- Services and future views can consume one balance read model.
- No duplicated balance math in views.

Rollback risk: low.

### Step 13: Interest Accrual Model And Service

Objective: persist interest recognition rows separately from operational previews.

Scope:

- Add `PawnLoanInterestAccrual`.
- Preview completed periods.
- Execute accrual rows idempotently.
- Post finalized accruals when the snapshotted policy is accrual accounting;
  under cash accounting, recognize interest when collected.
- Add explicit capitalization events for compound loans after their snapshotted
  configurable interval.
- Scope accrual rows to `PawnLoan` in the first implementation. Funding-loan interest payable accrual should be a separate later design, not inferred from pawn-loan rules.
- Do not make release depend on this yet.

Acceptance criteria:

- Accrual is an independent business event.
- Operational interest preview can remain selector-derived.

Rollback risk: medium.

### Step 14: Release Models And Full Release Service

Objective: support final settlement and collateral return.

Scope:

- Add `PawnLoanRelease` and `PawnLoanReleaseItem`.
- Implement full release only.
- Validate settlement, custody, active state, and catch-up accrual integrity.
- Snapshot settlement values.
- Move all collateral to customer custody.
- Emit accounting event if money is collected.

Acceptance criteria:

- Release is atomic.
- Custody handoff cannot happen without release document.
- No model method performs release.

Rollback risk: medium.

### Step 15: Partial Release Service

Objective: allow selected collateral item release with explicit settlement.

Scope:

- Extend release service to selected items.
- Calculate the minimum settlement from fees/interest plus principal reduction
  required to keep retained-collateral LTV within policy.
- Snapshot the release-time valuation policy, rate/appraisal inputs, and LTV.
- Released items move to customer custody.
- Pawn loan remains `ACTIVE`.

Acceptance criteria:

- Full and partial release share one service boundary.
- Partial release status is derived from custody.

Rollback risk: medium.

### Step 16: Notice Model And Notification Adapter

Objective: record and send WhatsApp/SMS loan notices explicitly.

Scope:

- Add `PawnLoanNotice`.
- Support repayment reminder, interest due, overdue notice, auction notice, and release confirmation.
- First implementation targets `PawnLoan` customer notices. Funding-loan lender notices should be added only after FundingLoan servicing screens exist.
- Store send status and external reference.
- Keep provider details in the notification app.

Acceptance criteria:

- Notice sent/failed state is auditable.
- Notice-sent status remains derived.

Rollback risk: low to medium.

### Step 17: Auction Model And Service

Objective: implement recovery workflow without overloading loan status.

Scope:

- Add `PawnLoanAuction`.
- Start auction only for active overdue/default-derived `PawnLoan` records after notice or explicit override.
- Record auction result and realized amount.
- Emit accounting recovery event.

Acceptance criteria:

- Auction is first-class.
- No direct journal creation.

Rollback risk: medium.

### Step 18: PawnLoan Renewal Service

Objective: create a successor pawn loan from an existing pawn loan with explicit settlement.

Scope:

- Add `PawnLoanRenewal`.
- Support pay-and-renew and top-up-renew.
- Link source and successor.
- Move source to `RENEWED`.
- Emit accounting events for payment/top-up only through adapter.

Acceptance criteria:

- Renewal is auditable and not a status alias.
- Source cannot renew twice.

Rollback risk: medium.

### Step 19: Read-Only Admin And Diagnostics

Objective: allow safe inspection of new data during development.

Scope:

- Register new models in admin with read-only or minimal-edit behavior.
- No business actions, posting buttons, or release buttons.

Acceptance criteria:

- Developers can inspect new data.
- Admin cannot bypass services.

Rollback risk: low.

### Step 20: Minimal Staff UI For Create/List/Detail

Objective: expose the new app read/create flow behind internal URLs.

Scope:

- Pawn-loan list, detail, and create draft pawn loan with collateral.
- No disbursement, repayment, release, or main navigation cutover.
- Bootstrap and HTMX-friendly templates.

Acceptance criteria:

- Staff can create and inspect new draft pawn loans.
- Existing Girvi navigation remains unchanged.

Rollback risk: medium; remove URL include to disable.

### Step 21: Staff UI For Approval And Disbursement

Objective: expose the first accounting-affecting workflow under controlled UI.

Scope:

- Approve draft.
- Cancel draft/approved.
- Disburse approved.
- Show accounting status on detail.
- Require permissions.

Acceptance criteria:

- Approved pawn loans can be disbursed through UI.
- Accounting adapter boundary is respected.

Rollback risk: medium.

### Step 22: Staff UI For Repayment

Objective: enable controlled collections.

Scope:

- Repayment form with interest-only, principal-only, full settlement, and custom presets.
- Show settlement preview from selectors.
- Post through repayment service.

Acceptance criteria:

- Collections can be recorded and posted.
- Balances update from selectors.

Rollback risk: medium.

### Step 23: Staff UI For Release

Objective: enable full and partial collateral release in the new app.

Scope:

- Release readiness page.
- Full release flow.
- Partial release item selection.
- Settlement preview and custody checklist.

Acceptance criteria:

- Release workflows use service only.
- Detail shows released items and release documents.

Rollback risk: medium.

### Step 24: Notices And Overdue UI

Objective: expose derived overdue queues and notice sending.

Scope:

- Dashboard overdue queue.
- Notice list on loan detail.
- Send reminder, overdue, and auction notices.
- No scheduled sending yet.

Acceptance criteria:

- Staff can identify overdue loans and send notices.
- No stored overdue status is required.

Rollback risk: low to medium.

### Step 25: Reports And Reconciliation

Objective: prove new app totals and accounting visibility.

Scope:

- Active loan report.
- Due/overdue report.
- Interest accrual report.
- Release report.
- Accounting reconciliation report.
- Collateral custody report.
- Unified coexistence selectors combining Girvi and Loans read models with
  explicit source labels and owner-app action links.

Acceptance criteria:

- Reports are selector-backed and read-only.
- Reconciliation detects missing or failed posting.

Rollback risk: low.

### Step 26: PDF Documents

Objective: generate essential customer-facing documents.

Scope:

- Loan ticket.
- Repayment receipt.
- Release memo or Form H equivalent.
- Notice PDF.
- Use fixed templates first.

Acceptance criteria:

- Staff can print core documents.
- No dependency on old Girvi template-frame system.

Rollback risk: low.

### Step 27: Girvi-To-Loans Comparison Mapper Dry Run

Objective: map Girvi data to new read contracts for comparison without creating
a second writable operational copy.

Scope:

- Read old GivenLoan, LoanItem, payments, releases, accruals, and notices where available.
- Produce counts and mismatch report.
- No writes.

Acceptance criteria:

- Dry run is deterministic.
- Unsupported legacy cases are reported.

Rollback risk: very low.

### Step 28: Optional Historical Snapshot Import Behind Explicit Flag

Objective: import immutable historical snapshots for staging/validation while
Girvi remains operational owner of every legacy loan.

Scope:

- Add `--apply`.
- Preserve old loan IDs as legacy references.
- Store snapshots or validation records, not writable operational loans.
- Do not post accounting during import.
- Store import batch identity.

Acceptance criteria:

- Import is idempotent by batch/source.
- Existing Girvi remains unchanged.

Rollback risk: medium.

### Step 29: Parallel Read Validation

Objective: compare old Girvi and new Loans outputs before cutover.

Scope:

- Compare counts, active/released totals, principal, interest paid, outstanding, custody, and release status.
- Read-only command.

Acceptance criteria:

- Matching data reports zero mismatches.
- Deliberate mismatches are categorized.

Rollback risk: low.

### Step 30: Feature-Gated New Loan Creation Cutover

Objective: allow selected tenants/workspaces to create new loans only in the new app.

Scope:

- Add feature flag such as `loans_new_module_enabled`.
- When enabled, sidebar and quick actions point to new pawn-loan create/list screens.
- Girvi remains writable for its existing active loans and available for
  history; it must not accept new loans for an enabled workspace.

Acceptance criteria:

- Flag off keeps current Girvi navigation.
- Flag on enables new Loans entrypoints.
- Rollback is flag off.

Rollback risk: medium operationally, low technically.

### Step 31: Controlled Production Hardening

Objective: close gaps before broad rollout.

Scope:

- Add tenant migration checks.
- Add end-to-end workflow tests.
- Add operational runbook.
- Confirm accounting reconciliation and import parity.

Acceptance criteria:

- New app can run complete loan lifecycle.
- Rollback and support procedures are documented.

Rollback risk: low to medium.

### Step 32: Make New Loans Primary, Keep Girvi Legacy-Servicing Only

Objective: move new-loan operations to the new app while Girvi continues to own
its remaining active legacy loans.

Scope:

- Main navigation points to `loans`.
- Girvi new-loan creation is blocked for cutover tenants. Servicing remains
  available only for active loans originally owned by Girvi.
- Old Girvi detail/list remains readable.

Acceptance criteria:

- Users create new loans only in `loans`; legacy servicing stays in Girvi until
  those loans close or a separate operational migration is approved.
- Historical Girvi remains accessible.

Rollback risk: medium.

### Step 33: Legacy Cleanup Planning Only

Objective: plan eventual Girvi retirement after stable production usage.

Scope:

- Inventory remaining Girvi read dependencies.
- Define retention and archive/export policy.
- No code removal.

Acceptance criteria:

- Retirement criteria are explicit.
- No runtime behavior changes.

Rollback risk: very low.

## Historical Reference Status

The legacy Step 1 documentation baseline is complete. Do not execute the older
numbered capability list by numeric order; use the authoritative `E0-E7` plan
and gates above.
