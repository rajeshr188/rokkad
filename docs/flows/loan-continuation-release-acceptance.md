---
status: active
owner: project
updated: 2026-10-07
tags: [loans, release, acceptance]
---

# Loan continuation release acceptance

LC-01–06 change supported admission, continuation and evidence. LC-07 checks the
candidate without converting loans or accepting unverified source books. Technical
rehearsal, operator acceptance and production deployment are separate gates.

## Dated cohort inventory

Run the candidate against a restricted-runtime, migrated **isolated restore** of
the intended release database first. Do not migrate production just to obtain an
inventory. Record the source database identity, snapshot time, candidate source
manifest/image digest, reporting date and Workspace ID with the private results.

```powershell
python manage.py check_loan_release_inventory --workspace-id 123 --summary-only
python manage.py check_loan_release_inventory --workspace-id 123 --as-of 2026-10-06
```

The operator command uses a PostgreSQL repeatable-read, read-only transaction.
The selector also requires a Workspace context and explicitly scopes every query.
Output includes loan identifiers/numbers; retain it privately with release evidence.
It omits borrower details, collateral descriptions, source documents and attachments.
No risk refresh, posting, contract adoption, archive admission or book review occurs.

Counts distinguish current ordinary states, retained immutable archive snapshots,
latest unadmitted source identities and ordinary active/closed contract profiles.
Balances and factual prerequisites use the requested date; state counts describe
the stored state at inventory time, rather than reconstructing past lifecycle state.
Draft/approved loans are counted separately and have no servicing position claimed.
An unsupported contract or unavailable pre-cutover position has no invented balance.

Calculation support, transaction coverage, saved assessment freshness and valuation
eligibility are independent. A supported legacy profile is not silently upgraded
to the shared anniversary contract. A terminal closed checkpoint does not establish
earlier receipts or cash totals. An unadmitted archive identity remains source
evidence, even when a source release claim exists.

`servicing_prerequisites.clear` checks common current-action factual prerequisites.
It is **not** permission to repay, renew, release or auction. Commands still check
membership/business availability, timestamps, schedules, allocations, successor
approval/quotes, custody, legal prerequisites, locks and idempotency. Auction book
coverage is a prerequisite; repayment/release arithmetic is not a book attestation.

Confirm live counts or capture a fresh production snapshot before rollout. The
September discovery archive and October fictional rehearsal are not a current
production inventory. Investigate each unavailable cohort and decide explicitly
whether it remains guarded, requires supported evidence or needs a later slice.

## Operator acceptance against source records

The 7 October [LO-05 comparison pack](../implementation/loan-source-staff-acceptance-lo05.md)
now selects JCL C07557 for direct payout and JSK 06716 for direct origination with
later paper closure, alongside RA00500 and staging-corrected D01623. The owner
volunteered as reviewer and subsequently accepted the RA00500/C07557/06716
comparisons as matching, correct and satisfactory on 7 October. Restricted
read-only financial/UI/document projections pass; shared screen and corrected
D01623 display/latest-position review remain pending.
Use the dated figures, snapshot limits and walkthrough in the pack. No actual
partial-repayment event exists in this selected source cohort, and none is invented.

The owner confirmed **JCL RA00500** on 6 October, correcting RA0500. Live read-only
inspection identifies an imported opening, not direct lending. It covers the
opening row below; a real direct-entry source comparison remains outstanding.
The owner selected **Lakshmi D01623**, a reversed-payout draft, and confirmed the
actual paper payout and terms: 24 September, 2,100 principal at 4% monthly,
84 advance interest, 10 document charge, 2,006 proceeds, three months and no later
receipt/closure. This establishes the owner's source statement, not a posted
financial origin or completed candidate acceptance. See the
[publication/source record](../implementation/loan-candidate-publication-20261006.md).

Staff check these examples against an actual paper register, receipt or direct
transaction; generated examples verify software behavior only. Keep references
and amounts in private evidence, and record the reviewer/date/result below.

| Example | Staff check | Acceptance record |
| --- | --- | --- |
| JCL/JSK direct lending | Series terms, item principals, latest eligible quote, payout deductions, document and numbering match; ordinary entry remains familiar. | C07557 displayed payout comparison accepted by owner on 7 October; current entry UI/quote walkthrough pending |
| Lakshmi delayed paper entry | Original date/number, every item's agreed principal/rate and actual payout survive late entry; no current-price approval is claimed. | Pending actual staff/source review |
| Partial receipt | Total pays interest first; actual multi-item principal split is supplied; next anniversary uses reduced principal. | Pending actual staff/source review |
| Shared boundary | A 5 April loan with one month upfront has no additional May charge on 5 May; the next charge starts 6 May in every supported shared contract. | Business rule confirmed; real-record comparison pending |
| Closed paper loan | Entered receipts reconcile; closure and actual custody agree with source. A terminal-only admission discloses missing earlier history. | 06716 displayed closure/custody comparison accepted by owner on 7 October; shared closure UI walkthrough pending |
| Opening/imported outstanding loan | Verified cutover position, current-period bases and advance coverage agree; earlier unknown receipts remain unavailable. | RA00500 displayed opening/collection comparison accepted by owner on 7 October; earlier receipts not reconstructed |
| Monitoring | Recorded/collection debt, book coverage, valuation availability and assessment freshness are read separately; missing books or prices are visible. | Pending actual staff/source review |
| Quotes/setup | Owner sees seven-day default, can choose zero or another limit; a changed pending review requires review again. Existing frozen approvals keep their original rule. | Pending actual staff/source review |

This gate does not require inventing receipts for archives or admitting every closed
source record. Unsupported/unreviewed identities stay browsable with their limits.
No reminder or collection claim gains certification from an inventory run.

## Deployment and recovery gates

1. Freeze and identify the complete candidate, including runtime JSON contracts.
   Local dirty-source manifests are rehearsal identities; commit/CI/release identity
   must be verified before deployment. Use one compatible candidate for web/workers.
2. Run affected servicing, admission, portability, tenant-isolation and quote checks;
   run application-boundary, documentation, schema-drift and runtime-startup gates.
3. Restore a full database/media backup into a new isolated target and compare
   every public table and individual media-file fingerprint before migration.
4. Rehearse the actual source-to-candidate migration range through owner-only
   settings: the 6 October production baseline is Loans 0032 / portability 0017,
   so Loans 0033–0063 and intervening dependencies are required, not only 0061–0063. Verify
   restricted runtime startup and rejection of pending-migration/owner startup.
5. Back up the migrated candidate, cold restore into another new target, compare
   all table/media fingerprints and repeat restricted startup and cohort reads.
   A disposable, already approved private staging database may instead be replaced
   from its validated sealed checkpoint, after checking adequate capacity, backup
   catalogue and absence of target connections. Never replace production for a
   rehearsal or create a new sensitive-data destination without authorization.
6. Before a separately authorized deployment, capture a current production backup,
   verify live cohort/unsupported cases and actual staff acceptance, and confirm
   the named target, candidate digest, migration plan and operational recovery path.

Do not downgrade software blindly after new evidence profiles have been written.
An older reader may not understand them. Recovery requires the matching reader
and verified database/media checkpoint, plus reconciliation of any transactions
after that checkpoint. A fictional local restore does not prove off-device
production recovery, nor does it authorize deployment.

The approved 6 October production-copy upgrade and current-artifact inventory
are verified: **6,707** ordinary active/closed calculations are supported, with
original contracts retained and all **183** original non-metadata projections
unchanged. **6,404** have unconfirmed transaction coverage; **152** assessments are
stale and **6,555** unassessed; every valuation is unassessed. Staff must disposition
these independent flags rather than treating calculation support as collection
permission. Archives remain browseable evidence. Cold recovery passes all **202
tables and 199 sequence positions**, repeated restricted startup, selected contract
reads and Workspace censuses; full pre-restore cohorts are retained based on
identical restored rows and artifact. Actual media and source-record acceptance
remain open. The server's observed
low-disk failure requires a fresh capacity check before release.

See the [delivery record](../implementation/loan-release-acceptance-lc07.md) and
[accepted slice plan](../plans/loan-continuation-consolidation.md).
