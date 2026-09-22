---
status: implemented
owner: project
updated: 2026-09-12
tags: [loans, portability, contracts]
---

# Opening evidence download: loan-opening-export/1

Histories with repayment events now use [version 2](loan-opening-export-v2.md).
This v1 contract remains unchanged for histories without payments.

This is a UTF-8 JSONL evidence download of one accepted v2 opening and its supported
later servicing. The dedicated operator restore supports this format after full
preview and graph reconciliation; complete-history browser upload remains separate.
Owners download
it using **Export loan data JSONL** on an active or closed loan. Opening loans use
`loan-opening.jsonl`; supported complete histories still use `loan-history.jsonl`.

## Manifest and bounds

Exactly two records: manifest, then evidence. The manifest contains:

| Field | Meaning |
| --- | --- |
| `profile` | `loan-opening-export/1` |
| `coverage` | `OPENING_AND_SUPPORTED_SERVICING` |
| `financial_history_from` | Reviewed opening date |
| `as_of` | Later of today's application-local date and the last recorded event date |
| `history_before_cutover` | `UNAVAILABLE` |
| `restore_supported` | `true` for current producers; older `false` files are also accepted by the dedicated restore |
| `reference_scope` | Source Workspace ID and `SOURCE_DATABASE_LOCAL` ID semantics |
| `exclusions` | Pre-cutover transactions, binary files, Workspace configuration and Party master |
| `sha256` | SHA-256 of the canonical evidence record |

Limit: 5 MiB, 20 collateral items, 240 events, 10,000 supporting/list records in
total and 20 source verifications. Decimal values are finite strings, dates and
timestamps ISO formatted, UUIDs strings, and unknown gross weight remains null.
Canonical JSON sorts object keys, uses compact separators, retains Unicode and
forbids non-finite JSON numbers. It ends each record with a newline. The checksum
detects evidence changes; it is not a signature or independent source verification.

## Evidence record

The [published row definition](loan-opening-export-v1-rows.json) freezes every
row field as `[wire_type, nullable]`. It is a row inventory, not a full JSON Schema
for nested event/source documents. Loans-owned
[opening_contract.py](../../apps/tenant_apps/loans/services/opening_contract.py)
decodes these types independently of live model fields. Changing an ORM column's
type, name or nullability does not revise v1. The exporter adapter must retain
the existing wire names. See the [decision](../adr/2026-09-13-frozen-opening-wire-contract.md).

`reference` means a positive source-local integer; `integer` and `boolean` remain
distinct JSON types. `decimal` is a finite string; `date` and `timestamp` use the
existing ISO parsing rules, with timestamps aware and not future-dated. `uuid`
decoding retains earlier hex/integer compatibility; new exports use UUID strings.
`json` preserves nested evidence for its existing semantic validators. Decoder
types do not replace financial, relationship or destination admission checks.

| Fields | Retained information |
| --- | --- |
| `loan`, `items`, `policy` | Current loan/collateral state and frozen servicing policy |
| `origin` | Original source namespace/ID, accepted document, checksum, item/event mappings, import actor/time |
| `source_verifications` | Available completed staging batch identity and exact selected dump evidence; empty for direct domain imports without source verification |
| `events` | Exact opening, catch-up, release and coupled reversal payloads, fingerprints, idempotency keys, actor/time and reversal links |
| `accruals`, `accrual_lines` | Recorded aggregate calculation and any actual item lines; no invented allocation of aggregate rounding |
| `releases`, `release_items`, `release_reversals` | Cash, release numbering, valuations, return time and reversal links |
| `closing_lines`, `custody_events` | Item principal settlement and actual return/reversal movements |
| `schedules`, `obligations`, `schedule_changes`, `allocations` | Reviewed remaining obligations, termination/reversal and payment allocation evidence |
| `appraisals`, `change_log` | Dated valuations, references, lifecycle reasons and actors |
| `recorded_balance`, `interest_conceded` | Event-derived outstanding principal/interest/fees and net recognized concession |
| `collection_preview` | Unposted continuation estimate, cutover/current cumulative baselines, agreed rule and next interest increase date |

The explicit field allowlist is in
[opening_export.py](../../apps/tenant_apps/loans/services/opening_export.py).
IDs and nested frozen references identify records in the exporting database; they
must not be used as destination foreign keys. Party/configuration rows are outside
this file, though frozen source evidence can contain customer values. Source
verification is present only when it was actually performed by the staging bridge.

Export requires the existing owner historical-setup boundary plus `data.export`,
rechecked under locks with forced-RLS scoped reads. It checks frozen review,
collateral and policy bindings, one opening schedule, supported servicing, balance
and custody agreement. Unsupported funding/storage/renewal/rate-policy graphs fail
explicitly. Successful export adds an audit entry and no financial records.

## Restore boundary

The complete-history importer explicitly rejects this profile and directs the
operator to `restore_loan_opening`. Supply explicit destination Party, licence
revision, series and product version. Preview rebuilds all supported records and
compares the financial/physical graph under rollback. Commit binds the exact source,
Workspace and mappings to the reviewed fingerprint.

Restoration preserves recorded dates and return timestamps, recalculates supported
servicing, and allocates deterministic historical numbers without advancing native
counters. Source actors, timestamps and the complete original file remain immutable
provenance; destination records identify the restoring operator. Source-verification
records are retained claims, not a fresh verification of the dump.
Frozen appraisal quote IDs retain their source Workspace in
`valuation_context.source_workspace_id`; the appraisal page labels that scope.
This annotation is preserved on subsequent restores and does not assign a local
Rates record. Reconciliation checks quote amounts/context while allowing the added
source-scope annotation.

After explicit reference/number normalization, reconciliation compares all exported
financial and supporting records, excluding regenerated database IDs, local audit
actor/timestamps and derived fingerprints. An inconsistent or unsupported graph is
rejected atomically. The original source identity prevents duplicate activation;
changed input and existing ordinary origins conflict. Exact restore retries do not
repeat historical actions or reset later servicing.

See the [restore decision](../adr/2026-09-12-opening-restore-reconciliation.md) and
[operator instructions](../flows/legacy-opening-import.md#restore-an-opening-export).

Repeating the original opening is a separate operation. The original accepted
opening command in the same Workspace still returns its existing
origin and never resets subsequent servicing. That existing idempotency behavior
is **not** restoration of this exported snapshot. The dedicated restore command
performs opening-plus-servicing restoration and reconciliation together. It does not merge newer exports into an existing loan.
Repeated restore ancestry is preserved and must fit the same 5 MiB limit.
