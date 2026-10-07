---
status: active
owner: project
updated: 2026-10-07
tags: [loans, continuation, inventory]
---

# Continuation inventory and first consolidation

This is a source-code inventory, not a production cohort audit. The owner selected
capture/verification → financial admission → common servicing. Existing LD-01–08
deliveries remain useful, but do not mean every read/writer branch is consolidated.

Classification: **agreement** means genuine saved calculation/allocation semantics;
**checkpoint** means the lower bound of known financial history; **posting** means
source recognition, allocation, custody or reversal persistence;
**compatibility** means a published old evidence/calculation contract;
**dispatch** means duplicate selection that can be centralized without changing
those contracts. A branch can have more than one reason.

| Surface / source | Classification | Finding / treatment |
| --- | --- | --- |
| `selectors/servicing_contract.py` | Agreement, checkpoint, compatibility | Validates one supported origin, frozen policy/profile and opening bounds. Legacy unknown policy fields stay unknown. Entry channel is not authority. |
| `selectors/exposure.py` and collection reads | Dispatch; agreement for legacy daily forecast | LC-01 centralizes unposted-interest selection with `selectors/continuation.py`. Recorded debt, eligible collection and risk exposure stay distinct. The former daily projection moves unchanged to a compatibility reader. |
| `services/pawn_repayment.py:151` | Posting, checkpoint, agreement | Native period rows, recorded cumulative recognition and opening catch-up use different evidence. Supplied paper item splits versus current highest-rate-first are actual allocation semantics. Keep writers and conservation checks. |
| `services/pawn_release.py` | Posting/checkpoint/compatibility; consolidated preparation | LC-03 common settlement preparation selects native, cumulative or opening facts. Release evidence, catch-up coupling, return timing and reversal dependencies remain specialized. |
| `services/pawn_renewals.py` | Posting/checkpoint/agreement; consolidated preparation | LC-03 shares source debt, completed recognition and frozen schedule capacity. Modern native completed periods recognize automatically. Current successor economics/approval and collateral carry remain lending decisions; completed paper renewal remains factual recording. |
| `services/pawn_auctions.py` | Posting/checkpoint; consolidated preparation | LC-03 shares preparation/recognition and caps allocation by original capacity. Transaction coverage is checked before command-owned recognition changes the prefix; notice/custody/legal and exact recovery guards remain. |
| `selectors/obligation_state.py:201` | Dispatch, agreement | LC-02 uses continuation for supported monthly native/recorded/shared-policy opening forecasts, capped at reporting-date knowledge. Original schedule capacity/maturity stays immutable. Four real admission paths agree after later reductions in single/multiple-item, paise/whole-rupee tests. Earlier opening schedule semantics remain compatible. |
| `selectors/delinquency.py:44` | Checkpoint, compatibility | Opening grace and schedule retain their reviewed source. Remaining/due/overdue projections now consume shared continuation through obligation state. Schedule versus old event-fold interpretation variance stays disclosed; no original-to-cutover replay. |
| `selectors/risk.py:54`, `services/risk_snapshots.py` | Evidence quality | LC-02 V6 stores calculation support and financial-history/principal basis alongside independent coverage and valuation. CURRENT means assessment freshness, not certified books. Prior V5 requires refresh without a finance migration. |
| `selectors/risk_portfolio.py:96` | Evidence quality | LC-02 discloses freshness, books, valuation and support in portfolio/dashboard, reports, position exports and repayment previews. Provisional and assumed-capture counts remain independent of unavailable valuation; inconsistent money is excluded from portfolio totals. |
| `services/notice_delivery_readiness.py` | Posting-adjacent safety, evidence quality | Notice amount uses shared servicing position. Coverage and source fingerprints are checked again at send, together with current risk, consent, recipient and frozen message. Keep those guards; no delivery is authorized by supported arithmetic. |
| `services/pawn_notices.py:257`, risk-notice readiness | Compatibility, evidence quality | Existing send-time/readiness guards remain. LC-02 identifies native-contract earlier-payout evidence as paper activity requiring book review. SYSTEM_RECORDED is expressly an ordinary-capture assumption, not absent-paper proof; native origin cannot override staff-reported missing activity. |
| `documents/payloads.py:258` | Dispatch plus agreement/compatibility/presentation | Khata/statement breakdown still calls recorded calculation directly. Frozen original documents must preserve original facts; current amount reports should later consume common continuation and disclose provisionality. |
| `services/history_export.py:44`, `opening_export.py:108` | Compatibility, checkpoint, posting | Published schemas retain different evidence graphs and admission capabilities. Shared serving must not discard portable source identity, supported profile or missing prehistory. Servicing ZIP remains graph/bytes recovery, not a generic JSON import. |
| `services/completed_payouts.py`, `historical_origination.py`, `loan_workflow.py:106` | Compatibility; consolidated presentation | LC-04 exposes one completed-payout action selecting recorded or retained-native review. Old GET links redirect, issued POST reviews/retries remain compatible. Genuine earlier approval and fully reversed native payout retain their evidence/authority checks. Recorded/opening graphs cannot use native reissue. |

## First boundary

`resolve_loan_continuation` validates the frozen contract, reads the recorded event
position, then selects existing native-period, recorded-cumulative or opening
checkpoint calculation evidence. Its descriptive recognition plan retains periods,
unposted amount, collection eligibility, adapter evidence and projection rule.
Repayment/notice amount reads and exposure now consume it. Servicing still applies
its operation-specific chronology and schedule checks. Descriptive plans are not
reused for posting without recomputation under an authorized locked command.

There is no new finance table or formula engine. Native accrual rows/lines,
recorded cumulative recognition, opening catch-up evidence, principal allocation,
future-known-through forecasts and coupled reversals remain with existing writers.
The full desired continuation interface (allocation/evidence summaries, forecast
support and explicit quality presentation) is deliberately incremental.

## Confirmed limits versus questions

Confirmed in code: multiple outstanding opening items block **paper principal**
allocation under the published profile; fee allocation lacks an agreed paper rule;
archive claims do not gain ordinary servicing until admitted; closed admission
with incomplete receipt history is not a generic current settlement; opening
servicing must be strictly after cutover. These are explicit supported-evidence
limits, not reasons for another permanent loan lifecycle.

The paragraph above records the LC-01 checkpoint. LC-05 subsequently supports
explicit actual paper item splits and fee components, and reviewed opening/5
supports evidenced same-day ordering. LO-04 aligns opening replay with ordinary
receipt acceptance of omitted zero item amounts, retaining complete allocation
lines and conservation checks. It also discloses saved legacy rounding and current
continuation holds separately in the interest-contract inventory. The native
reversed-monthly-charge hold remains an explicit unresolved correction integration,
not a reason to silently drop or repost interest. See the
[LO-04 verification and disposition](origination-servicing-compatibility-lo04.md).

Confirmed while constructing real admission fixtures: completed-paper history
admission through `admit_recorded_history` can lack a licence revision and its
history/4 export then rejects that missing
mapping. LC-01 uses an independently supplied supported history/4 source document;
it does not invent a revision to make that export succeed. LC-04 adds an optional
explicit existing-revision mapping for new paper entry, with scope/date validation
and frozen review. Existing drafts/loans are not backfilled. Unknown mapping still
permits admission and blocks portable export truthfully.

Opening pre-cutover repayment counters are not equivalent to complete history;
they remain unknown rather than invented. Exposure's existing opening
`original_principal` field uses the opening-position principal, whereas complete
origination uses disbursed principal. LC-02 adds explicit checkpoint/history basis
to risk provenance and ordinary presentation/position exports, alongside future
remaining-obligation forecasts. LC-01 compares actual current
debt and risk inputs without claiming identical historical counters or valuations.

Still hypotheses requiring production evidence: which live contracts can be
continued safely, how much old closed history can be admitted without invented
receipts, and whether all affected views explain provisional balances adequately.
Synthetic equivalence does not answer those questions. The owner selected quote
maximum age seven days by default, configurable by the Workspace owner, when
authorizing LC-02. Implementation remains LC-06; current approval checks are unchanged.

## Completed-payout compatibility trace

The current source paths establish these distinct cases for LC-04:

1. **Unpaid draft, no approval or financial origin:** completed payout reuses its
   loan/number/item identities and verifies actual terms through recorded admission.
   Historical digital quotes are not required. `completed_payouts.apply_actual_contract`
   is the existing adapter; do not create another loan.
2. **Unpaid draft with genuine retained approval, no financial origin:** the same
   completed adapter binds review to approvals and issued documents and rejects
   changed actual/frozen terms. Existing `test_completed_payouts` covers retained
   approval/policy/documents and incompatible facts. Keep the original evidence.
3. **Fully reversed native disbursal, draft again:** general completed admission
   rejects any financial graph. The earlier-payout adapter explicitly admits only
   native DISBURSAL/REVERSAL history with no unreversed payout; historical basis
   prefers the original eligible approval and frozen quote/policy identities. Its
   signed review, dependent-reversal checks and authorization must survive UI
   consolidation. `test_earlier_payout` covers original-quote preference, corrected
   earlier payout, duplicate replay, stale review and lack of setup authority.
4. **Existing active origin or other dependent graph:** this is servicing or an
   explicit history correction, not new payout admission. Never redirect it into
   the general unpaid-draft writer or silently create a second origin.

The LC-04 unified action selects the compatible adapter from verified saved
facts rather than asking staff to choose two similar retrospective actions. Keep
old endpoints as compatibility links/redirects when their review contracts allow;
reversed-origin requests retain their existing specialized review, not a blanket
redirect into `require_unpaid_draft`. LC-04 adds HTTP transition/redirect, retry,
stale-source, actor and Workspace checks before removing the competing visible
action. The service and POST endpoint remain compatibility contracts.

## Borrower-facing and recovery prerequisites

Borrower communication requires a supported collectible position, up-to-date
transaction review where assigned, current risk evidence, appropriate consent and
recipient/template/provider readiness; preserve source/amount fingerprints at send.
Auction recovery additionally requires operational/legal notices, custody and
transaction coverage under existing commands. Internal provisional monitoring can
continue without certifying missing paper transactions. Admission channel must not
be a shortcut around either class of prerequisites.

Validation results are recorded in the [plan](../plans/loan-continuation-consolidation.md)
and [Status](../STATUS.md). No production changes are authorized by this inventory.
