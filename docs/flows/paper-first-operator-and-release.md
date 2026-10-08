---
status: active
owner: loans
updated: 2026-10-08
tags: [loans, paper-entry, acceptance, release]
---

# Operate and accept the paper-first workflow

**8 October shared-editor refinement:** standard paper entry shows the standing
agreement and calculated proceeds without asking for monitoring/rounding settings.
Use **Record different agreed terms** only for an actual supported exception;
check the agreement choice to unlock item rates and tenure. Without JavaScript,
use **Apply agreement choice**. For a series-wide agreement change, update dated
Economic Setup once. Missing setup has a targeted prompt rather than silently
substituted terms. Current monitoring is separate from original financial terms.

**Additional payout details** is optional and independent of term exceptions.
Blank proceeds use the agreement calculation; entered proceeds must match it.
Choose confirmed cash only when the full proceeds were physically paid to the
customer. If proceeds were used to settle another loan and net customer cash is
different, retain PROCEEDS; this field is not an arbitrary net-cash override.
Optional source-licence evidence has its own section. These choices do not establish
complete paper books, identify an unknown predecessor or perform a second payout.

**LC-05 local extension:** paper receipt preview accepts actual fee components and
complete staff item principal splits for multi-item openings. Use the actual
receipt timestamp for a same-day transaction after a precisely timed checkpoint;
date-only checkpoints still start servicing on the following day. Current payments
retain their normal allocation priority. Multi-item archive reconciliation compares
every retained item and known source claim before admission.

An owner can choose **Record a verified closed position** from the completed-payout
editor when the original agreement and zero closure are established but earlier
receipts are incomplete. Review and confirm the actual items, dates, terms and
custody evidence. The result is an ordinary closed loan, with no invented payout,
receipt or settlement. Unknown handover stays unknown and pre-closure totals stay
unavailable. Disputed or missing terminal facts stay in the retained archive.

Delegated importers can stage supported evidence and **Save preparation for owner
review**. Only the owner performs financial preview/commit; changing preparation
invalidates an old approval. See the
[delivery record](../implementation/bounded-loan-evidence-lc05.md) for supported
profiles, entry points and portability checks. There is no automatic archive
conversion or production rollout.

**LC-04 local extension:** a saved draft has one **Record completed payout** action.
It selects the paper editor or retained native review from saved evidence. Genuine
earlier approval and fully reversed native payout corrections retain their quote,
policy, reason, authority and dependent-reversal checks. Old earlier-payout links
redirect to the same action; active origins require their correction workflow.
New paper entry optionally selects **Source licence evidence** under additional
details, when known. It must match the series/licence and original date. An inactive
legacy reference preserves unknown validity. Blank evidence does not prevent
recording, but full portable history still requires that mapping and its other
coverage/profile checks. Saved drafts keep their original mapping.

**LC-03 local extension:** full release, renewal performed now and current auction
completion share settlement preparation. Modern shared-monthly native loans no
longer need a separate completed-period finalization step before renewal/auction;
eligible charges recognize atomically with the action. Older contracts retain their
finalization requirement. Renewing now still requires current successor approval;
recording a renewal already completed on paper still preserves its actual facts.
Existing book-review, statutory, custody and correction restrictions remain.

**LD-02 local extension:** repayment purpose describes this receipt, independently
of how the loan began. A supported native shared-monthly flexible/single-payment
bullet loan can use Record a paper receipt with actual date, reference and item
principal split. A paper/opening loan can use ordinary collection for money received
now. The saved contract and actual transaction date determine debt. Unsupported
contracts, later activity and allocation limits give a blocker before posting.
Reviewed openings still support completed paper principal payments against only
one outstanding item; current digital collections retain highest-rate-first
allocation. No arbitrary allocation is inferred to overcome that profile limit.

Supported ordinary loans can record completed paper closure, retaining an unknown
handover as PAPER_CLOSED until a separately evidenced return. Full settlement needs
no metal quote or appraisal; partial release still requires valuation. Native
shared-monthly full release recognizes completed charges during settlement,
without a separate finalization task. Paper receipt/closure entry does not establish
whole-book completeness, even when the original loan was created directly.
Check paper transactions remains a separate optional review; borrower reminders
retain coverage checks. Broader source corrections and reduced-principal opening
admission remain later slices. This is local implementation, not deployment.

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

Use Close / release loan and select Record a settlement already completed for the
actual closing date and exact settlement. The same screen supports current collection
and return, irrespective of origination. See the [individual and bulk guide](paper-closure-transition.md). Leave
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

For a current auction of an overdue recorded-origin loan or supported reviewed
opening, confirm complete activity through today and use ordinary Initiate auction.
An explicit Rokkad-only transition can retain that coverage as described below.
Existing statutory readiness,
authority, actual service and vault-custody checks still apply. Completion uses
agreed anniversary debt and requires exact full recovery. Coupled reversal restores
that debt and custody; paper/mixed recording requires a fresh active-book check.
Reviewed openings retain their checkpoint and coupled interest catch-up.
Historical sales, shortfall/write-off and surplus distribution are not
enabled by this adaptation.

## Optional move to future Rokkad-only capture (LD-06)

Open the individual loan's **Check paper transactions** screen. Verify every
transaction through today against the source records (from cutover for an opening).
Choose **All transactions through this date are entered**. If all future activity
for this loan will be entered directly in Rokkad, select the corresponding future
recording choice, preview and confirm the signed review. This requires an active
supported loan and today's review; it changes no money, interest or collateral.

Leave **Paper or mixed capture** selected while business still happens on paper.
The ordinary batch book check continues checking coverage only. Nothing switches
because a loan was imported, originated on paper or received a recent current payment.

After the explicit transition, supported current transactions keep coverage current
without repeated book checks. Entering another completed paper transaction,
correcting historical activity or changing the agreement requires another check.
Review starts with paper/mixed as the default; choose the future mode deliberately.
Monitoring still needs fresh current valuation and risk assessment. A reminder queued
before a payment remains stale even though capture is complete: reassess/review its
current amount to prepare a replacement. Old portable exports hold capture/auction
evidence until wider profiles exist; retain exact Workspace recovery backups.

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
