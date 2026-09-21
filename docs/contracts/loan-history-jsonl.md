---
status: active
owner: project
updated: 2026-09-12
tags: [loans, portability, jsonl]
---

# Canonical loan-history/1 JSONL

The first supported source is UTF-8 JSONL: exactly two nonempty records, the
manifest on line one and one complete loan object on line two. A trailing newline
is accepted. The [executable schema](loan-history-v1.schema.json) describes the
assembled `{ "manifest": first_record, "loan": second_record }` object.
[Active example](examples/loan-history-active.jsonl) and
[closed example](examples/loan-history-closed.jsonl) contain synthetic values;
replace all facts and setup mappings with actual source evidence. The active
example uses `source-loan` / `00042`; the closed example uses
`source-loan-closed` / `00043` and release `R0043`. They are independent synthetic
loans, so both can be tested in one Workspace without changing accepted history.

Bounds: 5 MiB per file, one loan, 1–20 collateral items, 1–240 events, 0–20 fee
inputs, tenure 1–12 months, and at most ten years between disbursal and cutover.
Decimal spellings are normalized (for example, `1000.00` becomes `1000`) before
source hashing, without changing IDs such as `00042`. Amounts are nonnegative decimal strings, at most twelve integer and six fractional
digits. The currency quantum is 0.01. Unknown properties, duplicate JSON keys,
unsupported events, binary contents, malformed dates and excess precision fail.
A Workspace may retain at most twenty unfinished Loans import attempts at once.
Completed evidence is retained; this limit does not delete completed imports.

## Source identity and history

Keep a stable source namespace UUID and loan ID across retries. Keep original
loan and release numbers independently from those identities. Borrower references
use the exact Party source system and source ID already imported to the destination.
Never match borrowers by display name or copy database primary keys.

The loan supplies original licence number, disbursal date, calculation contract,
grace, tenure, approval timestamp/actor/reference, frozen policy and each collateral
item's physical facts, allocated principal, monthly rate and valuation evidence.
Disbursal supplies fee inputs, advance-interest periods and all resulting totals.
The original single flexible obligation supplies principal, interest and maturity.

Events appear in effective-date order. Array order resolves events on the same day.
Each has a unique source ID, historical actor, principal/interest/fees and the
recorded balance immediately after that event. Repayments carry item principal
allocations. Accruals carry original period, fraction, base and recognized and
unrounded interest. A closed loan ends with a full release, complete item return
and valuation evidence, and zero recorded balance. A null collector means source
collector identity is unavailable; it is never presented as verified locally.
Source approval and event actors remain historical claims. Importing creates no
source user accounts or permissions; local recording attribution names the importer.

Cutover is the as-of date for supplied recorded balances. It is not an instruction
to synthesize accrued interest or an opening position. Recorded balances and
remaining contractual obligations are reconciled separately. Source calculations
must match native frozen-policy rules; there is no tolerance or balancing entry.
Native event export preserves recorded history, including unrecognized future
interest. It does not invent missing source events.

## Supported coverage

Only flexible partial-payment, NONE amortisation, FLEXIBLE frequency and
REDUCE_PRINCIPAL contracts with SIMPLE interest, FULL_MONTH or SLAB partial months
are supported. Active and fully released histories use the same profile.

This is a partial financial/collateral export, not a Workspace archive. It excludes
binary documents/photos, workspace configuration, renewals, auctions and opening
positions. It does not transfer storage movements, funding, monitoring results,
communications, document issues or the complete appraisal revision archive.
A native history with funding pledges or storage movements is rejected. Reversals,
capitalization, installment structures and partial release histories are rejected.
Native export also rejects accrual evidence without an associated source event;
such zero-net/advance-covered histories require a wider explicit representation.
No unsupported event is silently removed to make an import pass.

Native exports require frozen approval, disbursal and original schedule evidence.
Loans lacking it cannot be converted by guessing. Imported loans retain immutable
source documents and local identity mappings and can export unchanged history back
to the same source graph. Subsequent supported native repayments/accruals/releases
extend exports; unsupported subsequent activity blocks this profile.

No vendor file has been supplied or certified. A CSV/Excel/vendor adapter is future
work only when a representative source demonstrates a concrete need.
