---
status: active
owner: loans
updated: 2026-10-05
tags: [implementation, loans, servicing, eligibility, ld-02]
related: [../plans/unified-loan-domain-correction.md, loan-interest-contract-ld01a.md]
---

# LD-02: common repayment and full-release eligibility

## Delivery boundary

The owner authorized LD-02 after checkpoint `4bf095b1` (LD-01A). This slice uses
the existing PawnLoan aggregate and posting/evidence shapes. It adds no table,
migration, action permission, generic opening writer or new loan-entry screen.
Admission changes remain LD-03; reduced-principal opening continuation remains
LD-04. Production and running candidates are unchanged.

## Shared factual prerequisites

`services/servicing_eligibility.py` returns immutable factual blockers for operation
REPAYMENT/FULL_RELEASE, purpose CURRENT/PAPER and actual effective date. It resolves
the saved contract in the active Workspace, checks active lifecycle, chronology,
later financial events, finalized interest and custody, the opening cutover bound
and full-release collateral. Coverage is metadata, not an authorization grant or
an automatic complete-book attestation.

Existing commands retain actor permission, scoped aggregate/item locks, request-key
retries, signed actual-source review and atomic posting. Internal compensation and
closed replay keep their existing separate validation: later retained originals
are expected during reviewed replay and cannot pass a generic earlier-insertion
gate. Generic `record_loan_event` remains closed to arbitrary opening transactions.

## Supported actions

- Native policy/2 SIMPLE/FULL_MONTH flexible/single-payment bullet contracts with
  saved disbursal snapshots accept reviewed completed paper receipts. Source date,
  reference, unknown original receiver and actual principal item allocations remain
  immutable facts. Saved origination terms are not rewritten.
- Current digital receipts on supported recorded/opening loans retain ordinary
  collection and highest-monthly-rate-first principal allocation. Completed paper
  multi-item receipts require staff's actual principal split. Interest-only receipts
  need no principal split; unsupported outstanding-fee agreements block explicitly.
- Early recorded policy/1 snapshots without a collection profile retain their
  existing recorded event fold for current repayments. This narrow compatibility
  fallback supplies no anniversary agreement and does not allow paper repayment.
  Unknown explicit profiles and mixed/missing origins still block.
- The existing opening review's multiple-outstanding-item paper principal limit is
  checked before recognition/posting, even with a supplied split. A new supported
  reviewed allocation profile is later work; no inferred split bypasses it.
- Full release of shared native monthly contracts quotes eligible completed charges
  without writing and recognizes them atomically before settlement. Completed
  charges remain independently owed; current-period catch-up retains existing
  release-paired reversal. Zero covered periods, advance, paise principal under
  whole-rupee interest and zero-extra-cash closure remain supported.
- Full debt settlement leaves no retained secured exposure, so current appraisal/
  metal price is not compulsory for any origin. Available values remain optional
  evidence. Partial release retains valuation/LTV safety checks and physical
  verification remains enforced.
- Reviewed completed closure works on supported ordinary loans independently of
  origin, retaining the original scoped closing number or an explicitly assigned
  recording number. Unknown handover stays PAPER_CLOSED with no fabricated return
  timestamp. Later confirmed return is a separate custody fact.

## Coverage, reversals and compatibility

A native loan with a completed paper receipt/closure now requires existing explicit
transaction review instead of inheriting SYSTEM_RECORDED completeness. Receipt
entry itself certifies no absent paper-book activity. Closure carries forward only
an already explicit complete review. Future-capture transition remains LD-06.

Newest-first existing paired closure reversal works for new native/opening paper
closures. Initial backlog admission and recorded-source correction dependencies
retain their history-review gate; later changed custody blocks reversal. Native
re-recognition after reversing a coupled settlement can still require reviewed
correction because the retained monthly row cannot be silently reused. Wider
correction/operation integration remains LD-06.

No portable wire profile is silently widened. Approval-based history/1/2/3 export
now explicitly rejects completed paper receipts whose source/allocation purpose
would be dropped; its existing paper-closure blocker remains. Use Loans recovery
backup for exact source identity, alongside matching database/media prerequisites.
Existing supported ordinary history and opening export/restore retain their
readers. Wider independently portable paper evidence remains LD-07.

Rollback stops newly enabled action purposes while retaining compatible readers
and existing writer/evidence support. Never undo accepted payments or replace an
application database with an earlier backup over later legitimate transactions.

## Verification

Verification uses disposable `loan-interest-ld02-qa-20261005` and dedicated
`test_rokkad_ld02_20261005` with `django_project.settings.test`. No application
database migration, contract conversion or deployment has been performed.

The final targeted regression passes **256 tests in 251.059s**. It includes shared
contract/position reads, current and completed-paper repayment, full release,
zero/advance handling, paise principal with whole-rupee interest, signed review and
retry/rollback, paired reversal and later custody guards, genuine native paper
recovery with exact source rows, frozen opening restore, ordinary recorded
corrections, paper batch concurrency, restricted-role posting/immutability/isolation
and risk/communication coverage reads.

The wider run exercised **294 tests in 338.822s**: 290 passed, with three stale
blocker-message assertions and one genuine frozen-opening release restoration
error. Full settlement had normalized an already known zero-valued field from its
saved precision; it now retains the existing valued calculation and uses the
no-valuation fallback only when values are incomplete. The three assertions now
check the shared prerequisite wording and explicit opening allocation limit.
All four cases pass in the final 256-test suite. The wider run also exercised
multi-item paper allocations, independent loans, release batches/concessions,
transaction reviews and loan-history/1/2/3 import/export compatibility.

Earlier focused checks exposed an overly broad paper-closure reversal gate and a
legacy recorded-current-payment compatibility gate; both were narrowed while
preserving actual admission/correction and custody dependencies. A dated fixture
and an assertion aimed at the read-only reversal layer were corrected; the latter
now exercises the locked writer's actual later-custody guard.

Django system checks report no issues (one existing silenced check), migration
drift reports no changes, 550 Loans Python files parse, and scoped whitespace
checks pass. The full repository suite was not repeated. The five unrelated
baseline failures recorded in LD-01A remain unchanged; this is not a claim of a
wholly green repository or production readiness for all later slices.
