---
status: active
owner: loans
updated: 2026-10-03
tags: [loans, paper-entry, acceptance, release]
---

# Operate and accept the paper-first workflow

Use ordinary **New loan** for each original numbered paper agreement. Select the
series and check **Entry: From paper**; use the compact Change control for an
exception. The ordinary Series field supplies the entry default, without another
series chooser. Switching retains typed facts and purpose-specific details; with
JavaScript, selected photographs are retained when returning to direct entry.
Without JavaScript, use Apply entry choice after selecting the series and reselect
photographs after a purpose change. Changing purpose saves no loan and removes
any old paper review, so review the final facts again.

A standing purpose default can be selected in economic setup at
Workspace, license or series scope; the most specific explicit choice wins. Staff
can switch to Create and pay now for this action. Record the borrower, original
date/number and book/page reference. Add each collateral item with its actual
principal; Rokkad adds these amounts to the loan total. Each item retains its own
agreed monthly rate. Select the series to load its dated standing
monthly rate, tenure, advance interest and document charge. Lakshmi's confirmed
standard tenure is 12 months; configure it in ordinary economic setup, with the
effective date when that agreement actually applied. Review the
calculated deductions and proceeds. Use Different paper terms for a supported actual
exception or absent dated digital setup, with a source explanation. Confirm physical
cash only when established; paper
proceeds alone do not establish how money moved. Current monitoring selection
assesses held collateral separately from the original decision. Do not reconstruct
an unknown predecessor or apply today's prices to an already agreed principal.

Review and confirm the displayed transaction facts. Optional paper-book verification
records a separate checked-through claim; routine entry does not require it. The ordinary Loans list then contains
the active or reconciled closed loan. Use Repayment for a later total-only receipt,
keeping its actual date and source reference. Interest is applied first, principal
second. For multiple items, enter the principal paid against each item; the split
must match the principal remaining after interest, without exceeding any item's
balance. An interest-only receipt needs no principal split. Rokkad does not apply
direct entry's highest-rate-first allocation to a paper receipt. A mid-month principal reduction changes interest from the next loan
anniversary; that month's charge uses its earlier principal. Missing earlier
receipts affecting existing later activity require Review paper history correction.

Use Record paper closure for the actual closing date and exact settlement. Leave
the original closing number blank when none was written: the system assigns and
labels a recording number. Choose whether the physical return is established.
Financial closure with unknown handover stays closed financially and retains a
custody warning. Later confirmation records the actual recipient/date/reference
without another receipt or a rewritten original release. Original issued copies
remain available; a new copy includes the later confirmation.

If a paper loan's relationship to another agreement is unknown, enter each loan
independently. If the source loan is already entered and the relationship is known,
use ordinary Renew: choose a decision performed now or an already completed paper
renewal. A current decision requires current approval. The optional already-completed linked paper renewal is currently limited to one
collateral group; enter multi-item paper agreements independently. A supported
known paper renewal uses its actual successor principal/terms, deductions and net cash. For example,
12,000 − 240 − 10 − 10,000 − 200 = **1,550 paid to the customer**. Retained jewellery
is linked and relabelled. Imported opening loans also support these two renewal
purposes, preserving the accepted opening balance and unavailable earlier history.

Use Paper-book progress to track books/pages/dates. It is a work queue, not a
balance certification. Review selected loans together only after checking each
against its source. Each receives its own dated completeness confirmation. Later
activity, corrections or an active loan's later date can require another review.
Risk monitoring continues to show current valuation and calculated exposure, with
known totals and provisional/unavailable counts. Ordinary viewing, receipt entry and
closure do not require daily per-loan book certification. Explicit missing activity
still needs reconciliation; reminders and recovery retain coverage checks. A current price cannot make
an incomplete transaction history complete.

Correct transcription errors through the original-term or closing-fact review,
with actual source references and reasons. Signed previews reconcile balances,
receipts, affected successor settlements and retained custody before posting.
Original evidence survives. These commands do not represent a renegotiation,
invented waiver, capitalized unpaid interest or physical reversal. Unsupported
shared-batch date/custody changes need separate reconciliation.

For a current auction of an overdue recorded-origin loan, confirm paper activity
through today and use ordinary Initiate auction. Existing statutory readiness,
authority, actual service and vault-custody checks still apply. Completion uses
agreed anniversary debt and requires exact full recovery. Coupled reversal restores
that debt and custody; recheck the active paper book afterward. Imported-opening
auctions, historical sales, shortfall/write-off and surplus distribution are not
enabled by this adaptation.

## Real-record acceptance

Before rollout, staff must reconcile actual representative Lakshmi records:

| Example | Acceptance result |
| --- | --- |
| Outstanding original paper loan | Original date/number/principal/deductions match; correct current interest and held collateral |
| Total-only partial receipt | Actual received total matches; interest/principal split and next-anniversary charge match the book |
| Closed loan, no original closing number | Exact settlement; labelled system recording number; zero current exposure |
| Unknown handover, later confirmed | No invented physical return; dated confirmation adds custody only; old document bytes remain |
| Independent old/new agreements | Each numbered loan recorded once; no guessed predecessor |
| Known subsequent renewal with reduction or top-up | Source clears; successor principal/deductions and actual cash match; held collateral linked |
| Incorrect original term or receipt | Reviewed compensation/replay; old facts preserved; current balance and coverage status explain correction |
| Monitoring and reminder | Current price and paper cutoff shown separately; incomplete history blocks borrower reminder/recovery intent |
| Imported opening renewal | Cutover and old obligations preserved; current successor approved or actual paper terms retained |

Record the source reference, expected figures, actual result, staff reviewer and
acceptance date. Fictional automated/browser checks establish implementation
behavior; they cannot certify a real paper book. Additional real fee, partial-period,
multi-item, waiver or capitalization arrangements need their actual terms before
expanding the profile. Do not invent rules from an unexplained total.

## Recovery and release

Paper-book progress links **Loans recovery backup**. The native ZIP retains the
whole ordinary-Loans inventory, including source identities, correction/renewal
graphs, reviews, custody, archive evidence and application file copies. Its filename
contains the SHA-256: retain that checksum separately and store the archive privately.
This is original-identity recovery; it cannot move/merge loans into another Workspace.
Party, actors, Rates, control-plane and portability prerequisites require their
matching full database/media recovery. The archive does not copy external original
source buckets or substitute for those backups. Export briefly locks ordinary-Loans
tables for a consistent capture; schedule a quiet operating window for a large book.

Operators can also run `python manage.py pawn_recovery export --workspace SLUG
--actor USER_ID --file PRIVATE.zip` using the applicable runtime settings. Restore
is an offline owner connection in a recovered environment with matching schema,
guard definitions and original identities, and empty ordinary-Loans tables:

```powershell
python manage.py pawn_recovery restore --workspace SLUG --actor USER_ID --file PRIVATE.zip --sha256 RETAINED_SHA256 --settings django_project.settings.migration
```

The preview performs a real restore/reconciliation and rolls back. After reviewing
its result, commit repeats the command with `--commit --confirm-workspace SLUG`.
Existing rows, missing prerequisites, checksum/guard mismatches and conflicting
media refuse restore. Do not run this on an operating Workspace. Runtime users
cannot disable evidence guards or perform native restore.

The release target and real-record acceptance remain to be supplied by the owner.
Freeze and review only the selected adaptation changes against that target's image,
because the shared checkout also contains unrelated work. Retain full database/media
and matching-image backups, rehearse the owner-only migrations and native restore,
then use `python manage.py migrate --settings django_project.settings.migration`.
Web/worker processes keep the restricted runtime role. Verify native JCL/JSK
origination/printing and Lakshmi's accepted examples on the target. No existing
loan, historical archive or book completeness is automatically converted or certified.
Rollback after new financial writes requires retained-data recovery and explicit
reconciliation; do not discard events by rolling schema backward.
