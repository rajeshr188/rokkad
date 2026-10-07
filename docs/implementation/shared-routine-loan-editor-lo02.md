---
status: implemented
owner: project
updated: 2026-10-07
tags: [loans, origination, editor, verification]
related: [../plans/loan-origination-completion.md]
---

# LO-02: shared routine New loan editor

## Result and boundaries

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
editable for actual paper exceptions. The standing agreement remains a summary
with additional details collapsed, rather than routine repeated terms questions.

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
