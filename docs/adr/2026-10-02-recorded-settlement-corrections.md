---
status: accepted
owner: project
updated: 2026-10-03
tags: [loans, corrections, paper-entry, settlements]
---

# Reconcile receipt corrections with an unchanged renewal or full return

## Decision

Extend [reviewed receipt restatement](2026-10-02-recorded-receipt-corrections.md)
through a recorded renewal or single-loan full release. An earlier receipt changes
the source balance; it does not change the successor's agreed principal or terms.
Require actual settlement cash, a source reference and confirmation that the
settlement date, numbers, successor agreement and custody facts remain correct.

Reuse canonical events, compensation links, obligation allocations, schedule changes
and principal-closing lines. Compensate the settlement and collection events at their
original business dates, reactivate the allocation schedule, replay the receipts and
reconcile settlement in one transaction. Source loan state remains CLOSED throughout.
Private repayment replay requires correction evidence and a compensated recorded
settlement; ordinary repayments continue to require ACTIVE.

Closure cash must equal corrected principal plus interest. Renewal reuses admission's
cash reconciliation for carry/reduction/top-up or full repayment/fresh advance, with
explicit old-interest offset and unchanged successor principal. A mismatch shows
actual versus required cash and rolls back. Never change actual cash automatically,
capitalize a difference, infer a refund or waive debt to force reconciliation.

## Evidence and readers

Original PawnLoanRelease/PawnLoanRenewal, successor opening and custody movements
remain immutable. No physical return, repledge or storage movement is repeated.
Replacement settlement evidence uses `recorded-history-correction/1`, role SETTLEMENT,
original root event, immediately preceding event, reason, actor and checked settlement
reference. Further corrections continue that root lineage. Financial compensation
does not undo the handover or the renewal agreement.

Shared selectors project current monetary particulars from the active replacement
event onto copies of the retained documents. Loan/release screens, settlement reports,
exports and regenerated memos use this projection with correction provenance and the
corrected event fingerprint. The successor opening retains its original funding
evidence; current pledge-book presentation follows its linked corrected settlement.
Saved statutory pages and original snapshots are never rewritten.

Renewal compensation retains original cash evidence so movement reports subtract
actual cash rather than carried debt. Closure cash entries remain distinct from
the retained physical return. Business-date queries show restated history; creation
timestamps show when corrections became known.

## Review, authority and limits

Existing administrator/repayment/accrual authority remains; settlement correction
also requires release authority. Lock the source and up to five forward successors
in admission order and lock collateral rows. A signed one-hour review binds event
fingerprints, contract identity, states, custody history and current date. Show linked
contracts, balances and custody. Later successor activity invalidates review; retries
remain idempotent. Posting uses existing forced Workspace RLS.

The admitted anniversary profile retains one collateral group and bounds of 120
active events/1,000 retained events per loan. Successors can be active, renewed or
fully closed with supported history. Their financial records and agreed terms remain
unchanged; monitoring continues from their original opening and later transactions.
The original completeness cutoff remains unchanged.

This command does not amend origination/successor terms, settlement dates, funding
method, loan identity or custody facts. Partial release, concessions, auctions and
other lifecycle amendments require wider reconciliation. UR-04 therefore supports
receipt corrections across unchanged lifecycle facts, not all possible contract or
custody amendments. See the [tracking plan](../plans/unified-loan-recording.md).

## Batch extension (3 October)

A receipt on a release-batch member must be corrected through a batch-wide review.
Lock the retained batch and every member loan in primary-key order. Explicitly
select one receipt correction per changed admitted-paper loan; every other member
is confirmed unchanged. Reuse the same compensation/replay command within one
transaction and require the sum of revised and unchanged settlements to equal the
actual combined collection. No inferred balancing payment, refund or concession.
This applies to counter batches and paper batches; a paper batch can retain
individual payers and receipt references rather than imply a single payer.

The one-hour signed review binds all member histories, contract state and custody,
including unchanged members. A later member change requires fresh review; retries
are serialized on the batch and bound to the complete normalized input. Existing
administrator, release, repayment and accrual authority and forced RLS apply.

Original batch header, lines, releases and handovers remain immutable. Canonical
correction events carry versioned `recorded-batch-correction/1` evidence linking
the batch, original/current collection, all members, changed members, request key
and checked source. No new table or migration. Shared read projections expose the
latest reviewed collection and current individual settlements alongside originals;
regenerated memos and reconciliation CSV retain correction provenance. A later
ordinary reversal of an unchanged member is shown separately and never invents
a cash refund or rewrites the retained collection.

Review supports the existing batch bounds (20 counter or 50 paper members), one unchanged collateral group for each changed
loan, no concessions/fees on changed settlements, 120 active/1,000 retained events
per changed loan. Native/opening members may remain unchanged; correcting their
receipts is outside this profile. All releases must still reconcile to CLOSED,
zero due and returned custody. Membership, payer, date, contract and handover
amendments remain unsupported.
