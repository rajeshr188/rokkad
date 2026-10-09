---
status: reviewed
owner: loans
updated: 2026-10-09
tags: [loans, history, migration, archive]
related: [../adr/2026-09-13-historical-closed-loan-archive.md, ../adr/2026-10-05-unified-loan-browsing-with-retained-evidence.md]
---

# How Historical loans arose

**Subsequent owner decision, 9 October:** the owner confirms the old source's
released loans have zero debt and all collateral was returned, and selects
[ordinary position import without earlier history](../adr/2026-10-09-loan-position-import-without-earlier-history.md).
The new [IP-01/IP-02 delivery](loan-position-import-ip01-ip02.md) prepares and
classifies 39,196 candidate closed positions and 19 date-order exceptions without
admission. This supersedes the unscheduled next-decision description below;
conversion and ordinary persistence remain subsequent ordered work.

The owner requested this review after deferring the measured Loans-list search
improvement to [FW-022](../plans/future-work.md#fw-022-main-loans-list-search-performance).
This is repository/source-decision tracing, supported by the already completed
9 October read-only inventory. No application, database, loan, source document,
policy or production configuration is changed. It is not a new financial audit
of every retained record.

## The original migration problem

Before the archive existed, supported loan imports established either complete
financial history or a reviewed opening position for ongoing servicing. An old
released loan could have a release row but insufficient evidence for either
representation. An active opening was inappropriate for a completed loan; a
complete-history import would require facts the source did not establish.

The [12 September portability audit](../architecture/loans-portability-audit.md)
identified the missing destination for these records. The accepted
[13 September archive decision](../adr/2026-09-13-historical-closed-loan-archive.md)
added immutable source retention without constructing operational debt, approval,
payout, collections or custody. The goal was to retain old closed-loan details
even when financial reconstruction was unavailable.

## What the migration adapter actually did

In [legacy_archive_preview.py](../../apps/tenant_apps/data_portability/legacy_archive_preview.py),
`candidates()` walks source `girvi_loan` rows. Any associated `girvi_release` row
routes that loan to a CLOSED archive claim; a loan without one is excluded from
this adapter. It does not first attempt complete financial reconstruction for
each released loan. Therefore archive membership does not establish that every
individual record is incapable of reconciliation.

The document retains the source loan, items, payments, releases and available
customer/series/licence/recipient rows. Original references and raw values remain.
Normalized original principal and reported balance are deliberately null for
this legacy adapter. The documented source interpretation treats the stored loan
amount as mutable, not automatically verified original principal. No supplied
payment rows becomes unknown payment evidence, not a declaration that nothing
was received. Multiple release rows leave normalized closure date unknown.

Consequently, a blank normalized principal is not proof that no amount survives
in the original data. Raw item amounts and payment principal/interest fields may
be available. Whether they establish original principal and a complete timeline
requires checking source semantics, not copying a value into a verified field.
Likewise, absence of normalized payment evidence does not establish that a
closing collection never happened or cannot be corroborated from other books.

The [dated migration follow-up](../plans/loans-portability-audit-followup.md)
records source preparation, selected pilots and a 19 September rehearsal retaining
26,474 JCL released claims without changing operational loans. Those are older
source/rehearsal counts, not today's production inventory.

## Representations that are easy to confuse

| Representation | What it establishes | Normal use |
| --- | --- | --- |
| Ordinary direct-entry or recorded paper loan | The accepted original agreement and supported financial events | Servicing, balances, monitoring while outstanding, and ordinary closure |
| Ordinary migration-opening loan | A reconciled position at cutover plus its continuation contract; earlier source records remain evidence | Servicing and monitoring from the opening, then ordinary closure |
| Ordinary verified closed-position loan | Supported original agreement and verified zero debt at closure; earlier payout/receipt history explicitly unavailable | Ordinary closed-loan browsing without fabricated historical transactions |
| Historical loan evidence | The old system's reported closed record and retained source details, without a reconstructed financial timeline | Browse, search, read photos/details and export source evidence |

Historical evidence is not an extra operational loan status. In
[models/archive.py](../../apps/tenant_apps/loans/models/archive.py),
`HistoricalLoanEvidence` stores an immutable JSON document, review, source
identity/fingerprint and local acceptance actor/time. It has no borrower Party
or ordinary PawnLoan foreign key. Changed documents append snapshots; identical
acceptance retries reuse the same snapshot. Source people and register IDs do
not automatically establish current Workspace relationships.

`HistoricalLoanImport` is different: it binds an accepted financial origin to an
ordinary loan. Both complete-history and opening admissions use it; reviewed
archive admission can additionally link the original archive snapshot. It is
not the Historical loans list itself.

## Why the initial interface felt like missing data

The initial archive separated these records from the ordinary Loans list and
put many details inside JSON. The [readable-browser review](historical-loan-browser.md)
records the owner's resulting concern about lost closed-loan details. The later
presenter exposes customer/dates, collateral, retained item amounts/rates,
payments and supplied splits, release records and source fields. The original
document/export and existing private media remain accessible.

The upload tool stages an additional source document for retention review. It
does not unlock already migrated records or require uploading them again, and
acceptance alone does not create an ordinary closed loan.

## What changed after paper-entry adaptation

The [2 October unified recording decision](../adr/2026-10-02-unified-loan-recording.md)
and [3 October archive admission decision](../adr/2026-10-03-archive-admission.md)
allow a supported reconciled history to become an ordinary closed loan while
retaining original archive documents. The current archive admission service
requires checked complete history, CLOSED final state, identified supporting
sources and agreement with known retained claims. Renewal events in this
archive-admission route remain rejected. Original digital approval and historical
metal quotes are not requirements merely to record what already happened.

The subsequent [6 October evidence extension](../adr/2026-10-06-bounded-loan-evidence-extensions.md)
also supports a **verified closed position** through
[terminal_admission.py](../../apps/tenant_apps/loans/services/terminal_admission.py).
This can create an ordinary CLOSED loan without reconstructing unavailable
earlier receipts or payout. It requires verified original agreement/item
principals/rates/tenure/rounding, local mappings, dated closure, identified
supporting evidence and confirmation of zero principal, interest and fees.
Physical handover may remain UNKNOWN rather than be invented. The service
records a zero-debt terminal checkpoint and immutable source link, not a made-up
settlement collection; earlier cash and total interest collected stay unavailable.
The owner reaches this option from the specialist paper-history/archive review
form via **Record a verified closed position**. It is not automatic bulk conversion.

The [5 October browsing decision](../adr/2026-10-05-unified-loan-browsing-with-retained-evidence.md)
lets the familiar Loans list show both ordinary loans and retained history.
One latest snapshot per exact source identity is shown there; the dedicated
Historical loans page retains all snapshots. An admitted identity appears
through its ordinary loan rather than a duplicate historical card. CLOSED can
include both kinds. Local Party/licence/series filters cannot assume an archive
mapping from a name or old ID. Financial reports and monitoring still use
ordinary loans, not unreconciled archive claims.

These screens and workflows are now deployed; earlier local-only statements
in the original implementation records are superseded by the
[production release](loan-production-release-lo07.md) and
[9 October cumulative release](loan-ui-and-servicing-release-20261009.md).
The completed 9 October search investigation measured retained evidence counts
of JCL 26,664, JSK 3,840 and Lakshmi 8,711 (39,215 total). These are dated evidence
counts; snapshot rows and ordinary financial loans are different quantities.

## Product assessment and next decision

Retaining incomplete old records was useful; exposing source JSON as the primary
staff experience was the usability problem. The archive predates paper-first
adaptation and was not created because late-entry loans need a separate product.
Today a supported paper-origin loan can be an ordinary loan; an old source-only
record can remain browsable without manufacturing a financial history.

Do not assume all archived histories are irrecoverable: the adapter applied a
cohort-wide released-record route, and normalized unknown fields can coexist
with useful raw data. Conversely, do not assume all can be converted merely
because a release exists. Neither claim has been established by this review.

Keep routine closed-record access independent of financial conversion. If the
owner later selects reconstruction, first inventory source coverage read-only
and classify reconstructable cases, cases needing book confirmation, and
unresolved cases. Prepare source-backed mappings and timelines for a reviewed
eligible batch through existing admission services, choosing complete history
or verified closed position according to the evidence; preserve unresolved rows
as readable history. Do not force one-by-one staff reconstruction as a
prerequisite for seeing their old records, and do not invent balancing receipts,
concessions, approval or handover to make every record operational.

Search performance is a separate deferred query improvement. Moving archive
rows into ordinary loans is not required to fix it and must not be used as a
performance workaround.
