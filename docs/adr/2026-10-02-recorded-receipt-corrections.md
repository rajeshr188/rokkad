---
status: accepted
owner: project
updated: 2026-10-03
tags: [loans, corrections, paper-entry, history]
---

# Reviewed restatement of recorded paper receipts

## Decision

Extend the [unified Loans workflow](2026-10-02-unified-loan-recording.md) with a
reviewed correction command for missing receipts, mistaken receipt facts and voids
on active `recorded-anniversary/1` contracts. A void corrects an entry that did not
happen; it is not a refund. A refund or new advance needs its own business action.

Use existing immutable loan events, reversal links, principal allocation lines,
obligation allocations and change logs. Do not introduce a second ledger or edit
completed events. Compensate the supported collection history newest first and
replay it in actual date/order, preserving every unaffected receipt's total and
source evidence. Recalculate interest and allocations using the unchanged agreed
contract. The bounded command reviews all collection events, even an unchanged
earlier receipt, instead of implementing a second dependency calculation engine.

The command supports one collateral group, up to 120 active collection events and
1,000 retained events. It requires the current loan administrator, repayment and
accrual permissions, active Workspace write access, a reason and explicit signed
review. Locks, actor/Workspace binding, event fingerprints, atomic posting and
request-key replay protect against concurrent or altered submissions.

## Dates and evidence

Compensation has its original event's business date. Replacement/replayed receipts
have their actual receipt dates. Creation timestamps and recording actors describe
the present correction. Versioned `recorded-history-correction/1` metadata links the
batch, source event, root receipt, reason and request digest. Earlier corrections
remain traversable; a replacement may retain its own original paper reference but
cannot borrow another receipt's reference, including a voided one.

Historical balance queries by business date show the corrected facts. They are
not a claim about what the software knew on that historical date. Original events,
their creation times and compensations retain that audit evidence; no new
knowledge-at-time query API is introduced. Printed/reported corrections identify
restatement and do not represent another physical collection or refund.

For a replacement on the same day, preserve its position unless another same-day
receipt is explicitly selected as the following receipt. New or moved receipts
default to after that day's existing receipts. The operator can choose an explicit
same-day position; calendar dates alone cannot establish cash order.

## Boundary and consequences

The initial boundary below is extended by the
[settlement correction decision](2026-10-02-recorded-settlement-corrections.md):
receipt corrections can reconcile a later full closure or renewal while its
agreement and physical custody facts remain unchanged. Other amendments remain
outside this command.

Origination/renewal-opening terms remain unchanged. An active successor loan may
have its own later receipts corrected without altering the predecessor renewal.
If the target history includes closure, renewal settlement, auction, unsupported
accrual/correction or non-vault custody, show its dependencies and refuse posting.
Revising these can require different actual settlement cash, successor agreements
and custody facts; receipt replay cannot manufacture those facts. Cross-lifecycle
correction is a separate remaining extension of UR-04. Native loans and migration
openings retain their existing correction workflows.

Do not allow generic one-event reversal to split an admitted paper contract's
receipt and anniversary-interest correction. Do not advance the original scoped
completeness date merely because one missing receipt is entered. Current exposure,
obligations and principal monitoring consume the corrected canonical records.
Automatic notice/recovery and portable history integration retain their existing
guards until the corresponding unified-recording stages are complete.
