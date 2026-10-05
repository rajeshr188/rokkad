---
status: active
owner: project
updated: 2026-10-05
tags: [contract, loans, history, recorded]
---

# loan-history/4: recorded source agreement

Use exactly two bounded UTF-8 JSONL records: a manifest, then one loan. The
[published schema](loan-history-v4.schema.json) and
[closed example](examples/loan-history-recorded-v4.jsonl) match the implemented
contract. The example is synthetic: 6,000 at 1% plus 4,000 at 3%, one advance month
(180), document charge 10 and proceeds 9,810. Receipt 1 applies 1,000 to the
lower-rate item on 20 January. From 2 February interest is 50 + 120 = 170; closure
receives 9,170. These amounts are illustrative, not an owner's actual account.

## Meaning and bounds

`contract=recorded-anniversary/3` selects the shared original-anniversary inclusive
monthly calendar. A loan dated 5 April remains in its first period through 5 May;
its next charge starts 6 May. Principal paid within a period changes the following
period's base. Currency quantum is the agreement's captured `0.01` or `1`, HALF_UP
per item per period; cash and principal retain paise precision.

The supported product is flexible partial payment, no amortisation, flexible
frequency and principal reduction. Tenure is 1–600 months within the mapped
product's bounds; source history spans at most ten years and no future dates.
Twenty actual items and thirty receipt/closure transactions are supported. Source
receipts use fees/interest/principal priority under this contract, with explicit
actual per-item principal allocations. Rates, weights, purity, principal, proceeds
and deductions undergo the existing recorded agreement validation too.

The original payout is represented by `collateral` and `payout`, not a second cash
event in `events`. `CASH` means known actual original cash; `PROCEEDS` means the
agreed amount after deductions while physical cash is unknown. Events contain an
actual total, its principal/interest/fees, stable source ID/reference, source actor
claim or null, original capture purpose and actual item balances. All monetary
splits and final eligible collection `cutover` balances must reconcile; no supplied
allocation is silently replaced. Derived interest recognition is checked on export
against the shared period bases and cumulative recognized charges.

`CLOSE` is final and required for CLOSED state. `RETURNED` records a confirmed
physical return; `PAPER_SETTLEMENT` retains PAPER_CLOSED custody and unknown
handover. A known source `returned_at` must match the local business day and cannot
be future dated. Source actor, collector and time can remain null. Restoration
uses day-level recorded evidence; a known original timestamp remains an original
source claim in the accepted immutable document. The local importer is a separate
actor and is never represented as the original collector.

## Identity and mapping

The namespace is stable for the source. Loan ID must be stable and unique within
that namespace; include the book in a book-local ID (e.g. `Book A:42`). Number and
book are searchable source aliases, not local number or Party identity. Book means
the source register grouping; a locally originated Rokkad export uses its known
series grouping and retains the separate original paper reference. Legacy
`legacy:{namespace_hex}:{schema}` Party systems keep existing schema scoping.
Same number from different books/licenses can have distinct generated H/... local
numbers. Same source ID with changed payload/mapping, or same book/number under a
new ID, requires reconciliation. A generated number cannot consume a future local
number range. Manual paper entry's existing duplicate protections are unchanged.

The owner selects explicit local licence revision, series and compatible product;
borrower maps by exact imported Party identity. A product configured later or
retired can supply matching continuation. Its availability date does not assert
past approval. Verified source licence validity must cover the original date, or
explicit `legacy_license_evidence` must map to an inactive legacy reference with
unknown dates. This cannot authorize current lending.

`monitoring` selects current method/LTV/reason separately from original approval.
No original digital Rates, appraisal or approval rows are required or manufactured.
Current value must subsequently be evidenced through ordinary monitoring.

## Review, replay and export

Existing staged upload, rolled-back preview, signed owner confirmation and locked
commit are reused. Each actual receipt/closure is written through existing financial
services and checked against the source; failure rolls back the whole admission.
An identical accepted source/mapping returns its original admission. Different
payload or mapping is held. The same source-binding table also prevents admitting
a full history over an already accepted opening.

Exports preserve original IDs and claims, retain actual later item allocations and
original action purpose, and extend cutover to later financial activity. Verified
source coverage must match the current aggregate and cover cutover. No completeness
beyond that cutover is claimed. Direct later receipts and full closure remain
supported; a restore records them as completed source facts while retaining their
original purpose claims.

This is a PARTIAL portable financial history. It excludes binary files, workspace
configuration, opening positions, linked renewals, auctions, reversals/corrections,
standalone recognition and additional custody/funding/storage movement histories.
Unsupported graphs fail explicitly; they are never dropped. Wider graphs use
reviewed opening admission or exact Loans recovery with required database/media
backups. The closed-evidence archive remains a separate retention option. Existing
recorded agreements without explicit source licence mapping or verified coverage
are not automatically asserted to have complete portable origination history.
