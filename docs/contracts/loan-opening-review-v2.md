---
status: active
owner: project
updated: 2026-09-12
tags: [loans, portability, continuation, review]
---

# Opening review v2: inclusive anniversary collection checkpoint

This technical review format supports the agreed original-anniversary collection
baseline. It is not a public import upload or proof of source balances. The existing
bounded review command accepts it; dump preparation still leaves missing facts
empty. Explicit `jcl-owner/2` preparation now emits v2 candidates without approving
them; other preparation keeps its previous profile. Version 1 remains
available with its previous period semantics. Users do not need to write JSON.

Use the exact same root groups, common fields, source identity checks, amount/file
bounds, collateral and obligation reconciliation as [v1](loan-opening-review-v1.md),
with `profile: loan-opening-review/2` and these differences:

Collateral may identify `BRONZE` explicitly and use JSON null for an unrecorded
`gross_weight`. Net weight must remain positive, purity separate, and
`weight_reference` nonempty. A supplied gross weight must be positive and at least
the net weight. Null never permits inventing a gross weight, custody, valuation or
original maturity. Ordinary new-loan forms and approval still require gross weight;
v1 and complete-history input remain strict. See the
[collateral decision](../adr/2026-09-12-legacy-collateral-evidence.md).

An explicitly reviewed unknown valuation uses the exact alternative object
`{"status":"UNVERIFIED","source_amount":"17325.00","source_date":null,"evidence_reference":"Owner confirms old undated source value"}`.
Both source amount and source date may be null; supplied amounts must be positive
and bounded and dates cannot postdate cutover. The evidence reference is required.
This creates no approved appraisal and never supplies current collateral value or
LTV. Plain `valuation: null` still means unfinished review. Full settlement of an
opening may return all collateral without a valuation; partial release remains
blocked without its required evidence. Later dated appraisals work normally and
are retained through export/restore.

The opening commit setup may include nonempty `legacy_license_evidence` when the
source used a grouping label without legal validity. This requires an inactive
legacy-reference licence/revision with unknown dates; known verified licences are
not silently converted. The source label must still match, and native lending and
complete-history rules stay strict. See the
[unknown-evidence decision](../adr/2026-09-12-legacy-opening-unknown-evidence.md).

| Terms field | Required value |
| --- | --- |
| `rule_id` | `original-anniversary-upfront-inclusive/2` |
| `period_rule` | `ORIGINAL_ANNIVERSARY` |
| `interest_basis` | `ORIGINAL_PRINCIPAL` |
| `partial_rule` | `INCLUSIVE_UPFRONT` |
| `partial_cutoff_days`, `partial_lower_fraction` | null |
| `rounding_scope`, `rounding_mode`, `interest_quantum` | `AGGREGATE`, `HALF_EVEN`, `1` |

Each item's remaining principal must equal its original principal. Reduced
principal requires a separate agreed continuation treatment; naming this rule does
not silently choose how a partial payment affects later interest.

Replace the v1 `continuation` object entirely with these exact fields:

| Field | Meaning |
| --- | --- |
| `covered_through` | ISO business date, exactly equal to cutover |
| `additional_months` | Integer 0–1,200 matching inclusive original anniversaries at cutover |
| `recognized_interest` | Decimal string: reviewed cumulative baseline through cutover, excluding the first paid month |
| `recognized_unpaid_interest` | Decimal string: exactly opening unpaid interest, no greater than recognized baseline |
| `first_month_paid` | Boolean true, supported by reviewed evidence |
| `evidence_reference` | Bounded nonempty reference for the reviewed coverage and recognition |

The validator recomputes cumulative baseline: sum unrounded monthly item charges,
multiply by additional months, then round once to whole rupees using HALF_EVEN.
`document_reconciled` checks supplied facts and arithmetic; `import_ready` stays
false. It does not prove actual first-month payment, receipt history or approval.
The report container/COMPLETE marker retains its review-report v1 format; each
result identifies its document profile independently.

For a 10,000 loan at 2% dated January 10, February 10 is still covered by the first
paid month. February 11 adds 200. At a March 15 cutover, cumulative additional
interest is 400. If reviewed unpaid interest is 290, the opening records 290 and
continuation recognizes the full 400 baseline. April 11 adds only another 200.
The difference of 110 is not automatically classified as a payment or concession.

For a monthly charge of 148.20, cumulative rounded charges are 148, 296 and 445.
A cutover after the first charge leaves later increments of 148 and 149; rounding
each later month to 148 would incorrectly reduce the total.

`preview_opening_collection` consumes frozen opening evidence and returns a labeled
unposted increment and next increase date. The exposure selector uses it instead
of native daily projection. Supported later events are full-release catch-up,
settlement and their coupled reversals. Readers validate paired evidence, stop
projecting during a closed interval and resume after reversal. Other later events
remain unsupported. Preview alone never changes the recorded balance.

`persist_opening_repayment_schedule` materializes reviewed remaining obligations
under the existing owner-only historical setup permission. It preserves original
due dates/maturity, verifies retries and rolls back partial creation. Exposure
requires that schedule; delinquency uses reviewed grace. This service requires an
already persisted opening and does not create or authenticate one. The
[authorized opening command](../adr/2026-09-12-authorized-opening-commit.md) now calls
it inside the same transaction as the opening and its identity binding. It also
requires reviewed tenure, source licence number and servicing policy; preview
rolls back the full command and commit confirms its exact fingerprint.
The dedicated full-release workflow now posts collection catch-up and
settlement atomically; reversing the release restores both, schedule and custody.
See the [servicing decision](../adr/2026-09-12-opening-full-release-servicing.md) for
payload and allocation semantics. Native periodic posting, partial repayments,
ordinary opening correction remains unsupported.
The [opening export and dedicated restore](loan-opening-export-v1.md) preserves
and reconciles the supported graph before confirmed atomic restoration.
The [one-loan source bridge](../flows/legacy-opening-import.md) now verifies the
dump and stages an immutable prepared review for owner browser approval. It leaves
unresolved source facts held. The domain commit is tested with synthetic
evidence only; `loan-history/1` explicitly rejects opening histories.
