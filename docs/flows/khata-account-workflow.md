---
status: active
owner: loans
updated: 2026-10-03
tags: [khata, workflow, operators, developers, collateral]
---

# Khata account workflow

This guide explains how staff take a Khata from proposed terms to financial
settlement and completed collateral returns. It also gives developers the source
contracts behind each step. The workflow is implemented in the local test
candidate; production activation and operator acceptance remain separate gates.

A Khata has an agreed borrowing limit, gradual secured withdrawals and interest
on the full agreed limit from the first actual withdrawal. It continues until
settlement, with no fixed maturity. Khata uses separate numbering and financial
records within Loans; existing ordinary and flexible loans keep their own rules.

## Finding saved documents and returning to work

Open **Documents** to find original saved issues. Search by title, source payment
reference, issue/source/item number, request UUID or an exact collateral-label UUID.
Filter by document type and document date; source document dates are business dates,
while statements/labels retain their saved as-of date. Sort by issuance time, newest
or oldest, and use 25-row pages. Filtering never changes a saved PDF. Each source
issue links to its event and any later correction; the original reprint remains.
The recent photo disclosure shows up to 25 photographs, with a link to the full
searchable collateral browser.

On mobile, **Account section** shows the current section and provides a GET **Go**
fallback without JavaScript. With JavaScript, selecting a section navigates directly
and the active tab is positioned in view. Action/review back links return to the
relevant account section. Interest receipts/finalization return to Interest after
confirmation; agreement actions return to Actions, withdrawals/settlement to
Overview and corrections to their new History event. Collateral receiving/exchange/
photo/handover keep their existing receipt, exchange and pending-return flows.

See the [navigation checkpoint](../implementation/khata-document-navigation.md).

## Pause or retire a Khata series

In **Khata series & policies**, a setup-authorized member chooses **Review status
change**, selects pause/resume/retire, enters the reason, reviews the effect and
confirms. Status history retains the responsible staff member, time and reason,
with 25-change pages. Temporary pauses can resume; retirement is permanent.

Pause and retirement block new drafts, opening approvals, every withdrawal and
limit increase, including existing accounts. Existing interest collection,
collateral servicing, reductions and settlement continue under their usual rules.
Resume restores series availability only: licence eligibility, number capacity,
photos, prices and lending approval still apply. Existing account numbers and
consumed counters are preserved; the licence association is unchanged. A new
series with a distinct prefix is required after retirement.

The account's Overview/Actions explains a paused/retired lending series and hides
known unavailable lending shortcuts. Confirmation remains authoritative. Native
recovery retains these setup events; older archives require their matching
schema/guard image or full database/media recovery. See the
[status decision](../adr/2026-10-03-khata-series-status.md).

## Understand the account figures

| Figure | Meaning |
| --- | --- |
| Agreed limit | The committed interest base and overall borrowing ceiling; it is not principal debt |
| Actual principal outstanding | Actual payouts less principal received through formal reductions or settlement |
| Unused entitlement | Remaining permitted withdrawals under the limit and revision history; repayments do not refill it |
| Accrued unpaid interest | Calculated interest not yet received, including amounts not yet due and the opening minimum |
| Interest due | Unpaid interest whose scheduled due date has arrived |
| Interest overdue | Unpaid due interest from the day after its due date |
| Eligible collateral | Held items that are not reserved for outgoing return |
| Items awaiting handover (return pending) | Items reserved for return but still physically held; they cannot back withdrawals |

The register groups four filtered financial totals in cards above its filters,
with the matching-account count in the results-table header. Totals cover all
matching accounts before pagination. It shows agreed limit and actual principal
outstanding side by side. Its
**Items awaiting handover** count links to the pending collateral browser. Counts
refer to item records, not the number of jewellery pieces inside a record.
The detail-page position is an account summary. Use the settlement review for the
amount to collect when closing, rather than treating the summary as a settlement quote.

## Navigate the account

Each account opens on **Overview**. Select a tab to work with one section at a
time; links work without JavaScript and retain the selected section in the URL.
On phones, scroll the tab bar horizontally for the remaining sections.

| Tab | Use it for |
| --- | --- |
| Overview | Dated balances, agreed terms, collateral drawing cover and owner policies |
| Actions | Permission-aware workflows grouped into agreement/opening, collateral, withdrawals/interest, and settlement/corrections |
| Collateral | Custody/photos, receive/exchange/handover shortcuts and the large-holding search browser |
| Interest | Interest schedule and authorized receive/finalize shortcuts |
| History | Filtered and paginated immutable source events |
| Documents | Issue/reprint saved PDFs, labels and original photo history |

**Service this khata** in the header opens Actions. Available actions still depend
on role, account state and current workspace write availability. Opening a tab or
selecting an action records no cash/custody movement; existing review/confirmation
or actual-receipt requirements apply. QR/item and source-event links automatically
open Collateral or History. Invalid document submissions select Documents so staff
can see the errors instead of losing them inside another section.

## Set up the workspace

Open **Loans > Khata accounts > Khata series & policies**. Create a separate
series, for example KH. Leave the licence blank for an independent series, or
select a usable licence for an associated series. The association and numbering
format freeze after the first number is issued. Issued numbers are not recycled.

The workspace owner chooses **Allow with warning** or **Disallow** for exchange
valuation/LTV shortfalls and overdue interest before withdrawals/exchanges.
Warning is the default. These choices never waive same-metal exchange rules or
the hard collateral cover required for a withdrawal. Photo requirements follow
the workspace collateral-photo policy. Authorized approvers, cashiers and
collateral releasers need the respective existing Loans permissions.

## Create the draft

Choose **New khata draft** and select an active borrower and series. Enter the
agreed limit, interest percentage per month, agreed LTV, monthly or annual
collection frequency, and lender identity. Review and confirm the proposed terms.

Saving reserves the permanent number but does not approve the account, advance
cash or start interest. Before opening, changed terms need a new proposal and
approval. An unopened account can be cancelled after actually returning held
collateral through the supported return workflow.

Example terms throughout this guide are a INR 1 crore limit, 1% per month and
75% LTV. They illustrate the chosen calculation rules, not suggested customer pricing.

## Receive collateral and photographs

Open **Actions > Collateral > Receive collateral**, or use the shortcut on the
**Collateral** tab. Record
description, metal, quantity, gross/net weight, purity, storage reference and who
delivered it. Confirm only collateral actually received into custody.

The receiving screen includes an optional JPEG or PNG upload and local preview.
Choose **Open camera**, select rear/front or an available webcam, and use
**Take photo**. Check the still preview before saving; opening or taking a photo
does not receive collateral by itself. **Remove selected photo** clears it, and
opening the camera again allows a retake. Switching/closing/submitting stops the
camera. Browser permission is requested only when staff open it.

Live browser camera requires HTTPS or localhost. A phone visiting a computer
through an ordinary HTTP LAN address cannot use the live camera API; the
**Phone rear camera** / **Phone front camera** buttons request the native device
picker where supported. Browsers may offer a picker or a camera and may ignore
the front/rear hint. File upload remains available when permission is denied or
a camera is unavailable. Captures become JPEG uploads, with the same existing
validation/private storage as chosen files. These controls also appear on the
later photo-attachment screen. Photographs appear beside items in the browser,
exchange search and detail-page custody list; select a thumbnail for its original.

Confirm actual receipt, then choose **Save received collateral** or **Save and add
another**. Receipt and photo remain separate audit records within the same operation
transaction. A failed photo does not silently receive the item without its upload.
**Attach collateral photo** remains available for later attachment. Photos and
small browser thumbnails use authorized private routes.
Missing mandatory photos permit draft preparation but prevent opening approval;
photo policy is checked again at relevant withdrawal and exchange boundaries.

Collateral backs the actual principal after a payout. At 75% LTV, INR 20 lakh of
eligible collateral supports up to INR 15 lakh of total principal. It need not
cover the entire unused INR 1 crore commitment at opening.

Receiving an item records custody. It does not record a payout or identify that
item as the replacement in a particular exchange. The
[collateral usability checkpoint](../implementation/khata-collateral-usability.md)
records combined receiving/photos and searchable selection. The earlier frozen
candidate remains identifiable separately from this implementation.

## Approve and make the first withdrawal

An authorized approver uses **Approve opening**. Then an authorized cashier uses
**Record actual withdrawal**, reviews eligibility, and confirms the real payout
with its actual payment reference. Current approved prices, collateral, photos,
terms, permissions and lending eligibility are rechecked.

The first payout changes the account from approved to active and starts interest
on the full agreed limit. If the first payout is INR 10 lakh on 10 October:

| Position immediately after payout | Amount |
| --- | --- |
| Agreed limit | INR 1 crore |
| Actual principal outstanding | INR 10 lakh |
| Unused entitlement | INR 90 lakh |
| Interest for one full unchanged month | INR 1 lakh |

Approval alone starts neither interest nor cash debt. There is one original
first-month minimum; a later limit/rate change does not start another minimum.

## Make later withdrawals

Receive more collateral when needed, then record each actual withdrawal against
the same Khata. The payout must fit unused entitlement and the current collateral
cover of total principal after payout. Both checks apply independently.

With overdue blocking enabled, overdue interest prevents withdrawals and exchanges.
Interest receipts, collateral deposits and settlement remain available. Paying
the overdue amount removes that restriction; other lending checks still apply.

## Collect interest

The percentage is always monthly, even for annual collection. For a first payout
on 10 October, monthly interest is first due on 10 November; annual collection is
first due on 10 October the following year. Twelve unchanged months at the example
terms total INR 12 lakh. Short months clamp to the last available day and later
anniversaries return to the original day when possible.

Use **Receive interest** only after receiving actual money. Partial receipts
allocate oldest due first. Ordinary advance or excess interest payments are not
supported. Interest is simple: unpaid interest does not compound. Interest
receipts change neither principal nor unused entitlement.

**Finalize completed interest** freezes completed monthly charges without receiving
cash. Annual collection preserves annual due dates even when monthly charges are
finalized. Check the interest schedule alongside accrued, due and overdue figures.

## Exchange collateral

Receive and photograph the replacements first. Open **Exchange collateral** and
select both **Collateral to return** and **Received collateral replacing these items**.
The selections identify a group of outgoing items and the exact incoming group
that replaces them; they do not require one-to-one pairing.

Search and page each table by item identity, description or storage; filter metal
and receipt date. Selected groups stay visible while changing search or pages.
**Receive replacement collateral** returns to the exchange with existing selections.
The new item is suggested for explicit selection, never silently assigned.

The right-hand replacement selection is significant even though receipt has
already been recorded. Receipt proves custody; exchange selection proves which
items were accepted for this replacement. The exchange retains both selections,
current approved valuations, per-metal shortfalls, policy and warnings. It does
not receive the items again or count their value twice. A previously used active
incoming selection cannot be reused as incoming for a second exchange; that item
can later be selected as outgoing.

Both sides use the same current approved price evidence. Gold replaces gold and
silver replaces silver; value from one metal cannot offset another. Higher purity
may compensate for lower weight. The owner policy warns or refuses if replacement
value or remaining whole-account cover falls short.

Confirmation reserves outgoing items. They stop backing withdrawals immediately
but remain physically held. Use **Hand over reserved collateral** for each actual
return, with the reservation source, recipient and handover reference. A reservation
is not proof of physical delivery. A warned exchange cannot bypass cover for the
next withdrawal.

## Change the limit or rate

Use **Propose agreement terms**, then **Approve agreement change**, recording the
borrower's consent reference, and **Activate approved agreement**. Proposal or
approval alone does not change live terms. Routine changes are effective today.

An increase from INR 1 crore to INR 1.5 crore raises the interest base and unused
entitlement without advancing cash. Interest splits between the old terms before
the effective date and new terms from that date. Subsequent payouts remain separate.
The number and original anniversary continue; collection frequency, LTV and lender
identity stay fixed after opening.

A reduction below principal requires repayment of at least the excess principal.
Additional principal repayment is allowed within a formal reduction, up to
principal outstanding. Principal payments do not refill entitlement. This release
has no standalone principal repayment, same-limit repayment/renewal, or revolving
repay-and-redraw operation.

If returning collateral during reduction, select it for approval and activation.
Clear due interest and retain adequate LTV cover after principal repayment,
including under exchange warning policy. Unbilled annual interest stays on its
schedule. Actual handover is separate and, while active, rechecks due interest and
current retained cover.

## Settle the money

Choose **Collect full settlement**. Review actual principal plus all unpaid
interest through today's closure, deducting prior interest receipts. Receive the
quoted payment and confirm with the real payment reference.

An annual payer closing after four unchanged full months pays four months of
interest rather than a whole year. Closure within the first month collects the
original full-month minimum. Later partial months use actual days within the
original monthly anniversary interval. Start days are included and end days
excluded; monthly amounts round half up to paise.

Settlement zeroes principal and unused entitlement and stops interest on the
settlement date. It reserves remaining collateral for return. Earlier exchange
or reduction reservations retain their original return sources.

## Complete physical returns and close

The account remains **Settled, return pending** while any collateral is held.
Record every actual handover to the recipient. After the last item leaves, the
account becomes **Closed**. Delayed collection does not restart interest.

Issue relevant source PDFs, statements and individual/combined 100 x 60 mm labels
during the lifecycle. Saved PDFs reprint their original bytes; label QR codes show
current authorized custody. For large holdings, prefer individual labels when a
combined label cannot fit readable complete text. See the
[label guide](khata-labels-and-pilot-review.md).

Review principal, unpaid/due interest and pending physical returns regularly.
Keep protected backups through the [servicing and recovery flow](khata-servicing-and-recovery.md).
Supported corrections preserve original evidence: whole interest receipt
nonreceipt/full refund and an exchange before outgoing handover, subject to
dependency checks. Mistaken payouts, activated revisions, settlements, completed
handovers and complex corrections are not generic editable records.

## Identify collateral in the current candidate

Use the **Collateral** tab on the account detail page to inspect the item number,
immutable UUID, description, metal, quantity, weights, purity, storage reference
and held/return-pending/returned status. Use private photos to verify appearance.
Scan an individual label QR while signed in to reach that item's current custody.
A combined label identifies the account rather than one selected item.

Descriptions and storage references may repeat. Verify the item identity and
physical piece before selection or handover. An item record with quantity greater
than one is selected as a whole; arbitrary partial quantities are not an exchange
selection. Record separately identifiable units as separate items where staff need
to exchange or return them independently.

Choose **Search & browse collateral** from the detail page for a paginated browser.
Search item number, UUID, description or storage; filter metal, custody and receipt
date, and sort newest/oldest received. Rows include private thumbnails, identity,
weights, purity, storage and current valuation suggestions. Missing same-day prices
show unavailable rather than zero. The Collateral panel preserves item QR anchors.

Exchange uses searchable tables with visible selected groups instead of full-holding
dropdowns. Incoming excludes prior active incoming membership. Services still reject
foreign, returned, reserved, reused incoming or otherwise invalid selections and
recheck evidence at confirmation.

## Understand the next action and prepare a draft

Overview and Actions show **Agreement & next step**: current source-backed terms,
latest saved proposal, dated recorded approval and exact evidence links. A proposal
is not active merely because it was saved or approved. Stale proposals require a
new today-dated review. Activation choices show only usable, unused approvals for
today's latest proposal; changed account evidence requires approval again.
Suggested actions respect existing capabilities and known prerequisites. Complete
review/confirmation to recheck current prices, photos, policy and actual cash/custody.

Interest actions appear when there are actual due amounts or unsaved completed
periods. Receipts finalize elapsed periods automatically in the same transaction;
**Finalize completed interest** only saves charge evidence, receives no cash and is
optional. The next/oldest unpaid anniversary links to the interest schedule.

In **New khata agreement draft**, search an active borrower and review their
existing outstanding. Actual principal/accrued unpaid interest are debt; agreed
limits and unused entitlement are not. Without JavaScript, expand **Borrower search
without JavaScript** before entering terms and narrow name/code/phone to at most
25 matches. Check the borrower's Party > Loans page for outstanding in native use.

Enter limit, monthly rate and monthly/annual payment to see **Indicative opening
interest**. It assumes first actual withdrawal today and unchanged terms. Annual
collection still uses the monthly percentage; the first bill aggregates twelve
monthly charges. The first due date uses the original anniversary, with short-month
clamps. No charge is posted by this illustration. The same illustration appears
in draft review without JavaScript; only confirmation saves the draft, without
opening it or paying cash. Opening acknowledgement remains a design proposal.

## Follow up on interest collections

From **Khata accounts**, open **Collection worklist**. Its default includes overdue,
due today and upcoming active accounts. Choose the next 7, 30 or 90 days, filter
by number/borrower, series or licence association, or inspect all active accounts.
Upcoming excludes arrears; due today excludes older unpaid dues. Days overdue
start the day after the oldest unpaid anniversary. Evidence-review accounts remain
visible in every status filter so missing sources cannot look like cleared dues.

**Instalment unpaid** is the oldest unpaid due-date group; **Total interest due now**
includes all older unpaid groups. If dues are cleared, the next anniversary and
instalment are estimated from current activated terms. Annual payment groups all
monthly charges at the annual anniversary: 1% per month remains 1% per month.
Future estimates are not posted bills or authorization to accept advance payment.
Choose **Interest schedule** to review evidence, or **Receive interest** when due
and your role/workspace allow it. Enter actual cash/reference and complete the
existing review/confirmation. Merely viewing the worklist posts nothing.

**Current LTV cover** uses eligible held collateral and today's approved prices;
reserved outgoing items cannot back draws. Missing prices leave cover unavailable
without hiding known dues. **Recorded exchange warning** opens the latest warned
exchange, labelled if later corrected. It is historical evidence, not extra cash
debt or proof that current collateral remains short. Totals include all matched
accounts before pages of 25. No automatic reminder is sent by this screen.

## Review cash and custody across accounts

From **Khata accounts**, choose **Cash & custody reports**; ordinary Operational
reports also links here. **Cash daybook** defaults to today. Select an inclusive
business-date range, event type, number/borrower/payment reference, series or
licence association and date order. Totals include all matching sources before
pages of 25. Principal and interest received are separate; payouts/refunds are
cash out. Net movement is not current outstanding or a closing cash balance.

The report uses corrections known today. A receipt later confirmed **not received**
shows zero actual cash even when its correction lies outside the selected range.
A confirmed **refund** keeps the original receipt inflow and shows an outflow on
the refund's business date. Both originals and corrections retain exact event
links; collateral exchange corrections carry no cash. Review linked evidence if
comparing a previously downloaded copy with today's results.

Choose **Custody & pending returns** for current physical holdings across active,
unopened and financially settled accounts. Pending means reserved but still
physically held. Filter held/not reserved, pending, returned or all; search an
Item ID, permanent UUID, description, storage, borrower or account number. Receipt
dates select items received in that range; their status is still today's status.
Metal totals distinguish item records, pieces and net grams. Open exact item,
receipt, reservation or actual return evidence, including recipient/reference.

**Download matching CSV**, when your role has report.export, includes matching
rows across every page with source IDs/URLs and knowledge/custody date. Exports
above 10,000 rows are refused with guidance to narrow filters; no rows are
silently dropped. Cash and custody reports work without JavaScript and change no
financial or physical source. Historical outstanding requires separate reporting.
See the [report contract](../implementation/khata-operational-reports.md).

## Find an event in source history

Open the **History** tab on the account detail. It shows 25 events per page,
newest business date first, with the immutable account sequence ordering events
on the same date. **Date order** can show oldest first instead. Recorded date/time
appears separately so staff can distinguish the business date from recording time.

Choose **Event type** for withdrawals, collateral received, interest received,
collateral exchanges or any other recorded operation. Set **Business date from**
and **through** for an inclusive range. Search **Item ID, UUID, description or
payment reference** to find receipts/photos/returns/exchanges involving an item,
or cash movements by their reference. A numeric item search uses the exact Item
ID. **Operation ID** finds one exact recorded event. Exchange searches return one
event even if several matching collateral items belong to it.

Choose **Filter events**; paging preserves the filters and sort. **Reset history
filters** restores all events in newest-first order. The History tab stays selected after a
filter or page change. On small screens, scroll the table horizontally to read
all columns. Selecting an operation number isolates it; correction and
return-source links similarly find the exact related event even on another page
or outside the prior filters. Direct collateral links open the existing custody
record. Dates/filter errors are shown rather than silently substituted.

**View event details** opens the exact immutable event. Review business date versus
recording time, actor, actual payment/handover/consent references and related
approval/reservation/correction sources. Exchanges show exact metal-specific IN
and OUT groups and permanent item identities. Expand saved valuations to see all
reviewed items, original quote dates/prices and preserved values; later prices or
owner policies do not rewrite them. Recorded replacement shortfalls, retained LTV
backing and overdue-interest warnings have separate meanings. Interest events show
receipt allocations or frozen monthly charges and dated term segments. Corrected
sources retain their facts and link to the compensating event. Native links work
without JavaScript.

Filtering history never filters the account balances or changes audit evidence.
Corrected original events remain visible with links to their separate compensating
events. A displayed correction is not an additional cash receipt.

Select an operation number for its correction/support guidance. Supported scope
is distinguished from corrected, unsupported, settled-account or later-operation
refusals. Exact blocking-source links help the administrator review dependencies;
an authorized writable administrator can enter supported review with the source
selected. Confirmation still rechecks all existing conditions. Read the
[exception/support runbook](khata-servicing-and-recovery.md#exceptions-and-support)
for cash/custody evidence and unsupported cases.

## Developer reference

| Concern | Existing implementation |
| --- | --- |
| Terms, numbering, cancellation | [Khata account services](../../apps/tenant_apps/loans/services/khata_accounts.py) |
| Receipt, photos, approval, payouts | [Opening services](../../apps/tenant_apps/loans/services/khata_opening.py) |
| Charges and interest receipts | [Servicing services](../../apps/tenant_apps/loans/services/khata_servicing.py) |
| Revision approval and activation | [Revision services](../../apps/tenant_apps/loans/services/khata_revisions.py) |
| Exchange, reduction cover, handovers | [Collateral services](../../apps/tenant_apps/loans/services/khata_collateral.py) |
| Closure quote and collection | [Settlement services](../../apps/tenant_apps/loans/services/khata_settlement.py) |
| Operational cash and current custody reports | [Report selectors](../../apps/tenant_apps/loans/selectors/khata_reports.py) and [CSV service](../../apps/tenant_apps/loans/services/khata_report_exports.py) |
| Position and eligible custody | [Canonical selectors](../../apps/tenant_apps/loans/selectors/khata.py) |
| Screens and reviewed actions | [Forms](../../apps/tenant_apps/loans/web/khata_forms.py) and [workflow adapter](../../apps/tenant_apps/loans/web/khata_workflows.py) |
| Immutable operation and selection records | [Khata models](../../apps/tenant_apps/loans/models/khata.py) |

Preserve separate `DEPOSIT`, `PHOTO`, `EXCHANGE` IN/OUT selections and `HANDOVER`
evidence even if screens combine steps. Item receipt, exchange authorization and
physical release have distinct meanings. Derive custody from actual sources;
never add a mutable checkbox that substitutes for a handover. Selection is scoped
to the account and workspace, and confirmation must recheck current eligibility.

Existing reviewed commands bind actor, workspace, account, action, business day
and request identity. Reviews expire after 30 minutes or at the day boundary;
changed evidence needs a fresh review. Repeated confirmations must not duplicate
money, items or returns. Keep business posting in services and preserve forced RLS,
private media and immutable evidence. UI improvements must not alter ordinary
loan services or the frozen pilot image without a newly verified candidate.

See the [technical design](../architecture/khata-technical-design.md),
[custody checkpoint](../implementation/khata-custody-settlement.md) and
[pilot acceptance checks](khata-test-pilot-acceptance.md) for detailed boundaries.

## Searchable pending returns and servicing

From **Collateral**, choose **Pending returns**. Search by Item ID, UUID,
description or storage; filter metal/receipt dates and page through 25 records.
Each pending row shows its protected photograph when available and links the exact
reservation operation. **Hand over Item** opens the handover form with that item
and its active source selected. Check identity and actual recipient/reference, then
review and confirm; opening/searching a page never records physical movement.

The handover form also searches pending items and pairs the reservation automatically.
**Attach photo** opens the held-item search with that row selected, followed by the
existing camera/file preview. Reduction approval searches eligible held items with
multiple selection; selected items stay listed across filters/pages. Returning no
items remains allowed. Required repayment, cleared due interest and retained LTV
remain server checks. Ordinary scoped dropdowns work without JavaScript; **Use
ordinary selection** is available if search is unavailable. Photo and handover
success return to the relevant collateral browser.

## Custody pages and exact item links

The **Collateral** section shows 25 item records per page, ordered by Item ID.
Use **Previous items / Next items**, or **Search & browse collateral** for filters.
An individual QR or history item link selects its exact UUID and shows that record
with current custody/latest photo even if it normally belongs to a later page.
Choose **Show all collateral** to return to paged browsing. Printed QR routes are
unchanged. Old fragment-only browser bookmarks use JavaScript to locate an item
outside the current page; without JavaScript, use the collateral browser's UUID
search. Financial totals/interest always cover complete source evidence and do not
change with custody or history pages. Only the chosen section loads its own data.
