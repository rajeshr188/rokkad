---
status: deployed
owner: loans
updated: 2026-10-10
tags: [loans, directory, search, import, rehearsal]
---

# IP-05: ordinary browsing and measured source search

Follow the [position-import plan](../plans/loan-position-import.md) and
[directory decision](../adr/2026-10-09-loan-directory-after-position-admission.md).
Implementation and 294 fresh-PostgreSQL checks pass. All 39,196 eligible real
source positions have been admitted in the isolated production-derived copy,
with 19 contradictory date pairs held. Search counts and selected records pass
the complete-query reference. The later [production rollout](loan-position-import-release-20261010.md)
verifies the compatible switch and all 39,196 eligible live conversions.

## Staff-facing behavior

Loans remains the primary list. Accepted closed positions are ordinary CLOSED
loans with ordinary detail links and retained source/media access. They do not
also appear as pending source cards. Running DRAFT/APPROVED/ACTIVE loans precede
completed records, ordered by original date within each group. Unknown original
dates appear last; true entry timestamps remain unchanged.

Remaining unadmitted claims are labelled Source record / Awaiting admission.
Remove the separate Historical loans sidebar entry. Retained source documents
and all immutable snapshots remain accessible through secondary directory tools
and existing authenticated URLs. Local borrower/licence/series filters use real
local mappings; search also preserves original numbers, source IDs and source
borrower names after admission. No history, evidence, attachment or financial
guard is removed.

## Query changes

Migration 0066 adds stored database-generated source number/name/original-date
fields to HistoricalLoanEvidence. These cannot be independently supplied or
edited and do not change the immutable document, hash or portable profile. Null
facts remain unknown. No new Workspace table, role, search service or global
PostgreSQL setting is introduced.

For narrow searches, collect at most 501 matching retained IDs before checking
source identity/latest snapshots. Up to 500 uses a compact candidate query;
broader searches use the complete SQL fallback. If the fully checked pending
set itself has at most 500 IDs, reuse those IDs for count and page instead of
repeating the expensive source checks. Larger pending sets retain the full query.
Latest snapshots are checked
against the entire source universe, including newer nonmatching snapshots.

Known closed-position source FKs can be excluded early only when their exact
namespace/system/source binding also matches. An FK or name alone cannot hide
an unresolved source. Other snapshots and older origins retain the existing
identity checks. Closed-position search uses ordinary numbers, source metadata
and generated fields rather than repeatedly decompressing copied source graphs.
Older financial-profile aliases remain searchable, with their own narrow
candidate optimization and complete broad fallback. A SQL CASE prevents the
older alias branch from evaluating copied JSON for closed-position origins; a
joined marker filter alone did not prevent that work in the measured plan.

Number claims use the generated retained number and compact old alias values.
Closed-position numbers are already covered by their guarded ordinary loan
number. All normalization, uniqueness, source collisions, reservations,
sequence locks and range rules remain in force.

Results-only HTMX requests skip New loan readiness/setup work. Full pages,
history restores and boosted requests retain it. Access, cache headers and
financial entry checks remain unchanged. SQL still filters/counts/pages the
combined projection and hydrates only the selected 25 cards.

## Verification

294 checks pass in a fresh PostgreSQL database. Coverage includes native draft
entry and isolation, older import aliases, source aliases after closed admission,
latest-snapshot changes, invalid source scope and inconsistent origin FKs, a
503-result broad fallback and last page, null generated fields and rejected
independent edits, fragment/full-page readiness, closed admission/guards,
concurrent batch replay, rollback, portability and retained source/media access.

A midnight run exposed a new closed-position guard comparing Python's India
business date with PostgreSQL's UTC CURRENT_DATE. Migration 0067 replaces only
that comparison with the statement's Asia/Kolkata business date. UTC storage,
other posting guards and future-date rejection remain unchanged. Tests cover a
UTC connection at the India midnight boundary and direct database rejection of
a future position. No financial history or source facts are rewritten.

The bounded 36-file loan-only candidate is derived from the live image and
preserves deployed billing. The isolated copy passes owner-only migrations
0065/0066/0067, restricted startup and schema consistency. Production remains at
0064. Runtime and conversion roles remain restricted; media mounts are read-only.

### Real-source conversion

| Workspace | Ordinary closed positions | Held source claims |
| --- | ---: | ---: |
| JCL | 26,649 | 15 |
| JSK | 3,836 | 4 |
| Lakshmi | 8,711 | 0 |
| Total | 39,196 | 19 |

JCL includes the exact 190 identity/hash recovery cohort. The full review signs
all 26,649 JCL candidates; a slower earlier candidate is stopped and that same
review resumes without duplicate admissions. JSK and Lakshmi run independent,
bounded jobs. Each accepted loan has one immutable origin and one zero opening
checkpoint; no payout, receipt, approval or physical-return event is fabricated.
All original existing loan/event/provenance/source/sequence fingerprints and
every retained source hash pass verification. The 19 held claims remain visible.
Private manifests, mappings, source graphs and query parameters stay on the server.

### Search acceptance

Restricted read-only measurements on the fully converted copy cover 78 requests
across three Workspaces and 13 cases: existing/converted numbers, source IDs and
names, prefixes, blank/no-match searches, CLOSED/ACTIVE, ordinary mode, dates,
local borrower and page two. All requests pass; all 39 case comparisons agree
with the complete-query reference. The final refinement also preserves counts
and selected-record hashes from the earlier full-cohort candidate.

Measurements use the same completed cohort and reader limits of 0.5 CPU/1 GiB.
The original IP-04 reader's repeated existing-number times were 7.217 / 2.944 /
3.344 s for JCL / JSK / Lakshmi. The final 78-case run yields 3.123 / 0.163 /
0.271 s; an earlier matched experiment yields 0.548 / 0.184 / 0.317 s. Repeated
converted-number requests also improve in all three Workspaces. These are server
measurements, not a production latency guarantee; variability remains visible.

The JCL plan initially evaluated old alias JSON across 29,087 origins before
checking the joined marker. CASE gates that work. Broad plans additionally spend
about one second compiling each duplicated source count/page branch; a bounded
pending-ID probe reuses the fully checked small pending set. No global JIT change
is needed. The blank JCL list drops from roughly 3.8 s before this refinement to
1.766 s in the final run. JSK/Lakshmi measured 1.167 / 1.356 s in the matched
experiment; the final run records a JSK outlier of 3.242 s and Lakshmi 1.354 s.
Broad views can still take several seconds. Raw timing reports remain private;
aggregate acceptance retains the variability instead of promising instant lists.

The baseline prefix counts can differ deliberately because IP-05 adds scoped
source IDs and original borrower aliases to ordinary-loan search. All final
counts and selected IDs match the complete new-contract reference and the prior
full-cohort candidate, including broad filters and later pages.

## Coordinated production release

This phrase means a compatible application/schema/data transition, not another
requirement to reconstruct old receipts. Take a fresh recovery checkpoint and
check capacity. Apply migrations 0065/0066/0067 through the owner-only configuration,
switch compatible web/worker readers under the restricted runtime role, and
verify startup and ordinary workflows before converting reviewed eligible batches.
Then reconcile admissions, retained exceptions, source access, counters and
search results. Stop/resume failed chunks without deleting successful admissions
or restoring a checkpoint over later customer transactions.

The exact 190-record JCL recovery input remains temporary and unchanged. The
19 contradictory date pairs remain retained source claims, pending correction
review; they are not silently admitted or rewritten. The later [production
rollout](loan-position-import-release-20261010.md) completes the compatible
migration/application switch, all 39,196 eligible conversions and final acceptance.
The isolated search measurements above remain rehearsal evidence, not a production
latency guarantee.
