---
status: implemented-local
owner: loans
updated: 2026-10-03
tags: [khata, collections, source-events, verification]
related: [khata-read-performance.md, ../flows/khata-account-workflow.md]
---


The later [document-navigation checkpoint](khata-document-navigation.md) records the current
local runtime; earlier checkpoint identities/counts below remain dated evidence.
# Khata collection worklist and readable events

The later [action-guidance checkpoint](khata-action-guidance.md) records
the local guidance runtime. This collection checkpoint retains its dated evidence.

The owner authorized phase four: collection worklists and clearer event details.
The read-only UI uses existing canonical interest and immutable source evidence.
No migration, charge, penalty, persistent projection or ordinary-loan change.
Final frozen-image and browser verification is complete in the fictional localhost
pilot; production is unchanged. Existing fictional records/media are preserved.

## Collection definitions

The register links to a separate **Collection worklist**. Only ACTIVE Khata
accounts qualify. Number/borrower, series, licence association and borrower scope
are applied before canonical replay. The default shows overdue, due today and
upcoming accounts, with a seven-day window; 30/90-day windows and all active
accounts are available. Upcoming excludes arrears. Due today excludes older
arrears. Overdue starts the day after the oldest unpaid anniversary due date.
Accounts needing evidence review stay visible in every status filter and sort
first; unavailable evidence makes complete money totals unavailable, never zero.

The oldest unpaid instalment amount is grouped by its due date. It is distinct
from total interest due now, which includes all older arrears. Days overdue use
that oldest unpaid date. Due and overdue totals cover all matching accounts before
25-account pagination. Principal/limits do not become extra interest debt.

Without unpaid dues, the next monthly/annual anniversary is restored from the
original first-withdrawal date (including short-month/leap clamps). The existing
interest schedule calculates the amount at that future anniversary using only
financially activated revisions, frozen past periods and effective allocations.
An annual instalment groups all monthly charges with that due date. Proposed or
approved-but-unactivated changes do not affect it. Forecasts are explicitly
**estimates assuming current activated terms continue**, not current balances,
posted charges or permission to receive advance interest. Zero projected charges
show no charge scheduled. Receipts remain actual staff-entered cash through the
existing signed review and command; no amount or payment reference is invented.

Current LTV cover is calculated only for the visible page, from eligible held
items and same-day approved prices, using unchanged rounding. It excludes reserved
outgoing items. Missing prices leave cover unavailable while known dues remain
visible. The latest recorded warned exchange is selected in SQL per visible
account, including an explicitly labelled subsequently corrected source. Historical
warnings do not prove current undercoverage or become additional cash debt.

## Event evidence

History offers **View event details** and marks recorded warnings. A scoped GET
resolves the account and exact operation under existing data.view access and
private/no-store headers. It does not calculate today's balances or consult
current Rates/policy. Saved business/recorded dates, actor, sequence, typed amounts,
source terms, policy, reasons and actual cash/consent/handover/correction references
are labelled by meaning. Related approval, reservation and correction links stay
within the account. Corrected originals remain readable and disclose compensation.

Exact IN/OUT groups come from immutable selection rows. Their identity, metal,
net weight and saved values use immutable received-item and valuation rows. All
reviewed valuation rows can be expanded with original price identity/effective /
recorded timestamps; this includes eligible collateral beyond selected groups.
The saved per-metal replacement shortfall is separate from retained account LTV
backing and overdue interest. Typed receipt allocations and frozen charge/term
segments explain interest events. Native links work without JavaScript.

[Collection selector](../../apps/tenant_apps/loans/selectors/khata_collections.py),
[event selector](../../apps/tenant_apps/loans/selectors/khata_events.py) and
[scoped views](../../apps/tenant_apps/loans/web/khata_views.py) keep calculations out
of templates and posting out of views. No source facts are rewritten.

## Verification and remaining scope

Twelve new checks pass in 11.001 seconds: monthly due/overdue boundaries, oldest
unpaid versus total arrears, partial payment/compensation, annual forecast/rate unit,
short-month/leap restoration, upcoming windows, activation-only forecasts, zero
rates, filters/totals before paging, evidence review, stopped servicing, historical
warnings versus current cover, frozen event groups/quotes/policies/references,
receipt/charge/revision/handover details and account/Workspace/viewer/GET boundaries.
The initial 424-case frozen run caught a redundant non-JSON date in the shared
cover result, which broke statement snapshot validation. It is removed; statements
already carry their own as-of date. The failed candidate was never switched into
the pilot. The corrected source passes 38 document/layout/collection checks in
26.649 seconds. The final frozen image passes **424 Linux regressions in 217.369
seconds**. All 1,410 application/settings files match the archive and actual image;
schema/no-drift/dependency/restricted-runtime/static/owner-startup-refusal checks pass.

Actual Chromium verifies worklist filters and totals placement, saved event groups /
values/policy, exact source/item links, private headers, wrong-account refusal,
viewer access, mobile layout and no-JavaScript use. Prior register/tab/servicing,
bounded custody/QR/legacy-link and exception-guidance/blocked-preview checks pass.
Desktop/mobile screenshots are inspected; no page JavaScript errors occur. Tables
scroll within their own responsive wrappers. QA serves the exact configured
Bootstrap 5.3.8 CSS/JS bytes with matching SRI because the sandbox blocks the CDN;
application asset configuration is unchanged.

Candidate at this checkpoint: `khata-local-20261002-53cb3807081f`, image
`sha256:ff9b400b815abc4a9be261f24ed9ab3597794cae1dd4940ea84f4d0579e4343b`.
Source digest: `53cb3807081f305409d5ad69c37a719ee4ad0d35f4e9ae94b068281d2fc71a6a`;
archive: `370994261da46bfa3c0c508973c2d9322a958e2557081e6caf077ba5b00f575c`.
This is an uncommitted local snapshot, not a remote-CI/release identity. Pre-update
fictional database/media backups/checksums are retained, along with stopped prior
web `khata-img-20261002-web-pre-collections`. Private verification/browser evidence
is under `.tmp/khata-collections-candidate-20261002-v2/`. Later changes are docs only.

Optional automated/manual reminder dispatch remains queued. It needs a separately
reviewed Loans-owned notice-intent, audience/consent, channel/provider eligibility,
idempotency and delivery evidence contract through Notify v2. This phase creates
no notice or outgoing message. It does not add penalties, top-up debt, settlement
rules or unsupported corrections. Cash/custody operational reports were the next
ordered phase and are now delivered in the linked later checkpoint. Single large event groups/valuation details are complete rather
than silently truncated; further document/event navigation can be measured later.
Hosted/operator/physical and remote-CI release acceptance remain separate.
