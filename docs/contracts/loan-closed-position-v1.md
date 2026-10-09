---
status: implemented-contract
owner: loans
updated: 2026-10-09
tags: [contracts, loans, import, closed-position]
---

# Ordinary closed-position input, version 1

`loan-closed-position/1` describes a known zero-debt closed position without
asserting a reconstructed payout, collections, approval, pricing or calculation
contract. The Python schema and bounded parser are in
[closed_position_contract.py](../../apps/tenant_apps/loans/services/closed_position_contract.py).
The [published JSON schema](loan-closed-position-v1.schema.json) is frozen;
semantic changes require a new version rather than rewriting this contract.
This first slice supplies a validated input and coverage report; persistence,
owner batch approval and ordinary-loan conversion are subsequent IP-03/IP-04 work.
Parsing or preparing a candidate does not authorize admission.

## Fields

| Object | Required contents and meaning |
| --- | --- |
| profile | Exactly loan-closed-position/1 |
| source | Canonical non-nil namespace UUID, scoped system and exact source loan ID; never borrower-name matching |
| loan | Original number and exact borrower source reference; original date, actual closure date, original principal, monthly rate and tenure keys remain present but may be null |
| position | CLOSED, identified as-of date, INR, zero principal/interest/fees, returned-to-borrower or unknown custody, source-release or owner-position basis, and identified supporting reference |
| earlier_history | UNAVAILABLE means the complete earlier financial timeline is unavailable; some source receipts may still be retained |
| retained_evidence | Optional exact closed-evidence/1 source document; identity and known normalized fields must agree, while raw rows retain their original values |

Original principal is positive when supplied. Unknown is null rather than zero.
A known rate may be zero. Dates cannot contradict the accepted position date or
place closure before origination. Unknown actual closure date remains null; the
position as-of date is not substituted into it. Supplied original terms are
descriptive and do not require a current economic or monitoring policy.

Principal/interest/fees in the position are zero debt, not amounts collected.
There is no payment total, payout cash, accrued-interest total or invented release
receipt. A custody assertion is an accepted position, not a newly performed
physical handover event. Unknown custody remains independent of zero debt.

The document is at most 2 MiB. Duplicate keys, fractional JSON numbers, nonfinite
numbers, malformed identities and unsupported fields are rejected. Decimal
values use strings. Retained evidence has its existing 1 MiB/depth/type bounds.
Additional keys for events, approvals or policies are not silently accepted.
Complete historical restoration keeps its existing separate versioned profile.

## Legacy source adaptation

The [adapter](../../apps/tenant_apps/data_portability/legacy_closed_positions.py)
applies the owner's 9 October release interpretation only to namespace
6ca968d6-2647-4dbb-8e39-24f0c1a12ed6 and exact legacy source systems jcl, jsk and
lakshmipawnbroker. One matching release row establishes an import candidate with
zero debt and returned-to-borrower custody. A different installation/schema
cannot inherit this interpretation merely by using a similar status name.

The existing NO_RELEASE_ROW; OWNER_REPORTS_CLOSED cohort can produce a candidate
from its retained owner decision and explicitly reported zero balance. Its actual
closure date and physical handover stay unknown where not supplied. Today's
release-row interpretation does not retroactively supply a missing release row.

Mutable raw loan amounts and available old receipts are preserved in retained
evidence. They are not promoted into original principal or financial events.
Missing receipts, item rows, pricing, rates or tenure do not block the position.
Exact Party/register mapping, source snapshot fingerprints, duplicate ordinary
identities, permissions and owner review remain admission responsibilities.

## Active positions and compatibility

The corresponding active-position route reuses the published reviewed-opening
contracts. It needs a dated principal/interest/fee position and enough supported
terms, period/advance coverage and item allocations for ongoing calculations.
It does not need old receipts or digital origination approval/quotes. Missing
current risk inputs remain explicit coverage limits. Active position and complete
Rokkad-history restore contracts are not relaxed by this closed-position profile.

Future ordinary closed admission must preserve this source/coverage distinction
in its canonical position and export, and refuse live financial mutation or
historical balances it cannot establish. Current positive/native invariants
must not be globally relaxed merely because this input permits absent terms.
