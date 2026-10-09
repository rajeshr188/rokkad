---
status: implemented
owner: project
updated: 2026-10-09
tags: [loans, origination, editor, verification]
related: [../plans/loan-origination-completion.md]
---

# LO-02: shared routine New loan editor

## Result and boundaries

On 9 October routine paper entry removes the repeated Standing agreement section.
The main fields remain customer, series/product/date/tenure, original number/source
and collateral allocations. One collapsed Additional details control contains
actual terms exceptions, optional payout facts and licence evidence. Complete
agreement and deductions stay in focused review. Missing setup is actionable;
current monitoring and rounding retain their supported fallback controls. A missing
rate on another item also prompts setup; percentage fees await the entered principal.

`paper_source_license_revision` resolves only one dated retained revision in the
selected Workspace/series/licence. Ambiguity and unknown legacy validity remain
blank. Routine forms opt in to this read-only convenience through a presentation
field stripped before canonical normalization; old POSTs without it keep their
fingerprints. A signed review retains its posted mapping, including blank, rather
than remapping after later setup changes. Explicit manual choice remains scoped and
dated by admission validation. Saved drafts and archive entry do not auto-map.
The existing financial services freeze all reviewed facts as before. No model,
migration, calculation profile, approval requirement or posting service is changed.

Terms refresh now also updates licence evidence while actual agreement exceptions
remain intact. Open optional sections survive refresh. Native Apply controls work
without JavaScript. Both direct-entry and paper-entry regression checks, including
financial reconciliation, frozen agreement and exact retry, pass; see Status.

The 8 October tenure refinement explains the dated standing source beside tenure.
When no tenure is configured, agreement details open with a targeted warning;
Enter actual agreed terms explicitly enables the existing exception and actual
tenure/item rates, retaining the source-reason requirement. The missing-tenure
error explains both setup and supported actual-entry recovery. Asynchronous terms
refresh updates the tenure value, read-only state and help text together. Routine
paper entry/review now uses distinct visible steps; see the
[review implementation](shared-origination-review-lo03.md).


Routine direct and paper entry now render `loans/pawn/routine_entry.html` at the
same New loan route. Both have the same customer search, series/product/date/tenure
layout, borrower balances, collateral rows, add/remove controls, camera/upload and
entered-facts summary. Existing scoped defaults and the compact purpose override
remain. Total principal comes from actual item allocations.

Direct entry retains automatic numbering, valuation/price guidance and its existing
draft submission/economic preview commands. Paper entry asks for the original
number/source, supplies dated standing terms, permits explained actual exceptions
and optionally records known payments or closure. It does not reapprove the original
advance using current prices. The shared tenure field is supplied from setup and
editable for actual paper exceptions. Agreement details are shown in review,
with exceptional entry controls collapsed under Additional details.

On 8 October the paper original-number field gained selected-series guidance:
configured prefix/digit width and next automatic number, refreshed through the
existing series-change presentation. The original remains editable and is never
prefilled or rewritten as the next automatic number. The read-only hint explains
high-water advancement on successful recording, preservation for older/unmatched
originals, and no reservation during review. Automatic-preview unavailability is
displayed without changing admission rules. Direct numbering presentation and both
financial writers are unchanged.

The same day's agreement cleanup separates actual terms, optional payout details
and optional source-licence mapping. Ordinary monitoring/rounding controls are
hidden standing fields, with missing monitoring and unavailable/different rounding
prompts. Itemized actual agreement exceptions use available current monitoring;
legacy explicit non-itemized contexts keep their shape. Standard-term explicit
proceeds are retained instead of cleared, and existing exact reconciliation rejects
inconsistent amounts. No arbitrary customer net-cash override was added. Terms
refresh retains open optional sections; no-JavaScript exception selection uses the
existing nonfinancial terms action. Verification counts and local overlay state are
recorded in [Status](../STATUS.md).

An owner-requested reversible presentation trial on 8 October moves the optional
per-loan purpose override from the page heading to the series field. Ordinary entry
retains a read-only current-purpose label and automatically follows configured
defaults. Explicit override state is disclosed; Use series setup resets it. No
dispatch/default/financial behavior changes. The fictional 8083 demo includes
DEMO-D-/DEMO-P- series; existing series and loan records are untouched. Previous
templates and a local-only restore/reapply helper are retained in
`.tmp/entry-purpose-preview-20261008/`. On 8 October the owner accepted the entry
presentation as satisfactory for now. This does not complete the outstanding
corrected-paper, document and monitoring acceptance or production release gates.
Seven focused Django checks and actual desktop/mobile/no-JavaScript browser checks
pass. The saved previous layout was restored and checked for both demo defaults;
the trial was then reapplied. Rollback changes templates only, not database records.

This slice does not combine final confirmation. Direct still saves a draft and
uses existing approval/payout actions; paper still uses its signed history review.
LO-03 shares that review/confirmation presentation. Saved-draft payout/correction,
archive admission, imports/openings and legacy non-itemized POST retries retain
their specialized interfaces. No schema, interest contract, posting engine,
permission or production financial record is changed.

## Small implementation

`routine_entry_context` exposes the five existing bound fields under their current
form names. Ordinary Django forms and existing commands keep their validations.
Customer/series widgets are reused from the direct form, with Workspace-scoped
choices and the Workspace-bound customer search URL. The shared collateral
controller owns add/remove for both purposes; the paper controller reacts to its
change event to recompute the displayed total, refresh standing terms and invalidate
a prior review. Terms refresh updates the shared tenure and summary without uploading
selected files. Direct preflight remains exclusive to current lending.

Purpose switching keeps physical item facts/deletions and purpose-specific details
in the existing presentation state. JavaScript retains the actual File input across
replacement. Without JavaScript, switching explicitly asks staff to select photos
again. A normal page reload after an upload also requires file reselection; browser
file selections are not silently represented as persisted attachments.

## Current photographs on recorded entry

Paper entry now supports optional current photographs through the existing
immutable collateral-media model/service. The selected surviving item positions,
names, digests, sizes and MIME types are bound to the signed financial review and
retained in recording evidence. A missing, changed or reassigned file requires a
fresh review. Removed row indices remain stable; attachment positions refer to
the surviving items, not raw form indices or foreign database IDs.

Preview writes neither finance nor stored photos. Confirmation wraps the existing
history writer and current photo attachment in one database transaction. Failed
attachment rolls back origin/number/media rows; already stored files are compensated
using the existing draft-upload pattern. Cleanup failure is logged for operator
reconciliation. Exact successful retries append no duplicate loan or photographs.

Photos use the existing post-origin `POST_APPROVAL` storage category, with today's
capture timestamp/actor; presentation calls these **Current collateral evidence**.
Neither the interface nor review claims an original-day photograph or approval.
Existing source/renewal/draft photo labels retain their meanings. Exact Workspace
recovery preserves the photograph bytes and reviewed metadata.

## Verification

Verification uses the isolated PostgreSQL Django test database, test settings and
fictional records. The targeted suite covers shared layout/defaults/exceptions,
scoped search, switching/deleted rows, numbering and invalid retries, direct draft
economics/uploads, paper receipts/closures, signed photo changes/retries, rollback
and exact recovery. Final counts are recorded in [Status](../STATUS.md).

Chromium desktop (1440 px) and mobile (390 px) checks use actual Django-rendered
fictional pages and local static assets, with captured HTTP responses. They verify
both layouts, one added row per click, stable removal, no horizontal overflow,
editor reinitialization and direct/paper/direct File-input/summary preservation.
Financial HTTP POSTs are tested separately against Django, not inferred from those
captured browser responses. No JavaScript page errors occur.

Persistent JavaScript tests exercise both item controllers together, add/remove
limits and total updates, both borrower-field aliases, overlapping balance
responses, price preflight and draft submission. CI includes the new shared-editor
test. Actual source/staff acceptance, clean release artifact, production media
recovery/capacity and deployment remain later plan gates.
