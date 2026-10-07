---
status: awaiting-owner-review
owner: project
updated: 2026-10-07
tags: [loans, origination, acceptance, release]
related: [../plans/loan-origination-completion.md, ../flows/loan-continuation-release-acceptance.md]
---

# LO-05: real loan comparison and staff review

## Result and acceptance boundary

The representative source comparison pack is prepared. Current loan code reads
four real loans from the approved isolated copy, renders their authorized detail
pages and relevant repayment/release forms, and projects their document values.
All reads succeed under the restricted runtime role and a PostgreSQL repeatable-read,
read-only transaction. No-context and cross-Workspace reads remain isolated.

On 7 October the owner volunteered to review RA00500 and D01623 and confirmed
that JCL/JSK loans created after 25 September were created and paid in Rokkad.
That identifies the reviewer and sample cohort; it is **not completed acceptance**.
Actual book comparisons and staff workflow results remain pending. D01623's
previously confirmed terms are retained below without requesting them again.

No production correction, book-review confirmation, risk refresh, document issue,
financial posting or deployment occurred. This slice currently changes documentation
only; existing commands provide the inspected behavior.

## Comparison basis

- Application source: `d89f32f557b0daafdd9eddca0ef884de32c1a7c6` (LO-04).
- Source: approved 6 October server-only production copy, migrated for the
  candidate and explicitly corrected for D01623 in LO-01.
- Reporting date: **7 October 2026**; final capture **12:40:29 IST**.
- Source overlay: 756 current Loans Python/template files verified by SHA-256,
  mounted read-only over the earlier pinned staging image. Other applications
  remain from that image. This is a bounded diagnostic, **not an exact clean
  candidate build or full browser certification**.
- GET rendering uses real Workspace owner access checks. A static URL storage
  override avoids the earlier image's missing current manifest. Asset execution,
  photo availability, issued PDF bytes and media recovery are not certified here.
- Source rows, rendered customer HTML, hashes and the exact probe remain in the
  approved private server directory. No borrower identity, photos or rendered
  customer documents were copied into local OneDrive or committed.

The balances below calculate 7 October against the **6 October snapshot**. They
do not establish that later off-system or production activity has been captured.
Confirm any activity after the snapshot before relying on a live balance.

## Real-source comparison sheet

Amounts are rupees. Advance interest and document charge are deducted at payout.

| Workspace / loan | Original agreement | Saved payout or checkpoint | Position calculated for 7 October | Owner comparison |
| --- | --- | --- | --- | --- |
| JCL **RA00500** | 2 September; principal 60,000; 2% monthly; 3 months | Imported opening effective 24 September; earlier receipts are not reconstructed | Recorded debt 60,000; collection 61,200: principal 60,000 + interest 1,200; one item in vault | Compare original register and cutover position, including whether any later payment is missing |
| JCL **C07557** | 26 September; principal 8,170; 2% monthly; 3 months | Advance 163.40; document charge 10; net payout **7,996.60** | Active; principal/collection 8,170; interest and fees zero; one item in vault | Compare the original Rokkad payout/ticket, item amount, deductions and actual amount paid |
| Lakshmi **D01623** | 24 September; principal 2,100; 4% monthly; **3 months** | Advance 84; document charge 10; paper payout **2,006** | Corrected staging loan active; principal/collection 2,100; no receipts/closure in snapshot; one item in vault | Terms already confirmed by owner; review corrected presentation and report any subsequent activity |
| JSK **06716** | 29 September; principal 600; 2% monthly; 12 months | Direct payout: advance 12; document charge 10; net **578** | Paper closure **6 October**: principal 600, interest 0, fees 0, total **600**; closed debt zero; one item with customer | Compare original ticket and closing book/receipt, including actual return of collateral |

The candidate search found 160 JCL and 130 JSK active/closed loans with dates after
25 September and a live disbursal, excluding migration openings. In this dated
cohort, neither Workspace has a repayment event; JCL has no release and JSK has
five releases. C07557 is the first eligible JCL sample; 06716 is the first eligible
JSK release sample. These are snapshot counts, not today's production totals or
an assertion that no paper receipts exist outside Rokkad.

There is no actual partial-repayment example in this selected cohort. Mixed-rate
interest-first receipts with staff principal splits are technically covered by
LO-04. A real receipt can supplement acceptance when available; none was invented
for this pack.

## What the technical comparison establishes

RA00500 retains `original-anniversary-upfront-inclusive/2`, aggregate whole-rupee
half-even rounding and a 24 September opening boundary. Its earlier financial
history is unavailable. The computed 1,200 interest is a candidate result for
the owner to compare, not an attestation of the register.

C07557 and 06716 retain `native-event-fold/1`, paise half-up per-accrual-period
semantics. Existing loans are not silently converted to a newer contract.
D01623 uses `recorded-anniversary/3`, paise half-up per item/anniversary: no new
interest through **24 October**, followed by **84 on 25 October**. Its actual
paper date, three-month tenure, deductions and proceeds match the confirmed facts.
The retained payout/reversal IDs 19388/19390 remain present. Production D01623
remains the uncorrected draft; the active corrected record is staging-only.

All four detail GETs return 200. The three active loans' repayment and full-release
GETs return 200. Direct and paper New loan in the selected JCL/Lakshmi series
render the shared routine editor. JCL is SIMPLE and exposes Review loan; Lakshmi
is EXTENDED, so current lending exposes Save draft and the existing separate
approval/payout operations. Paper exposes Review loan record in either Workspace.
This difference comes from the configured workflow, not paper provenance.

The selected series currently resolve to **DIRECT**, including Lakshmi, in this
snapshot. Paper entry must be selected explicitly unless the owner changes the
standing entry setup. The diagnostic did not change setup or assume Lakshmi's
operating model automatically overrides the saved setting.

Native ticket, recorded contract and JSK release-memo projections read successfully.
The recorded contract carries D01623's 84/10/2,006 values; the release memo carries
06716's 600/0/0/600 settlement and 6 October date. These are document projections,
not proof that the corresponding stored PDF, photograph or printed copy opens.
Opening RA00500 is not passed through a new original-payout ticket workflow.

## Monitoring and action dispositions

| Loan | Read-only current monitoring calculation | Saved assessment / book position | Disposition |
| --- | --- | --- | --- |
| RA00500 | Collateral value/LTV unknown; `MISSING_APPRAISAL`; HIGH priority review | Saved assessment unassessed; books unconfirmed | Add an applicable dated appraisal, compare books and refresh Loan health before relying on coverage or reminders |
| C07557 | Eligible value 11,625; monitoring LTV 74.50%; MEDIUM / LTV warning | Saved assessment unassessed; system-capture assumption | Monitoring can evaluate the active direct loan; refresh the saved assessment and review paper activity if any occurred |
| D01623 | Eligible value 16,256.25; monitoring LTV 13.95%; LOW, transactions unconfirmed | Saved assessment unassessed; books unconfirmed | Financial calculation works independently of original digital approval; current book position still needs an actual review |
| 06716 | Closed; no active-loan monitoring projection requested | Books unconfirmed because closure was recorded from paper | Closed balance and custody are browsable; ordinary new collections/releases/renewals/auction are refused |

Monitoring LTV uses forecast exposure, so it is not current collection divided by
collateral value. The on-demand risk calculations above **do not refresh the saved
assessment**. Saved valuation quality remains UNASSESSED; it must not be described
as current simply because a selector can calculate today's estimate.

Common factual prerequisites for repayment, full release and renewal are clear
on the three active samples. That does not authorize or guarantee a final action:
the ordinary command must still validate permissions, availability, allocation,
settlement, successor evidence, custody and retries. Auction coverage is held on
RA00500/D01623 until books are confirmed; C07557's clear common prerequisite does
not bypass statutory notice/auction requirements. No action was submitted.

JSK 06716 demonstrates that origination and later recording purpose are independent:
a native loan can have a completed paper closure without becoming another kind of
loan. The memo/record claim return; only the actual source/staff comparison can
confirm that physical jewellery was handed back.

## Owner's workflow walkthrough

### Where to perform and report the review

The **book comparison is available now**: compare the sheet above with the actual
register/tickets/closing receipts, then report matches or discrepancies in the
project chat with a short source reference. The agent records those results here.
This release acceptance is not the in-app Review transactions action, which
records a separate per-loan coverage attestation.

**A browser-accessible LO-05 candidate has not yet been provided.** The private
server evidence is a read-only diagnostic, not a running staff preview. The
existing localhost:8079 preview was checked on 7 October and lacks the shared
routine editor; it cannot accept the latest LO-02/03 screens. Prepare and identify
an isolated current candidate and provide its actual URL/login route before asking
the owner to complete the walkthrough below. Corrected real D01623 remains
server-only staging data; do not imply it is present in a local fictional preview.

Use the candidate in an isolated test environment. Existing records can be read
without posting. Any new payout, receipt or closure exercise uses fictional loans
in a disposable test Workspace; do not use the real comparison loans for trial posts.

1. Open **Loans > New loan**, choose the series and inspect the standing terms.
   Check the initial **Entry: Direct in Rokkad / From paper (from setup)** label.
   Under Change, **Use series setup** means inherit the configured default;
   **Create and pay now / Record from paper** is the per-entry override.
2. Check customer, tenure, item principal/rate, add/remove collateral, photos and
   the sum of item principals. The two purposes share these controls. Actual
   paper exceptions should remain available without repeating standing terms.
3. Direct SIMPLE: **Review loan > Confirm payout**, or Save draft. Paper:
   **Review loan record > Record completed payout**, with original number/date
   and source. EXTENDED current lending retains separate responsibilities.
4. Check the payout breakdown and document labels. Paper date is the original
   transaction date; entry time is later. Current valuation must not replace
   the original agreed principal. Keep known receipts/closure optional.
5. Inspect the repayment form's current/completed purpose and item split controls.
   For actual paper receipts, total pays interest first; staff identify the
   principal split and actual fee component. Check a fictional mixed-item case
   if no actual receipt exists yet; record that as workflow review, not source proof.
6. Inspect 06716's closure and custody. Paper settlement with handover unspecified
   must stay distinct from confirmed customer return. A future known linked
   renewal is optional; independently numbered closed/new paper loans do not
   require an invented predecessor link.
7. Open **Loan health**, inspect calculation, paper-book verification, valuation
   evidence and assessment freshness separately. Use **Reassess / history** for
   missing appraisal evidence and **Review transactions** for actual books.
   Choose future Rokkad-only capture only if that is the intended practice.

The detailed operational guides are [workflow choice](../flows/loan-workflow-choice.md),
[reassessment](../flows/collateral-reassessment.md) and
[Loan health](../flows/loan-health-monitoring.md).

## Acceptance record and remaining gate

| Review | Reviewer / date | Source and result |
| --- | --- | --- |
| Sample selection | Workspace owner / 7 October | Owner reviews RA00500/D01623; post-25-September JCL/JSK originations confirmed as direct |
| D01623 original facts | Workspace owner / 6 October | Paper date/amounts/rate/three-month tenure/no later payment or closure confirmed; matches corrected staging read |
| RA00500 register and checkpoint comparison | Workspace owner / pending | Source reference, cutover reconciliation, later activity and result needed |
| C07557 payout/ticket comparison | Workspace owner / pending | Original document/actual payout and result needed |
| 06716 closure/custody comparison | Workspace owner / pending | Original closing record/actual handover and result needed |
| Corrected D01623 display and latest position | Workspace owner / pending | Presentation review and any post-snapshot activity needed; confirmed terms need not be repeated |
| Shared workflow, documents and monitoring walkthrough | Workspace owner / pending | Actual UI review date, acceptable/problem result and any required corrections needed |

Record matches or exact discrepancies with a short book/page or document reference;
do not copy customer documents into the shared repository. An owner confirmation
becomes source acceptance only for the facts actually checked. It does not write
an in-app transaction review or establish complete books for every loan.

LO-05 remains **awaiting owner review**, not complete. Financial or workflow
mismatches return to LO-01/02/03/04 as appropriate. LO-06 still needs the exact
candidate, fresh database/media recovery and measured capacity; LO-07 contains
the concrete production rollout review. D01623 production correction remains a
separate reviewed financial action.

Private evidence is retained under the already approved server-only directory
`/home/rokkad/deploy/cutover-20260924/loan-continuation-20261006-b69df6ab`:
`lo05-acceptance.private.json`, `lo05-read-acceptance.py`, `lo05-source-code/`.
Final private report SHA-256:
`f0fc9bf8a7776c82d4b1878fa326afc26c3d687a7c167e32f9d21fe0638c3b32`.
Probe SHA-256:
`74f3554e894e4500e18d181773c1d689616a9bcdbac01a0313abc341aac074c4`.
