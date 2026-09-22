---
status: implemented
owner: project
updated: 2026-09-23
tags: [loans, portability, contracts]
---

# Opening evidence with payments: loan-opening-export/2

Version 2 extends the [v1 contract](loan-opening-export-v1.md) with one required
`repayment_lines` evidence section. All v1 row fields, manifest fields, limits,
source-local reference semantics and exclusions remain the same. The
[published row inventory](loan-opening-export-v2-rows.json) freezes the additional
per-item allocation fields. Monetary values remain finite decimal strings.

Export selects v2 when any `REPAYMENT` exists, including a subsequently reversed
payment. Histories without payments retain v1. The parser rejects payment events
labelled v1 and unexpected/missing sections rather than dropping allocation evidence.
Existing v1 fixtures continue to parse and restore unchanged.

New collections carry `opening-payments/1` event evidence and the rule
`reduced-principal-next-anniversary/1`. They retain the opening event reference,
operation, request identity, cumulative baseline at cutover and collection, and
interest recognized since cutover. Original anniversaries, inclusive day-after
charge boundaries and cumulative whole-rupee HALF_EVEN rounding remain intact.
Principal payments lower subsequent monthly charge bases; interest already earned
does not change. Repayment evidence records cash components, scheduled versus
unscheduled interest and each item's principal allocation. Full release and
newest-first coupled reversal use the same continuation.

Restoration additionally requires repayment permission and replays collections
through their financial services at the retained business dates. Item and event
IDs are rebound; source actors and timestamps remain source evidence rather than
being impersonated. The rebuilt graph, including every repayment allocation row,
must match before commit. Zero debt with collateral still held is a valid active
loan; only an explicit full release closes it. Binary files and prior transactions
before the opening remain outside this contract.
