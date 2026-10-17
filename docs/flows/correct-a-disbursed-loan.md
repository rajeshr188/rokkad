---
status: active
owner: project
updated: 2026-10-17
tags: [loans, corrections, user-guide]
---

# Correct an amount entered on a disbursed loan

First distinguish an original recording mistake from a real later business action.
A corrected principal is not, by itself, a new payout or refund. Use the existing
loan's supported correction; do not replace its saved agreement with today's setup.

## Choose by stage and affected fact

| Stage or mistake | Existing supported route |
| --- | --- |
| Unconfirmed DRAFT: borrower, date, amounts or collateral | Correct draft, then review again. Series/product and reserved number are fixed on an existing direct draft. |
| APPROVED but unpaid: agreed terms need changing | Return to draft with a reason, edit, then obtain a fresh approval/review. |
| Confirmed wrong borrower or collateral transcription | Use **Correct… → Borrower / Collateral details**, subject to the shown dependency checks. These do not replay principal or payments. |
| Confirmed wrong original principal, rate or date | Use **Correct… → Agreement details** and its supported signed review. Check original proceeds, later retained receipts and any settlement before confirming. |
| Incorrectly recorded financial transaction | Use the supported event correction/reversal, retaining its reason and dependency checks. |
| Actual later payment, top-up, different agreement or physical movement | Record the appropriate business action; do not label it an original transcription correction. |

Supported agreement correction retains the loan identity, genuine approval and
original agreement evidence. It appends corrected evidence and the required
compensation/recalculation, retaining actual receipt dates/amounts rather than
inventing another cash transaction. Current documents reflect the reviewed
correction; previously issued copies remain addressable.

Support depends on the saved agreement and available history. In particular,
native financial correction currently requires a supported monthly contract;
legacy native corrections are further bounded to unserviced history. Opening
agreements need their checkpoint-specific review. Linked renewals, funding,
auctions or some settlements require connected reconciliation. Do not bypass a
hold by changing the entry method, deleting history or rewriting a posted row.
See the [financial correction decision](../adr/2026-10-15-shared-agreement-financial-corrections.md)
and [implementation boundaries](../implementation/shared-agreement-financial-corrections-20261015.md).

## When the disbursal entry itself needs reversal

Reversal/re-entry remains a supported bounded route for an erroneous disbursal;
it is not the default instruction for every original agreement mistake. An
authorized administrator can reverse it from **More loan actions**, entering the
reason. Later dependent records require their supported reconciliation/reversals
first. Do not reverse genuine receipts merely to make an active loan editable.

1. After reversal, return the approved loan to draft with a correction reason.
2. Edit the amount and collateral allocations, then save.
3. Review the corrected principal, interest, deductions and net payout. Confirm
   **Review and disburse**, or approve then disburse in the separate workflow.
4. Print the ticket for the corrected approval. An earlier issued ticket remains
   part of the historical record and must not be used as the corrected ticket.

The loan keeps its number. The original disbursal, reversal and replacement remain
in its history. Balances and the active schedule use the replacement amount;
confirming again on an active loan does not create another payout. Reversal
records a correction in Rokkad; staff must also reconcile any physical cash already
handed over and the difference required by the corrected payout.
