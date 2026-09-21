---
status: accepted
owner: project
updated: 2026-09-12
tags: [loans, portability, numbering]
---

# Historical Loans setup preparation

Following [evidence protection](2026-09-12-loans-history-evidence-guards.md), expose
a read-only preparation form backed by Loans-owned setup checks. Reuse existing
licence revisions, series and product versions. No imported setup objects,
activation, mapping persistence or new tables are introduced.

The first profile remains flexible partial payment, NONE amortisation, FLEXIBLE
frequency and REDUCE_PRINCIPAL. Require exact source licence number/date coverage,
source calculation contract and operational grace, tenure bounds and original-date
product availability. ACTIVE/RETIRED product versions may represent historical
contracts; DRAFT fails. Current licence/series active flags do not rewrite history.
This is setup compatibility checking, not proof that source financial evidence is
complete or matches all native calculation semantics.

Candidate local numbers are `H/<source UUID hex>/<20 hex SHA-256 characters>`.
Hash input is document kind, a null separator and stable source entity ID. Loan
and release have distinct kind domains; source display numbers do not control
identity. Candidates fit the existing 64-character columns. Exact source display
numbers remain required input and must become provenance in the eventual importer.
The check detects existing local numbers and overlaps with any configured future
sequence range of the same document kind, including inactive sequences; more than
1,000 sequences fails this bounded preview. No allocator is called and no number
is reserved. Source replays and hash collisions are not silently treated as success.
Future commit must recheck under locks and provide persistent source uniqueness
and numbering protection; this preview does not supply those guarantees.

Read preparation requires current explicit Workspace, canonical owner/membership
or existing platform override, data.view, data.import and workspace.settings.manage,
and ACTIVE lifecycle. Normal HTTP commercial checks and CSRF remain in force.
There is no permission to commit historical financial events through this page.

The [operator flow](../flows/loans-import-preparation.md) describes the delivered
boundary. The financial graph parser, staged preview, historical command, source
provenance, locked reservations and canonical Loans export remain the next work.
