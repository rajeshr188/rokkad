---
status: complete-local
owner: loans
updated: 2026-10-06
tags: [loans, continuation, settlement, lc-03]
---

# Shared settlement preparation

LC-03 follows the locally completed LC-01 continuation reads and LC-02 forecasts.
`services/settlement_preparation.py` supplies current settlement facts for ordinary
full release, renew-now and auction completion. It validates the same servicing
contract and chronology, then uses the existing continuation adapters. No new
financial model, table, evidence profile or migration is introduced.

## Amount and posting boundaries

Preparation separates recorded debt, completed native periods and paired terminal
catch-up. Recorded cumulative recognition is included in its collection balance;
opening catch-up starts at the accepted checkpoint. Native period previews use
their saved item principal/rates, advance coverage and policy rounding. Legacy
period calculation remains a compatible fallback, with its completed-period
finalization prerequisite.

Modern native simple/full-month renewal and auction automatically recognize
completed monthly periods during the authorized atomic command. This matches
repayment/full release and removes an entry-channel discrepancy, including a
completed first period entirely covered by advance interest. The action-specific
writer still posts its paired partial/opening catch-up and settlement. Completed
native charges remain independently owed on reversal. Cumulative recorded and
opening recognition use their existing evidence identities and writers.

The internal recognition helper recomputes facts under the caller's aggregate lock;
it does not execute a supplied read plan. Book coverage is checked before derived
recognition changes the event prefix. Facts are recomputed afterward inside the
same command without requiring staff to certify the command's own new interest
events. Auction source evidence retains the original coverage check. No later
external receipt is allowed to bypass coverage or chronology checks.

Opening servicing explicitly reads original schedule allocation capacity with
`adjust_recorded=False`; LC-02's dynamic future debt is for risk/delinquency. Full
release, renewal and auction cap scheduled interest allocation while retaining the
whole actual collection in the immutable financial event. Shared-monthly native
renewal/auction use the same cap as full release when debt extends beyond maturity.
Neither the schedule nor the accepted opening is enlarged or rewritten.
Policy/2 auction cash precision is paise, independent of interest rounding.

## Retained action contracts

Release retains numbers, cash/concession reconciliation, collectors, physical
verification, actual handover, storage removal and paired reversal. Current renewal
retains successor approval, quotes, exact preview fingerprint, immutable source
settlement, principal allocation, retained/returned items and linked custody.
Completed paper renewal remains a separate recording purpose and is not executed
as a current lending decision. Auction retains administrator authority, complete
transactions, statutory evidence, in-vault custody and exact full-debt recovery;
shortfalls and surplus distribution remain unsupported.

Published correction restrictions are deliberately preserved: recorded-history
release needs its complete history review; retained native reversed monthly periods
require review rather than silent replacement; a reversed renewal retains its
successor relationship. Reversal restores financial/custody effects through existing
compensating records, not deletion of the original action. Opening renewal catch-up
reversal now retains the exact source amount spelling, matching the immutable
opening pairing guard and existing release/auction reversal writers.

## Verification

`test_settlement_continuation.py` exercises real direct origination, completed-paper
admission, history/4 import and opening-review/4 admission. It compares 5 May,
6 May and 6 June settlement quotes after an April principal reduction, with a first
month paid in advance. Single/multiple items and paise/whole-rupee policies use the
same facts. Terminal command tests exercise full release, current successor
approval/renewal and overdue auction with real synthetic statutory evidence.
They check failed-command rollback, retries, source immutability, custody,
cutover/restricted-role isolation and the retained reversal restrictions.

All **14 settlement tests** pass in the final run. The affected existing suite
runs **541 tests** (649.203s): 539 pass; two exact-recovery tests encounter PostgreSQL
deadlocks. Both pass on isolated rerun with no recovery-business-code change. The
final **29 checks all pass** (77.446s), comprising those two recovery cases, the 14
settlement tests and partial-month policy checks, including a new explicit
completed-period-finalization case. No single clean 541-test rerun is claimed.
Django checks, no model/migration drift, 34 changed/new Python parses and repository
whitespace checks pass. Evidence is retained privately under `.tmp/lc03-20261006/`.

All evidence is synthetic local QA; no production/source-book acceptance, deployment,
historical conversion or prospective quote-age change is included. LC-06 retains
the owner's seven-day configurable quote-age decision.
