---
status: accepted
owner: project
updated: 2026-10-06
tags: [loans, servicing, architecture]
---

# Consolidate continuation reads before servicing writers

Capture/verification, financial admission and common servicing are separate
boundaries. An admitted direct, completed-paper or imported loan is a PawnLoan.
Entry channel is provenance, not a second loan product or lifecycle. Renew now
requires an eligible active ordinary loan; a historical archive claim cannot
renew, and recording a historical renewal must not execute a present advance.

The LD-01–07 implementation established shared contract selection and factual
eligibility, but collection and exposure still select interest adapters separately.
The next boundary is a small Loans-owned, read-only continuation selector. It
resolves the frozen agreement and financial-history boundary, recorded position,
and eligible unposted interest through existing versioned calculators. Repayment
previews and exposure consume those facts, retaining different balance bases.
Legacy daily exposure remains a compatibility calculation, not collectible debt.
Opening reads never replay pre-cutover interest. Original dates, maturity, advance
coverage, per-item rounding and published profile meanings remain intact.

The recognition plan is descriptive, not authorization or an executable posting
command. Native accrual periods, recorded cumulative deltas and opening catch-up
evidence remain different persistence contracts. Existing authorized, locked,
atomic writers retain allocation, recognition, idempotency, reversal and source
identity checks. No posted amounts are reinterpreted and no data is converted.

Characterization must use real direct origination, completed-paper admission,
history/4 import and opening-review/4 admission. A manually attached import marker
does not prove admission equivalence. Equivalent continuation facts should agree;
different pre-cutover history, schedule capacity and evidence must stay visible.

Assessment freshness, transaction coverage, valuation freshness/availability and
calculation support are independent. A supported calculation can be provisional
because later paper activity is unknown. Read consolidation does not certify books
or relax borrower-notice/recovery prerequisites or send-time fingerprints.

Later work consolidates action orchestration and presentation in controlled
slices. Completed payout should be the routine retrospective entry, with tested
compatibility for genuine retained approval and reversed-origin corrections.
Latest applicable quotes need an explicitly selected maximum-age policy. The owner
subsequently selected **seven days by default, configurable by the Workspace
owner** when authorizing LC-02. LC-06 implements this prospective quote workflow;
LC-02 does not change quote eligibility, monitoring limits or retained evidence.
No daily confirmation may be fabricated. See the
[continuation plan](../plans/loan-continuation-consolidation.md).

## LC-02 forecast and evidence boundary

The continuation reader accepts an optional forecast horizon separately from its
reporting/knowledge date. Recorded debt stays at the reporting date. Supported
monthly maturity forecasts use only transactions effective through that date;
the future result cannot be used as a current collection balance. Native period,
recorded cumulative and reviewed opening calculators remain compatible adapters.
Shared-policy opening forecasts use their reviewed checkpoint, advance coverage
and subsequent known item reductions, never replaying pre-cutover history. Older
opening schedule meanings and legacy daily exposure remain compatibility reads.
The immutable repayment schedule remains allocation capacity and retains its
original maturity; its dynamic remaining-obligation view feeds delinquency and risk.

Saved risk contract V6 distinguishes calculation support and financial-history
basis alongside existing transaction and valuation evidence. Earlier V5 projections
require refresh; no financial records or posted amounts are migrated. A fresh
assessment with inconsistent financial components is excluded from monetary totals.
Missing valuation does not remove a supported financial calculation. Missing paper
coverage leaves internally inspectable calculations provisional.

Ordinary system capture remains an explicit operating assumption, not an attestation
that no off-system activity exists. Known completed-paper receipts/closures, a staff
book review, and native-contract earlier-payout evidence require coverage review.
Native origin cannot override reported missing paper activity. Per-loan reviewed
Rokkad-only continuation remains the stronger explicit future-capture choice.
Existing notice/recovery guards and send-time fingerprints remain in force.

## LC-03 settlement preparation

Release, renew-now and current auction completion share a small Loans-owned
settlement preparation service. It consumes validated continuation and retains
operation eligibility, checkpoint/schedule bounds and native financial guards.
It distinguishes completed native periods, a paired terminal catch-up, recorded
cumulative recognition and opening checkpoint catch-up. Preparation does not
authorize an action or execute a read plan. Atomic commands retain their own
permissions, aggregate/collateral locks, exact retry identities and source writers.

Supported native simple/full-month policy/2 renewal and auction completion now
recognize completed monthly periods automatically, matching repayment and full
release. Their previews include those amounts. Older frozen contracts retain the
requirement to finalize completed periods before settlement. Completed charges
remain independently owed when a terminal action reverses; the specialized action
writer couples its partial/opening catch-up to its settlement and custody reversal.
Published native reversed-period correction guards remain in place; this slice
does not invent a replacement recognition or make a retained renewal successor
disappear. Recorded cumulative and opening correction contracts remain unchanged.

Scheduled allocation remains bounded by frozen capacity. Shared monthly native
renewal/auction collections can include interest beyond the original schedule;
the full recognized collection is retained in the source event, while schedule
allocation uses only remaining capacity. It cannot replace or expand the schedule.
Policy/2 auction cash precision is paise independently of interest rounding.

Renew-now still requires actual current successor approval, current quote rules,
collateral evidence and linked carry/return records. Recording a completed paper
renewal remains a factual admission/correction workflow, not a current advance.
Auction coverage, statutory service and exact full-debt recovery remain mandatory.
No new table, migration, origination conversion or production change is involved.

## LC-04 completed-payout presentation

One visible Record completed payout action selects the existing recorded or
retained-native review from saved evidence. An earlier matching native approval,
or a fully reversed native payout after required reopen, retains native quote/
policy identities and correction prerequisites. An unpaid unapproved draft uses
actual agreement facts without fabricated approval or historical Rates. The
APPROVED unpaid adapter retains genuine approval as evidence. Commands remain
authoritative; failure never silently falls back to another admission writer.

Old earlier-payout links redirect to the canonical action; issued v1 reviews
retain compatible POST and exact retry semantics. Active/unsupported origins
require servicing or correction. Recorded/opening snapshots cannot be reissued
through the native correction adapter. Financial records are not converted.

New paper entry may explicitly map retained source licence evidence, checked
against Workspace, series/licence and original date, and frozen with reviewed
terms. Mapping is optional; unknown validity stays unknown, and missing mapping
still blocks bounded portable history rather than admission. Saved draft identity
and mapping remain unchanged. No catalogue evidence is manufactured or old loan
backfilled. See [LC-04](../implementation/completed-payout-presentation-lc04.md).
