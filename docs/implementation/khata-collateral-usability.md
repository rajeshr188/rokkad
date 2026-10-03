---
status: implemented-local
owner: loans
updated: 2026-10-03
tags: [khata, collateral, photographs, search, selection, validation]
---


The later [document-navigation checkpoint](khata-document-navigation.md) records the current
local runtime; earlier checkpoint identities/counts below remain dated evidence.
# Khata collateral usability

The later [measured read-performance checkpoint](khata-read-performance.md) now
supersedes the earlier local runtime identity and addresses the initial eager
source/custody loading findings. Earlier checkpoints/review findings remain dated
evidence; hosted/operator/physical acceptance is still separate.


The guidance identity is recorded in the [action-guidance checkpoint](khata-action-guidance.md),
retaining prior reports/performance/exception/register/tab/collateral/collection
behaviors and verifying 469 regressions including existing archive checks. The searchable servicing follow-up below and earlier identities
describe their individual historical checkpoints.

The owner authorized the three improvements in the
[usability plan](../plans/khata-collateral-usability.md): receiving with photographs,
paginated collateral identification and searchable exchange groups. This changes
Khata UI and receipt/photo composition without changing financial terms, forced
RLS tables, migration state or ordinary-loan workflows.

## Searchable servicing follow-up (2 October)

Phase two reuses `selectors/khata_items.py`, the 25-row protected endpoint and the
existing picker script for pending handover, reduction approval and later photos.
Pending rows expose the active typed OUT source; GET handover resolves the selected
item within its account and derives the parent rather than trusting a URL parent.
JSON suggestions are not authority. Signed reviews, scoped Django choices, command
locking, current valuation/due checks and idempotent handover retry remain intact.
Native choices are the no-script and explicit search-failure fallback. No schema
changes or new financial/custody operations.

The 37 focused checks pass in 19.433 seconds; seven new cases cover source pairing,
GET without movement, signed multiple selection/edit, hard reduction LTV refusal,
photo held/pending eligibility, wrong/foreign/stale source refusal, viewer access
and exactly-once handover retry. Final frozen candidate
`khata-local-20261002-535598b92cbb` passes **406 Linux regressions in 197.108 seconds**.
Image: `sha256:51d3fe51099cc750948300a9a941808ef43044aa53e605e2ffa5af0ee1056112`.
All 1,403 application/settings files match both archive and actual image. Schema,
no-drift, dependency, restricted production-profile/static startup and owner refusal
checks pass. Current fictional records/media are preserved at localhost:8077, with
private pre-update backups/checksums and stopped prior web
`khata-img-20261002-web-pre-servicing-final` retained. Later edits update docs only.

Read-only Chromium checks verify exact source prefill, pending filters/links,
25-item pages, selection retention/removal, single-item replacement, latest private
photos/camera controls, native fallback on search failure and queued debounce,
existing exchange selections/receive links, viewer and foreign-account refusal,
mobile overflow and no-script controls. Register/tab/exception baseline checks pass.
Desktop/mobile screenshots are inspected; no page JavaScript errors occur. The QA
browser's CDN access was blocked; its routes serve the exact configured Bootstrap
5.3.8 CSS/JS bytes with matching application SRI hashes. No app asset configuration
or production changes result. Physical camera/phone/printer acceptance is still open.

Search responses are bounded, but native fallback options and whole-account replay
still scale with holdings/history. Representative performance measurement is the
next phase; these UI checks do not claim a large-account load benchmark.

## Register metrics and account tabs

The owner clarified that the metrics request concerns the Khata register. Four
existing filtered financial totals now occupy equal-height cards above the filter
form, with a shared heading/scope note. Matching count/range belong to the account
results-table header. Totals still cover all matched accounts before pagination;
no summary calculation or filter behavior changes.

Each detail renders one URL-selected section: Overview, Actions, Collateral,
Interest, History or Documents. Bootstrap navigation styling uses ordinary links,
so it works without JavaScript or browser preference storage. Mobile tabs scroll
horizontally using existing workspace styles. Action groups reuse `action_links`
and existing permission/write-availability checks, without new capabilities or
financial paths. Collateral/Interest offer relevant authorized shortcuts.

Legacy `section=collateral/history`, QR UUID anchors, history filter/page parameters,
exchange redirects and exact operation links select their proper panels. Invalid
or failed document POSTs select Documents so errors remain visible. Only the
active panel is rendered, reducing long pages and inaccessible hidden forms.
Document correction links reach exact History sources. Canonical balance replay,
photo/label privacy, confirmation and custody rules remain unchanged.

### Tabs verification and current local identity

The final image passes **395 Linux regressions in 183.149 seconds**.
The three new integration cases cover active-panel selection, legacy item/source
links, unchanged balances, document validation/issuance and permission-aware
servicing controls. The earlier full run found only a stale QR disclosure-markup
assertion; it now checks the selected Collateral panel and exact UUID anchor.
No application behavior changed to accommodate that assertion.

Actual Chromium acceptance is read-only and covers aligned register values above
filters, filtered total scope and results counts; all six sections; action groups;
private photo thumbnails; interest schedule; retained history filters and disjoint
pages; exact operation/exchange/UUID links; document controls; unknown-tab fallback;
viewer restrictions; mobile horizontal overflow and keyboard history scrolling;
and tab navigation without JavaScript. Desktop/mobile screenshots are inspected.
There are no browser page JavaScript errors. The workflow guide and stable memory
explain the new locations.

| Resource at that checkpoint | Register/tabs result |
| --- | --- |
| Candidate | `khata-local-20261002-0d22c65edc36` |
| Source inventory SHA-256 | `0d22c65edc3629906a3b9ba68ed8b82a5e113db3db4f3e5e1c1a0825804ab707` |
| Frozen archive SHA-256 | `14d0b75a0fa846949140ca1d0689bc1e0163fb039869d8a7e4b157ad91494add` |
| Image ID | `sha256:544544d43ae6ced2c9c62d97644a608baba46497afd431459265612beb0caa92` |
| Private verification/recovery evidence | `.tmp/khata-tabs-candidate-20261002-v2/` |
| Static volume | `khata-tabs-20261002-static` |
| Current web | `khata-img-20261002-web` |
| Retained previous web | `khata-img-20261002-web-pre-tabs` |
| Local review | `http://127.0.0.1:8077/w/khata-73081a4c/loans/khata/` |

All 1,399 application/settings files match the source manifest and actual image.
Later delivery documentation is the only archive difference. Schema, dependencies,
restricted production-profile/static startup and owner-startup refusal pass.
Existing fictional records/media remain intact with pre-update backups/checksums;
no production, hosted/remote CI or physical-printer acceptance is claimed.
Earlier source-history/camera identities below describe their prior checkpoints.

## Source-history follow-up

Owner-requested history pagination/sorting/filtering is implemented in the detail
page using a scoped read selector and an ordinary GET form. History alone uses
25-row SQL pages; existing canonical summary replay/document choices still use
complete account evidence. No financial command, tenant table or migration changes.
Event type, inclusive business-date range, newest/oldest date-plus-sequence order,
exact operation ID and item/reference search compose before pagination. Item
search covers receipt, photo/return and exchange membership; joins are deduplicated
so grouped exchanges do not create repeated event rows. Invalid filters show
errors and an empty result without changing known account balances.

Namespaced `history-*` GET fields preserve filters through paging independently
of document POSTs and custody navigation. Correction/parent links switch to exact
operation lookup, dropping prior filters and selecting the History panel.
This preserves source relationships across pages. Rows show recorded time,
actor, sequence, direct collateral links and recorded payment references. No raw
JSON or editable audit fields are exposed. Reads are private/no-store and scoped
to the current authorized account/workspace.

### Prior history verification and local identity

The 43 focused history/collateral/integration cases pass in 24.744 seconds,
including 52 same-day receipts, inclusive ranges, invalid parameters, grouped
item-search deduplication, cross-page corrections, unchanged balances, account/
workspace boundaries and a two-query bounded page with related item/actor reads.
`khata-local-20261002-16c741a72ede` passes 392 Linux regressions in 183.508 seconds.
Only the history table's min-width and keyboard scrolling are adjusted afterward;
the final seven history cases pass in 5.502 seconds. Manifest comparison proves
that template presentation is the sole subsequent application change.

Final actual Chromium checks are read-only: 25-row pages, date/type/item search,
oldest/newest sorting, filter retention, non-overlapping pages, exact off-page
sources, unchanged balances, empty results, invalid date errors, reset and viewer
access. Final desktop/mobile screenshots are inspected. A 760px minimum table
width avoids squeezing event descriptions; its mobile horizontal overflow is
keyboard-focusable and tested with ArrowRight. No page JavaScript errors occur.

| Resource at that checkpoint | Prior source-history result |
| --- | --- |
| Candidate | `khata-local-20261002-10e98f81aa49` |
| Source inventory SHA-256 | `10e98f81aa494539e2861c2343795d32d676fe8d6c19174d5db6e7d7d283a2c7` |
| Frozen archive SHA-256 | `38c19df2a72399f81c4581ef7cceba66458d32ea6b22d20ee8b7d312c86ff23a` |
| Image ID | `sha256:a7a03b562498cd8bf8a310368f1343a69de936f5015e2c7fe867001a045fac1f` |
| Final private evidence | `.tmp/khata-history-candidate-20261002-v2/` |
| Full regression evidence | `.tmp/khata-history-candidate-20261002/` |
| Static volume | `khata-history-layout-20261002-static` |
| Current web | `khata-img-20261002-web` |
| Retained previous web | `khata-img-20261002-web-pre-history-layout` |
| Local review | `http://127.0.0.1:8077/w/khata-73081a4c/loans/khata/` |

Current fictional records/media are preserved through each local switch, with
pre-update backups/checksums and stopped prior images. Browser acceptance makes
no business writes. All 1,398 app/settings files match the frozen source and the
actual built image; later changes update delivery documentation only. Schema,
dependencies, restricted production-profile/static startup and owner refusal pass.
Production, hosted/remote CI, physical/off-device acceptance remain unchanged.
Earlier camera/usability identities below describe their prior checkpoints.

## Camera and register follow-up

The owner requested webcam/mobile front/rear capture, item photos in lists and
clearer register amounts/custody. A shared progressive-enhancement partial adds
live video, facing/device choice, JPEG capture into the existing upload field,
still preview, removal and native mobile capture-picker hints. Camera permission
is requested only on an explicit click. Stream generation guards prevent late
permission/capture completions from reviving a closed camera; tracks stop on
switch, close, selected-file changes, submit and page exit. Pending JPEG encoding
prevents a save from racing the captured photo. File selection still works without
JavaScript, camera support or permission. Live capture needs a secure context;
native picker behavior/front-rear hints depend on the device/browser.

No new endpoint, photo storage, schema or financial operation is introduced.
Receiving and later attachment share the controls. Detail custody rows reuse one
scoped photo query and show the latest authorized private thumbnail with lazy
loading; all prior original photos remain in document history. UUID scan anchors
are preserved. The register displays **Agreed limit** and **Actual principal
outstanding** separately. **Items awaiting handover** links to pending custody
and explains item-record counts versus piece quantities. Permanent UUID, readable
Item ID and individual QR labels remain the identity contract.

### Prior camera validation and local identity

The 53 focused UI/integration/workflow tests pass in 28.496 seconds, including
JPEG receipt and latest-photo selection while original photos remain retained.
The camera candidate passes **385 Linux regressions in 183.491 seconds** and
existing schema/dependency/runtime/owner-refusal checks. No migration is needed.
Chromium uses a synthetic video device to verify actual JPEG capture and receipt,
front/rear constraints, closed late-request cleanup, removal, native capture hints,
simulated denial/file fallback, later camera attachment, private thumbnails,
separate agreed-limit/principal values, pending-custody links and mobile layout.
No JavaScript page errors occur; desktop/mobile screenshots are inspected.
This proves browser/software behavior, not physical phone/webcam selection.

| Resource at that checkpoint | Prior camera result |
| --- | --- |
| Candidate | `khata-local-20261002-cbb08c7071bf` |
| Source inventory SHA-256 | `cbb08c7071bfa304254675f20d8f3ccfd37421a3d078df7ea6fc811c2e5aac15` |
| Frozen archive SHA-256 | `7b15cf77b7b32d44b1e1a4e99c0c7a7a18bb2f423ef59de64d8fbb1655a099f4` |
| Image ID | `sha256:4f6630e45e98b0dfabc40dc0d0b25216f08c7b134d3d90ccdc9fe3e81fafff5f` |
| Private evidence | `.tmp/khata-camera-candidate-20261002/` |
| Static volume | `khata-camera-20261002-static` |
| Current web | `khata-img-20261002-web` |
| Retained previous web | `khata-img-20261002-web-pre-camera` |
| Local review | `http://127.0.0.1:8077/w/khata-73081a4c/loans/khata/` |

The same persistent fictional database/media remain in use. Full pre-update
backups/checksums are saved; original demos remain unchanged. Camera acceptance
adds Item 73 and two photographs to fictional KH00004, with no cash or physical
handover. Its two pending outgoing items remain pending. The archive and all
1,395 application/settings files match; delivery documentation changes afterward.
Production, remote CI, physical hardware and hosted/off-device gates are unchanged.
The preceding usability-only identity below is retained as historical evidence.

## Receiving and private photographs

**Receive collateral** includes item details, optional JPEG/PNG upload, a browser
preview and an explicit actual-receipt checkbox. Save returns to the browser with
the new item ID and label link; **Save and add another** opens a fresh form.
Workspace photo requirements are explained; later attachment and mandatory
approval/withdrawal/exchange checks remain available.

`record_deposit(upload=...)` validates before recording receipt. The fingerprint
includes photo SHA-256 when present; no-photo legacy calls retain their old
fingerprint. A deterministic subordinate UUID records a separate PHOTO source
inside the locked receipt transaction. Invalid or failed photographs roll back
receipt; identical retries return the same item/photo and changed bytes under
the same UUID are refused. Private paths are known before writing so partial-write
and row-persistence failures can remove only the new file. Unexpected failures
still propagate.

Save is a direct validated POST, with no temporary staging or binary data in
review/session state. Reviewed financial/custody commands retain existing signed
confirmation. Failed form submissions require selecting the upload again.

## Collateral browser

The detail page links **Search & browse collateral** to a read-only account- and
workspace-scoped browser. SQL filters search ID/UUID/description/storage, metal,
source receipt date and derived custody. Stable receipt-date/ID sorting and
25-item pages avoid rendering whole holdings into selection widgets.

Rows show identity, private photo thumbnail, quantity, metal, weights, purity,
storage, receipt date, custody and today's valuation suggestion. Missing current
quotes produce unavailable, not zero. Custody derives from actual return/handover
sources and active OUT reservations. Existing detail/scan anchors remain intact.
JSON search is private/no-store and bounded to one page.

Thumbnails use the authorized photo route with `thumbnail=1`. Original size/SHA
are verified before producing a JPEG at most 160 x 120 pixels. Original photo
rows/bytes are unchanged and no additional retained file is written.

## Exchange selection

Outgoing and incoming use searchable checkbox tables and visible selected groups.
Search/paging retains selected IDs in the current form. Incoming excludes active
prior IN membership; both exclude returned/reserved items. Items cannot occupy
both sides. Form selections are scoped; service confirmation checks stale evidence.

**Receive replacement collateral** carries selected IDs into receiving and returns
to the same exchange. The new item is suggested for explicit selection; receipt
does not record exchange membership. No arbitrary redirect URL is accepted.
Review shows exact outgoing/incoming counts, net weights and values by metal,
shortfalls and retained cover. Incoming value already belongs to the held pool,
never added twice. Confirmation offers actual handover while maintaining pending
outgoing custody.

No new framework, identifier scheme or tenant table is added. Browser values are
suggestions; approved values and current policies govern posting. See the
[staff/developer workflow](../flows/khata-account-workflow.md).

## Prior usability-only validation and candidate

The 45 focused UI/storage/search and existing opening/workflow cases pass in
24.328 seconds against an isolated Docker test database, including 203-item
pagination, private thumbnail integrity, mandatory-photo boundaries, cross-account/
workspace refusal, partial-file cleanup and retry identity.

The final frozen image passes **384 Linux regressions in 185.540 seconds**, including
all existing Khata slices, RLS/storage and ordinary-loan/Party/dashboard/ticket/media
preservation. Bare numeric searches target the exact item number. Current migrations,
no model drift, dependencies, production-profile restricted startup/static and owner
startup refusal pass. No migration is applied to the pilot.

Actual Chromium checks cover owner/viewer login, receiving/photo preview, Save and
add another, 25-item pages, selections across search/paging, replacement receipt
returning with existing selections, explicit new-item selection, reviewed grouped
exchange, pending custody, private thumbnail display, stacked mobile pickers and
viewer-write refusal. Desktop receiving/exchange/browser screens are visually
inspected with the existing public Bootstrap/icon assets loaded.

| Identity or resource | Prior result (before camera follow-up) |
| --- | --- |
| Source candidate | `khata-local-20261002-569b1175f32e` |
| Source inventory SHA-256 | `569b1175f32e0b06892b54bc5d4decf25bdf67c854b15b2068847c4d409706de` |
| Frozen archive SHA-256 | `59a2497bd73fda1c1a0691707b6d593589dcbacbbf178adc28b4f18bd148f333` |
| Image | `rokkad:khata-local-20261002-569b1175f32e` |
| Local image ID | `sha256:46c5fdb4030c4583f7c569efecb6376e19ec30c456ffdee6c5d9c8390847cea5` |
| Private evidence | `.tmp/khata-collateral-candidate-20261002-v2/` |
| Web container at that checkpoint | `khata-img-20261002-web` |
| Static volume at that checkpoint | `khata-ui-20261002-static` |
| Persistent database/media | Existing `khata-img-20261002-db-data` / `khata-img-20261002-media` |
| Local review URL | `http://127.0.0.1:8077/w/khata-73081a4c/loans/khata/` |

Original monthly KH00001 and annual KH00002 demos are unchanged. Separate fictional
KH00003/KH00004 retain browser evidence; KH00004 has a completed grouped exchange
and two pending outgoing items. No physical handover or real cash is implied by
synthetic acceptance data. Logins remain in `.tmp/khata-image-20261002/pilot-login.txt`.

Before each localhost switch, the prior owned image is checked, a full fictional
database dump/private-media ZIP are saved with separate SHA-256 checksums, and the
old web is retained stopped. Original/intermediate containers are
`khata-img-20261002-web-pre-collateral` and
`khata-img-20261002-web-pre-final-collateral`. The new web remains non-root,
read-only, restricted-role and internal-network-only behind the localhost relay.
Local HTTP uses `container_dev`; production-profile checks are separate. Later
documentation updates do not alter the frozen application archive/image.

Production JCL/JSK/Lakshmi data/deployments are unchanged. Remote CI, hosted
TLS/operator acceptance, off-device recovery and physical printer/QR checks remain
open. No Git commit/push, registry publication or external message occurs.
