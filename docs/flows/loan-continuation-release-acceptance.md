---
status: active
owner: project
updated: 2026-10-06
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

The owner selected **JCL RA0500** as the first real example on 6 October. Its
identification is not acceptance of its balance or confirmation of its entry
channel. Retrieve its actual agreement/events and compare with the source record;
the technical fictional database has no verified copy of this loan. A real Lakshmi
paper example and staff confirmation remain outstanding.

Staff check these examples against an actual paper register, receipt or direct
transaction; generated examples verify software behavior only. Keep references
and amounts in private evidence, and record the reviewer/date/result below.

| Example | Staff check | Acceptance record |
| --- | --- | --- |
| JCL/JSK direct lending | Series terms, item principals, latest eligible quote, payout deductions, document and numbering match; ordinary entry remains familiar. | Pending actual staff/source review |
| Lakshmi delayed paper entry | Original date/number, every item's agreed principal/rate and actual payout survive late entry; no current-price approval is claimed. | Pending actual staff/source review |
| Partial receipt | Total pays interest first; actual multi-item principal split is supplied; next anniversary uses reduced principal. | Pending actual staff/source review |
| Shared boundary | A 5 April loan with one month upfront has no additional May charge on 5 May; the next charge starts 6 May in every supported shared contract. | Business rule confirmed; real-record comparison pending |
| Closed paper loan | Entered receipts reconcile; closure and actual custody agree with source. A terminal-only admission discloses missing earlier history. | Pending actual staff/source review |
| Opening/imported outstanding loan | Verified cutover position, current-period bases and advance coverage agree; earlier unknown receipts remain unavailable. | Pending actual staff/source review |
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
4. Rehearse migrations 0061–0063 through owner-only migration settings. Verify
   restricted runtime startup and rejection of pending-migration/owner startup.
5. Back up the migrated candidate, cold restore into another new target, compare
   all table/media fingerprints and repeat restricted startup and cohort reads.
6. Before a separately authorized deployment, capture a current production backup,
   verify live cohort/unsupported cases and actual staff acceptance, and confirm
   the named target, candidate digest, migration plan and operational recovery path.

Do not downgrade software blindly after new evidence profiles have been written.
An older reader may not understand them. Recovery requires the matching reader
and verified database/media checkpoint, plus reconciliation of any transactions
after that checkpoint. A fictional local restore does not prove off-device
production recovery, nor does it authorize deployment.

See the [delivery record](../implementation/loan-release-acceptance-lc07.md) and
[accepted slice plan](../plans/loan-continuation-consolidation.md).
