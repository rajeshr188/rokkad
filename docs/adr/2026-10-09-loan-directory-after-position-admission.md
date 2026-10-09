---
status: accepted
owner: loans
updated: 2026-10-10
tags: [adr, loans, browsing, search, source-evidence]
---

# Ordinary loan browsing after position admission

## Context

The owner selects IP-05 after accepting ordinary imports from a known position
without reconstructing earlier transactions. The earlier unified directory is
still useful for unresolved source records, but a new admission timestamp must
not put thousands of old closed loans ahead of running loans. Routine searches
must not repeatedly decompress their retained source graphs.

## Decision

Loans is the primary directory for native, paper and imported loans. Accepted
closed positions appear once as ordinary CLOSED loans. Only unadmitted source
identities appear as clearly labelled source claims. Retained source documents
and all immutable snapshots remain accessible through secondary tools, existing
detail links and existing authenticated URLs; remove the separate Historical
loans sidebar entry. Do not delete evidence or invent historical events.

Order DRAFT, APPROVED and ACTIVE loans first, then completed/cancelled loans and
unadmitted closed claims. Within each group, order original loan dates descending,
then actual entry timestamps and stable kind/ID tie-breakers. Unknown original
dates sort last in their group. Neither original dates nor entry timestamps change.

Add three stored PostgreSQL generated fields to retained evidence: source loan
number, borrower name and ISO original date. They derive exclusively from the
immutable source document, cannot be independently edited, preserve null facts
and do not alter source hashes, portable profiles or tenant ownership. Apply the
ordinary Django additive migration with the owner-only migration configuration;
web/read/conversion roles remain restricted and forced RLS remains in place.

Narrow retained searches select at most 501 matching IDs to decide whether a
500-candidate optimization applies. Larger matches use the complete SQL query;
the bound never caps real results. Broad directory queries also probe at most
501 fully checked pending IDs. A small pending set is reused for count/page;
larger sets keep the full query. Latest-snapshot checks always use the full
source universe, so an older matching snapshot cannot reappear when its newer
snapshot no longer matches. Certified closed-position evidence FKs can be excluded
before older identity checks; remaining snapshots and origins still use the
existing namespace/system/source binding rules, including invalid-scope guards.

Ordinary search retains canonical borrower/number/licence/series fields and
older financial-profile number aliases. Closed-position search uses the ordinary
number, scoped import/source identities and compact retained fields instead of
scanning the copied source graph. Older JSON alias searches use the same bounded
candidate optimization with a complete broad fallback. A SQL CASE gates old
JSON evaluation: a joined marker filter alone still scanned closed-position
graphs in the real-cohort execution plan. Duplicate-number checks
use the generated retained number and still preserve old import aliases, locks,
normalization, reservations and range checks.

Results-only HTMX requests omit New loan readiness queries. Full pages, history
restores and boosted requests retain setup guidance and existing access checks.
No balance, posting, servicing or loan-health calculation changes.

The new closed-position admission guard compares effective dates with the
statement's Asia/Kolkata business date, consistent with existing Python business
dates. Migration 0067 corrects the UTC CURRENT_DATE mismatch found after midnight;
future-date rejection and other financial guards remain intact.

## Consequences

Closed position admission and browsing remain distinct from financial history
reconstruction. Original source aliases remain searchable after admission, and
unknown lifetime cash totals remain unknown. Local Party/licence/series filters
apply only to established mappings, never inferred names or source-local IDs.

IP-05 requires complete-result tests and real-cohort query measurements in an
isolated production-derived database. Production conversion still requires the
compatible reader/schema release, a fresh checkpoint and independently committed
reviewed chunks. No global JIT change, external search service or evidence deletion
is introduced. See the [delivery record](../implementation/loan-position-import-ip05.md).
