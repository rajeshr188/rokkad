---
status: accepted
owner: project
updated: 2026-10-05
tags: [adr, loans, archive, browsing, rollout]
---

# Browse ordinary loans and retained historical evidence together

## Context and authorization

The owner requested automatic admission of JCL, JSK and Lakshmi closed archives,
or unified browsing if reconstruction requires separate reconciliation. The owner
selected presentation cleanup followed by LD-08, and requested a generated
fictional Lakshmi acceptance example instead of supplying a real source document.

The retained September 21 source review has 38,943 closed candidates, all lacking
verified original principal and reported balance in the normalized archive facts.
Missing normalized payments affect 16,156 records. Raw source amounts can be
mutable; a release row establishes a source closure claim, not a reconciled cash
settlement or confirmed physical handover. These are dated source observations,
not a current production inventory.

## Decision

The ordinary Loans directory includes retained closed historical records through
a read-only selector. Ordinary cards retain their existing detail and servicing
links. Historical cards clearly identify source claims and link to the existing
authenticated historical details. Unknown principal, dates, settlement and custody
remain unknown. No operational loan, event, obligation, cash amount, approval or
handover is created by browsing. Financial reports and monitoring keep their
ordinary-loan scope.

SQL filters and paginates a common reference projection before hydrating at most
25 cards. Every query is scoped to the explicit active Workspace, independently
of RLS. One latest retained snapshot appears per exact namespace/system/source ID;
the archive page retains all immutable snapshots. Financially admitted source
identities appear through their ordinary loan, using the existing scoped identity
rules, including evidenced older unscoped imports. Invalid legacy source scope
cannot hide evidence by matching an unrelated import.

Search supports original number, source ID and source customer name. CLOSED
includes historical closure claims; other operational states exclude them. Local
Party/licence/series filters cannot establish an archive mapping by name or old
database ID, so the interface explains their ordinary-only scope. Date filters
exclude unknown original dates. Records can be narrowed to ordinary or historical.

Automatic financial reconstruction is deferred. A future batch adapter may prepare
and reconcile complete histories, classify exceptions, and admit an explicitly
reviewed eligible batch through existing financial admission services. It must
not invent original principal, receipts, splits, agreed terms, cash movements or
handover merely to classify an archive as an ordinary closed loan.

## Consequences

Staff can find and read old closed loans from the familiar Loans list immediately
after deployment. Historical evidence remains evidence until reconciled admission;
the distinction is visible rather than hidden behind a separate navigation entry.
One New loan action remains prominent; completed-entry and archive tools are
secondary links to existing workflows. Current lending safeguards remain intact.

LD-08 clean-image verification also requires runtime contract resources in the
image. The Docker allowlist now includes `docs/contracts/`; no financial schema
change accompanies this browsing work. Local fictional acceptance and recovery
are distinct from live production inventory, operator acceptance and rollout.
See [delivery and remaining gates](../implementation/unified-browsing-and-ld08.md).
