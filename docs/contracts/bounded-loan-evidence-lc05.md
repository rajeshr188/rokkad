---
status: active
owner: project
updated: 2026-10-06
tags: [loans, contracts, evidence]
---

# LC-05 bounded evidence contracts

These extend existing admission and servicing records. Earlier versions retain
their original meaning; no stored record is upgraded or retrospectively rewritten.
See the [decision](../adr/2026-10-06-bounded-loan-evidence-extensions.md).

| Profile | Meaning |
| --- | --- |
| `paper-repayment/2` | Actual fee component and/or actual aware receipt timestamp, alongside the existing receipt reference, total and optional staff item split. |
| `opening-payments/2` | Opening continuation with an explicit paper fee/item allocation or checkpoint-day timestamp. Paired recognition/reversal remains validated. |
| `archive-admission/2` | Complete reconciled admission of several source collateral items. Each supplied item corresponds to the retained source order. |
| `loan-opening-review/5` | Review/4 period bases, balances and advance coverage plus an actual checkpoint timestamp. |
| `loan-opening-export/4` | Export/3 row inventory supporting review/5 or opening-payments/2. |
| `loan-import-preparation/1` | Staged source and destination preparation, explicitly not financial admission review. |
| `loan-terminal-admission/1` | Verified original agreement and zero closed position, with incomplete earlier transaction history. |
| `archive-terminal-admission/1` | The same terminal position, bound to immutable archive snapshots. |
| `loan-terminal-evidence/1`, `loan-terminal-review/1` | Sole zero-valued migration opening and its frozen terminal review. |

## Receipt allocation

An outstanding fee balance requires the paper receipt's actual `fees_paid`,
including explicit zero. It cannot exceed the receipt or outstanding fees.
The remainder pays overdue/current interest and then principal. Current payments
retain fees-first and highest-rate-first principal allocation. A paper principal
payment across several outstanding opening items requires the staff's complete
item split, reconciled to the principal component and each item's capacity.
No split or fee priority is inferred from a total-only receipt.

Readers validate explicit components against posted amounts, allocations and
source metadata. Export/restore remaps item identifiers while preserving amounts.
The general servicing bundle retains these nested profiles and original evidence.

## Precise opening checkpoint

Review/5 requires `cutover.occurred_at`: an aware actual timestamp on
`cutover.date` in the declared timezone, no later than now. Review/1–4 remain
date-only checkpoints: servicing starts strictly after that date.
Same-day review/5 activity must occur strictly after the checkpoint and existing
activity. Current actions use the actual command clock; paper receipts require
their actual source `received_at`, matching the continuation timestamp.
Paired recognition and reversal can share their operation timestamp.
Date-only paper closures/renewals do not gain same-day eligibility.
Restoration retains the original action timestamps rather than using its clock.

## Closed position and unavailable history

Terminal admission verifies the supported original agreement, actual item
principals/rates, original date/tenure/rounding, closure date/reference and zero
principal, interest and fees. It creates one ordinary CLOSED loan and one
zero-valued opening checkpoint. The positive original agreement principal is
descriptive; it is not a payout or an outstanding opening balance.

There are no fabricated disbursals, approvals, receipts, settlement, schedule or
handover events. Known return is retained as source custody; unknown handover
remains `PAPER_CLOSED`. Earlier receipt/payout totals and pre-closure financial
positions remain unavailable. Book coverage is `TERMINAL_POSITION`, not complete.
Database guards prohibit subsequent financial events or reopening the loan by
reversing a settlement that was never recorded. Complete history admission remains
available when actual receipts reconcile. Retained archives and attachments remain
immutable; incompatible snapshots block admission. There is no automatic conversion.

## Preparation versus admission

Active members with `data.view` and `data.import` can upload/stage supported
evidence and prepare existing scoped mappings. Preparation creates no loans,
financial events, catalog definitions or customer bindings. Changes invalidate a
previous approval. The Workspace owner (or authorized platform override) still
performs financial preview and final commit with the existing action permissions,
source identity, stale-review, numbering and atomicity checks.
