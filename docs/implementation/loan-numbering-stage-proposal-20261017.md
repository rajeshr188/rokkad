---
status: accepted
owner: project
updated: 2026-10-17
tags: [loans, numbering, drafts, origination, proposal]
related: [origination-complexity-review-20261017.md, ../adr/2026-10-17-origination-review-and-safe-recovery.md]
---

# When to assign the official loan number

The owner subsequently approved this design after discussing draft printing,
approval ordering and its tradeoffs. The [accepted decision](../adr/2026-10-17-loan-number-at-approval.md)
and [local implementation](approval-numbering-20261017.md) track delivery. The
comparison below retains the design reasoning and pre-change baseline.

The owner clarified the print boundary: drafts cannot produce loan tickets or
draft PDF previews. Approval enables ticket printing with the permanent number,
including before payout in the extended workflow.

The owner agrees with simplifying origination but requested a detailed numbering
explanation before changing it. He confirms that staff print/share/write the
official loan number **only after payout is confirmed**. This supports delayed
assignment; it does not itself implement or migrate that behaviour.

## Current rule and its cost

New direct entry creates a numbered DRAFT, then opens the final agreement review.
The number and register/product association are fixed at that first saved draft.
Borrower, date, principal and collateral are editable before approval; choosing a
wrong register/product requires the existing linked replacement and cancellation.
This protects committed number identity, but consumes a number before the operator
has finished checking the agreement. Cancelled drafts leave explainable gaps.

Automatic generation and the point of issuance are separate choices. Retain the
existing atomic allocator, non-consuming preview, independent release counter,
range reservations and original-paper duplicate checks under every option below.

| Choice | Benefit | Cost and fit |
| --- | --- | --- |
| Keep assignment at first draft save | Existing references and printing remain simple. | Wrong-register recovery and abandoned-number gaps remain; immediate lowest-risk baseline. |
| Add full review before the first numbered save | Operators can catch mistakes before reserving a number, with smaller persistence changes. | Saving a draft still reserves a number; later register mistakes still require replacement. Useful intermediate option. |
| Keep saved drafts unnumbered; assign at agreement approval | Register/product mistakes are ordinary pre-approval edits; abandoned unapproved preparations do not consume official numbers. | Requires stable draft identity, document gates, changed signed review/retry and migration contracts. Best fit for the owner's confirmed printing practice. |

## Recommended next design

Use one rule across direct workflows: **assign the number when the agreement is
approved**. SIMPLE already combines approval and payout in one confirmation, so
assignment is in that transaction. EXTENDED assigns at its separate approval;
payout later retains that identity. This uses the existing agreement-freeze
boundary and avoids a new approved-but-unnumbered state. The owner's post-payout
printing practice permits this rule; it does not require delaying identity beyond
approval in every workflow.

Use the loan's stable internal identity throughout preparation and show a clearly
labelled draft reference. It must never be displayed as an official register
number or inserted into a customer's official ticket. Prefer the existing loan
identity; do not add an application/workflow module or another counter unless a
human-friendly reference has a concrete need.

For SIMPLE direct entry, confirmation would atomically:

1. Lock the current draft and recheck actor, register, terms, collateral and signed
   review against the actual input state.
2. Allocate the official number from the existing locked sequence.
3. Freeze the final agreement, record approval/payout and retain their linked
   evidence in the same transaction.
4. Commit once, then offer the official ticket.

Before this commitment, supported borrower, register/product, amount and item
mistakes remain draft edits. Register/product changes must still validate scope,
product eligibility and the newly applicable terms, invalidate stale reviews and
retain an audit of preparation edits. They cannot move a posted loan.

The reviewed screen may show an **expected next number**, explicitly unreserved.
Another confirmation can legitimately receive it first. The final official number
must be visibly confirmed in the completed result and issued documents; no ticket
can promise the preview value. Sequential allocation follows confirmation order,
not when a draft was first opened or saved.

## Boundaries that need design and tests

- **Concurrency/retries:** competing confirmations receive distinct numbers;
  double-clicks, network retries and uncertain responses return the original loan
  and number. A rolled-back database transaction leaves no committed issue.
  Numbers already committed remain consumed after a later cancellation/reversal.
- **Extended approval:** assign at approval and retain the identity for payout.
  Reopening an already numbered approved loan does not release or recycle its
  number. Choosing a different register after issuance still needs the existing
  supported recovery. Delaying EXTENDED beyond approval is not recommended
  without a concrete business need for the additional evidence/document states.
- **External handoff:** actual cash cannot be rolled back with the database.
  Preserve existing exactly-once outcome lookup and the completed-payout recovery
  route when cash has already moved; do not describe the database transaction as
  proving or undoing physical payment.
- **Documents:** preparations can show draft references, but official loan tickets
  require the official identity. Retained numbered draft documents stay unchanged.
- **Compatibility:** existing numbered drafts keep their numbers and current
  recovery rules. Posted/imported/paper loans and previously issued documents are
  never renumbered. Earlier signed forms need an explicit compatible route or a
  clear fresh-review response, with no duplicate creation.
- **Schema and recovery:** loan-number uniqueness/nullability, register/product
  immutability guards, exports, document fingerprints, loan lists, recovery and
  source-local preparation references all need review. No literal placeholder can
  masquerade as an official number.

## Paper backfill still works

Reserve the real historical range through AA05000, including already used closed
or excluded numbers. Direct confirmation uses AA05001 onward. Later paper entry
claims its original AA00001–AA05000 number, checks duplicate/source identities and
does not rewind the live counter. Paper preparation cannot allocate a replacement
official number for a number already issued outside Rokkad. Recording a higher
matching original number retains the existing monotonic counter rule.

This proposal did not itself change numbering. Following approval, the linked
implementation adds the specific ADR, Loans 0094 and compatibility tests. No
production record correction or deployment is part of this local checkpoint.
