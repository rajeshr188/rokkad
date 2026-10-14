---
status: deployed
owner: project
updated: 2026-10-12
tags: [dashboard, performance, workspace, authorization]
---

# Dashboard section loading

The five-file candidate builds on the deployed [monthly batching fix](dashboard-performance-release-20261012.md).
The ordinary Workspace dashboard renders navigation, search, New loan and setup
without running the counter-work or business-overview selectors. The existing
route accepts section=queues and section=overview for independently loaded HTML;
section=full retains a complete server-rendered fallback.

Each fragment repeats canonical membership/data.view checks and requires both
request.workspace and the PostgreSQL Workspace context to match its target.
Background reads do not change the saved navigation preference. GET/HEAD only
and no-store responses apply; partials carry an explicit response header. The
browser rejects unexpected/login HTML rather than inserting it into financial
sections, returns through ordinary navigation when authentication redirects,
and offers retry messages. A restored browser-history page reloads fresh data.

Queues load first. Overview waits until queues settle and it is visible. Request
permission context is passed directly to partial templates so global shell
context processors are not repeated. There is no global authorization cache.
Filters, review warnings, dates, amounts, health coverage and pagination retain
the canonical selectors and current templates. The complete fallback preserves
its mode across queue links, pagination and activity forms without JavaScript.

## Verification before release

28 distinct focused checks pass: 20 counter/overview/health checks, five restricted
HTTP cases and three Chromium cases. Browser checks cover desktop/mobile search,
a deliberately held queue request with usable navigation/search, lazy overview,
activity filtering, JavaScript-free pagination, retries after 503, rejected bad
fragments and expired login. Python/app boundaries, loader syntax and scoped
whitespace pass. Screenshots of synthetic fixtures were visually inspected.

Two old test assumptions were corrected: current Workspace creation lands on
setup rather than plans, and loan search uses result cards rather than tbody.
Dashboard fixtures use the existing explicit test entitlement helper; public
billing/configuration activation remains covered by its own tests and is unchanged.

A 202-table/967,885-row backup restored into a separately named database with all
row fingerprints matching. Restricted READ ONLY comparisons for all three live
Workspace datasets match every queue and overview result between fragments and
the complete fallback. Shell calls invoke neither financial selector. Startup,
no pending migration/schema drift, native/closed readers, bounded worker and prior
checkpoint rollback readers pass; financial source rows remain identical.
The isolated first cold shell took 2.596 seconds under the rehearsal resource cap;
subsequent JCL/JSK shells took 0.081 seconds. These exclude middleware/browser and
are not a latency guarantee. Final live measurements belong to the release below.

Standard collectstatic generated an isolated candidate volume; all 242 existing
asset mappings are preserved and the new loader content hash matches its source.
Production assets are untouched during preparation. No migration, financial
formula, posting, policy, risk-refresh behavior or financial cache changes.

## Remaining portfolio cost

This changes when work runs, not its financial meaning. Queues and overview still
process portfolio evidence once requested. A visible overview still takes time;
database pagination and maintained dated financial summaries are separate work,
requiring correct queue counts and explicit freshness/reversal invalidation.

## Production release

Deployment completed on 12 October 2026 at 22:48:39 IST. Web and monitoring share
rokkad:dashboard-sections-20261012-fb9c494297df, immutable image
sha256:fe76e58ee9d07609059a8a59b47db09ce5a3f188b109a31cfd995533a0317c6b.
The five-file source delta is
fb9c494297dfc99ac5c8c83ad8cd8dad22138f80e73b8c2bce83a0044ff9b2dd;
checkout ancestry is 6dc71e4a673751aaa19a658a9f326b9ba2427864. The dirty checkout
was not delivered wholesale. Pending Party/portability work remains excluded.

Exact candidate-image recovery passed; the key remained local and transient
plaintext image files were removed. Protected settings, credentials, environments,
commands and worker caps are unchanged. The new isolated collected asset volume
replaces only the static mount and preserves all prior mappings. Its hashed
loader was verified over HTTPS. Rollback restores the previous image/static pair
without rewinding later database transactions.

The switch took 19.007 seconds; sampled HTTPS unavailability had an observed upper
bound of 14.418 seconds. Native/closed readers, startup and HTTPS passed; six timers
resumed. First worker turns have zero errors. The disposable local test and isolated
rehearsal databases/staging copies are removed. Post-release backup and fresh capacity/recovery verification passed. Verified backups
are production-20261012T170541Z.dump and production-20261012T172005Z.dump;
their checksum/recovery/retention proofs are retained in the ignored release evidence.
Disk capacity is 8.8 GiB. The initial pre-backup low-space warning
from the temporary restore cleared after cleanup; final proof has no warning.
No live database or retained backup was removed by rehearsal cleanup.

Final live READ ONLY checks preserve all queue and overview results against the
complete fallback. Both containers have zero restarts and the first three worker
turns have zero errors. These empty turns are health checks, not throughput evidence.

| Workspace | Initial / repeated shell | Queues | Overview | Complete fallback | Shell queries |
| --- | --- | --- | --- | --- | --- |
| jcl | 0.9 / 0.041 s | 1.702 s | 2.672 s | 3.813 s | 46 |
| jsk | 0.04 / 0.038 s | 0.961 s | 1.361 s | 2.366 s | 46 |
| lakshmipawnbroker | 0.035 / 0.035 s | 1.805 s | 2.343 s | 4.044 s | 41 |

Each measurement is direct view/template work; middleware, network/CDN, assets
and browser rendering are excluded. The first JCL shell in a fresh diagnostic
process took 0.900 seconds; subsequent shells took 0.035–0.041 seconds. Real first
page loads can incur additional cold/browser/transport work. Section calculations
still take their canonical portfolio time. Whole-page query work can increase
because independently authorized requests repeat access checks; no query-count
or full-portfolio cost reduction is claimed here.

Local tests/screenshot artifacts and safe final proof are under the ignored
.tmp/dashboard-sections-20261012 folder. Server proofs remain under the matching
release folder in the established deployment root. The prior static volume/image
are retained for same-schema rollback.
