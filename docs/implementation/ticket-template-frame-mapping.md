---
status: design-ready
owner: loans
updated: 2026-09-22
tags: [loans, documents, templates, mapping, experiment]
related:
  - ../plans/ticket-template-designer.md
  - ../adr/2026-09-22-ticket-template-authoring-experiment.md
---

# JCL/JSK frame mapping and implementation contract

This is the implementation target for the isolated feature experiment, not a
claim that these capabilities exist or that production printing has been accepted.
It settles the engineering choices from the initial plan. No runtime code or
database was changed to produce this document.

## Evidence and inventory

Source: commit `4312573fa2dca9f8bea3abd1ab84aadb5bd1e1cd`, specifically
`apps/tenant_apps/girvi/models/template.py`, `girvi/views/prints.py` and
`apps/tenant_apps/utils/loan_pdf.py`, plus the September 21 production archive.
Only the `girvi_loantemplate` and `girvi_templateframe` tables in schemas JCL/JSK
were extracted, using `pg_restore --file=-` without connecting to a database.

The [machine-readable design inventory](fixtures/ticket-template-frame-inventory-20260922.json)
records the archive digest, original settings/coordinates and candidate converted
rectangles. It contains no customer records, photos, credentials or PDF bytes.
It is not an importable layout definition and cannot activate a template.

| Workspace | Default template | Frames | Copies and stock |
| --- | --- | --- | --- |
| JCL | ID 2, `jcl_loan` | 12, all shared by both fronts | `BA`: A4 landscape, Original left, Duplicate right, full backgrounds |
| JSK | ID 1, `jsk_loan` | 11 Original + 12 Duplicate | `BS`: A5 Original then A5 Duplicate, data only |

JCL's nondefault template ID 1 is excluded from the acceptance mapping. Its
default uses `pdf_templates/org.pdf` and `pdf_templates/dup.pdf`; saved
`Condition1.pdf` and `D31.pdf` are not selected by `BA`. Asset names are source
references, not proof of retrieved bytes, ownership or page dimensions. Inventory
all asset bytes/checksums and inspect artwork before asserting visual parity.

All selected frames use Helvetica 12 pt and no visible frame boundary. JSK has
no PDF backgrounds. Its stationery guide can be attached later for preview but
is not required to produce data-only output.

## Every used frame, mapped

The target bindings below are proposed v2 ticket-payload additions where absent;
they must not be mistaken for fields already available in the current registry.
The editor shows human-readable names, never these identifiers.

| Legacy frame | Usage | Target | Implementation requirement |
| --- | --- | --- | --- |
| `loan_id` | JCL Both; JSK O/D | `loan.number` | Existing value; add value-only display |
| `loan_date` | JCL Both; JSK O/D | `loan.date` | Existing value; retain day-month-year formatting |
| `license_no` | JCL Both | `license.number` | New separate value. Legacy code actually prints license **name**, so do not assume semantic identity |
| `customer_info` | JCL Both; JSK O/D | `borrower.contact_block` | Name, relationship, selected address and primary phone, with real line breaks; omit missing components |
| `customer_pic` | JCL Both; JSK O/D | `borrower.photo` | Authorized Party profile photo captured at first issue |
| `loan_desc` | JCL Both; JSK O/D | `collateral.description_lines` | All approved items in stable order; numbered descriptions, no forced grid/header |
| `loanitem_pic` | JCL Both; JSK O/D | `collateral.first_approved_photo` | First approved item, then its first eligible approval-linked photo; never a later unrelated photo |
| `weight` | JCL Both; JSK O/D | `collateral.net_weight_by_metal` | Display-only totals of approved net weights by metal, with units |
| `value` | JCL Both; JSK O/D | `collateral.approved_appraisal_total` | Sum approved appraisal evidence only; unknown if any component is missing |
| `amount` | JCL Both; JSK O/D | `loan.principal` | Existing approved principal, optional currency label and consistent decimal formatting |
| `amount_words` | JCL Both; JSK O/D | `loan.principal_words` | Indian English words for the same approved principal, including paise when nonzero |
| `loan_qr` | JCL Both; JSK O/D | QR bound to `loan.number` | Existing supported binding; preserve raw loan-number content, separate from verification QR |
| `label` | JSK Duplicate only | `loan.summary_label` | Fixed app-owned preset: number/date, principal/weight, borrower/descriptions; no executable expressions |

Also expose individual `borrower.name`, `borrower.relationship`,
`borrower.address`, `borrower.phone` and `license.number` fields so clients need
not use the combined contact block. Keep approved rate/tenure and the existing
collateral table available. Literal text, signature space and uploaded logos are
ordinary existing block concepts. Do not implement every unused legacy dropdown
choice merely because it existed in the model.

### Semantic differences that must be visible in acceptance

- Legacy `value` calls `get_current_value()`, whereas a contract ticket needs
  approval-time evidence. The target uses approved appraisal, with an explicit
  preview label/explanation. This is intentional, not a claim of numeric parity
  with today's legacy market value; no loan valuation rule changes.
- Legacy descriptions append a separate quantity. Native `PawnCollateralItem`
  and its approval payload have no dedicated quantity field. Preserve approved
  descriptions (including quantity already written there); never invent `Qty: 1`
  or confuse collateral-row count with physical article quantity. A separate
  quantity domain enhancement is outside this slice. If the owner requires it
  for acceptance, record that as a blocker rather than altering loan facts here.
- `license_no` must use the actual license number, not blindly copy the old
  misleading binding name. Compare the applicable license evidence and artwork
  before activating the converted JCL design.
- The old template's `page_width/page_height` are not authoritative: the renderer
  chooses A5 or half landscape-A4 from `print_option`.

## Geometry and appearance

Preserve original outer rectangles in the inventory. For source page height
`H=210 mm`, candidate new coordinates are:

```
x_mm = 10 * x_cm
y_mm = H - 10 * (y_cm + height_cm)
width_mm = 10 * width_cm
height_mm = 10 * height_cm
```

JSK source pages are 148 x 210 mm. JCL's pre-merge drawing canvas is 148.5 x
210 mm (half of A4 landscape). Background merging can scale to the PDF media box,
so inspecting the actual background dimensions is required before a final JCL
transform. The current A5-to-half-A4 compositor also changes width by 0.5 mm;
do not assume `ACTUAL_SIZE` means identical coordinates through that composition.
Use existing standard A5/A4 profiles initially and explicitly test/calibrate this
transformation. Add a page-size extension only if measured parity requires it.

Example: JCL frame 15 (`customer_info`) maps to outer `(40, 50, 60, 30)` mm.
JSK frame 1 (`loan_id`, Original) maps to `(109, 20, 30, 10)` mm.
Text needs the old ReportLab Frame's 6-point padding and Normal-style 12-point
leading; the v3 renderer lacks those controls. The feature's v4 text frames now
provide both explicitly, with bounds and overflow validation.
Photos were centered with aspect ratio preserved; QR occupied 90% of its frame.

Implement v4 decimal geometry at 0.1 mm precision, separate padding/leading in
points, aspect-preserving image fit and a QR inset setting. Imported drafts use
the observed legacy style settings; new designs use simple readable defaults.
Text is escaped structured content with explicit line breaks, never arbitrary
HTML. Offer wrap, bounded shrink (minimum 6 pt) or error; preview warns when
shrinking occurs. Do not silently truncate required values or omitted item rows.

**Concrete bounds finding:** JSK Duplicate amount frame 19 starts at x=40 mm and
is 120 mm wide, extending to 160 mm on a 148 mm page. Preserve that source fact.
Offer a reviewed draft width of 108 mm with x/y unchanged; never silently repair
or accept the original rectangle. Verify the visible amount against stationery
before using this adjusted draft. All other selected outer rectangles fit their
source canvas. This does not prove their text fits or a printer can reach them.

## Selected contract extensions

### One engine, additive versions

- Extend the existing layout validator/renderer with **layout schema v4** for
  the bounded ticket editor capabilities: optional backgrounds, value-only and
  custom-label display, structured multiline values, decimal geometry, padding,
  leading, bound photos and explicit image/QR fit. Keep v1/v2/v3 interpretation
  unchanged. Clone to v4 explicitly; do not rewrite published definitions.
- Use **ticket payload v2** for richer allow-listed facts/media references;
  existing document kinds/payload v1 remain supported. Projection/asset services
  resolve data; the renderer receives values and validated bytes, not models,
  ORM paths, remote URLs or storage credentials.
- Extend print profiles with **schema v2** `stock_mode`: `PLAIN` or `PREPRINTED`.
  V1 retains existing background behavior. In preprinted mode, backgrounds are
  guides only and omitted from print output; foreground frames still print.
  Existing page/copy compositions remain. Compatibility validation accounts for
  per-copy required information and any declared stationery content.
- Original/Duplicate can use separate blocks at separate positions. Keep one
  canonical block definition format; no new template/frame tables or parallel
  renderer. Preserve fixed and Flow rendering paths.

The editor offers **Design preview** (may show a guide) and **Print preview**
(actual background policy). Both are explicitly watermarked and unofficial.
Only the actual print PDF is the official stored artifact. A second full-form
official artifact is deferred; never let a guide PDF masquerade as the print file.

### Sources and first-issue evidence

Approved loan/financial/collateral facts continue to come from the existing
approval snapshot. It already contains per-item photo IDs and hashes; use them
instead of introducing a second approval photo snapshot. Missing approved media
must not be replaced by post-approval evidence. Preview shows a missing-photo
marker/warning; issuance blocks unreadable selected media. Explicitly optional
absent photos may leave space blank, with absence recorded; transport failure is
not absence.

Customer name/relationship/contact/profile photo are resolved by a Party-owned
document selector at first issue, not claimed as approval-time facts. Use Party's
primary phone. For address, prefer its default HOME address, otherwise its sole
address; ambiguous alternatives require an authorized selection before issue,
without changing Party defaults. Record the selected address/photo identity and
actual rendered values. Missing contact data renders blank, never Python `None`.

Add one nullable, immutable `source_snapshot` JSON field to the existing issue
record for payload-v2 facts, capture time, selected media identities/hashes and
absence/selection evidence. Preserve old rows with null evidence rather than
backfilling from mutable current records. The exact PDF remains the reprint
authority. Snapshot data is private, subject to the same Workspace authorization;
it must not enter layout exports. No new document-history model is needed.

Resolve existing official issues before fetching mutable Party data or photo
bytes. A Party edit or storage failure must not stop a valid stored reprint, and
must not produce another official issue by changing its identity. Retain the
source approval fingerprint/idempotency key; extra display evidence is captured
at issuance, not folded into a new business approval. Explicit regeneration stays
a linked new issue. Concurrent first requests must produce one consistent issue.
Keep media validation, checksums and storage-failure cleanup in services.

### Visible information versus internal evidence

Internal Workspace/Party/loan/approval IDs, fingerprints and full verification
strings stay mandatory in issue evidence, but v4 need not print them. A loan-number
QR does not imply a public verification service. Visible requirements still cover
business/license identity, loan number/date/principal, borrower, approved terms
and all collateral descriptions/weights. Compact description/weight blocks can
satisfy collateral coverage without a forced table.

For genuinely static identity/terms in artwork or preprinted stock, use a small
allow-listed declaration of fixed binding/value plus reviewed asset or stationery
reference per copy. At issue time, compare declared values to authoritative loan
facts; a mismatching license/rate/tenure blocks printing. Approval of the artwork
is an owner review, not OCR verification or legal certification. Dynamic customer,
loan number/date/principal and collateral evidence cannot be waived this way.
Until artwork/stock is reviewed, converted templates remain drafts. This does not
weaken the existing v1/v2/v3 rules or claim legal sufficiency for every lender.

### Activation and export

The first unified editor targets Workspace or Series. Existing advanced
license-level layout assignments remain supported, but a print profile has no
license scope: do not manufacture one, silently change all series or override
other assignments. Show inherited overrides and the exact target at activation.

A bounded application command validates the intended layout/profile pair, then
publishes/assigns both atomically using existing domain checks, permissions, locks
and audit. Validate intended state rather than incompatible intermediate pairs.
Failure leaves the previously active pair unchanged. Editing creates an editable
draft; activation must detect concurrent draft edits. No new approval hierarchy.

Pack export includes only reviewed layout definitions and static assets. Exclude
sample-loan values, source snapshots, customer/collateral images and issue PDFs.
Cloning static assets preserves isolation and hash checks; dynamic bindings stay
binding names, never copied customer data.

## Foundation implementation status (2026-09-22)

The feature implements v4 optional backgrounds, value-only/custom-label scalar
fields, 0.1 mm geometry, escaped line breaks and text padding/leading in points.
Profile v2 paper stock determines whether backgrounds print or act as design-only
guides. Both preview modes are marked unofficial; official output never receives
the design-preview flag. Existing profile v1 definitions stay unchanged. A dedicated
test launcher pins the local test database and filesystem media. Synthetic PDF
tests cover actual-size A5 copy positioning and background isolation; UI tests
cover first issue and unchanged reprints after replacing the template.

Payload-v2 contact/scalar/photo bindings and nullable immutable source snapshots
are implemented. First-issue media is read through Party's authorized selector and
approved collateral photo IDs/checksums; no live market valuation, fabricated
quantity or fallback to later photographs is introduced. The existing aspect-fit
image behavior is retained. Photos are required unless the frame explicitly
allows genuine absence; missing approved evidence or broken media remains an
error, with labelled placeholders available only in unofficial previews.

`scripts/review_ticket_frame_mapping.py` converts the inventory into candidate
v4 blocks/profile v2 definitions and a synthetic HTML positioning aid under
`outputs/ticket-template-tests/frame-review/`. All 35 frames have registered
bindings. The bundle is deliberately not importable yet: it records the current
validator failures and source semantic flags. The proposed JSK duplicate amount
width is 108 mm instead of the out-of-page 120 mm; this is a review candidate,
not an accepted correction. Browser text wrapping is not ReportLab calibration.

Owner review subsequently requested a common top edge for JCL's borrower photo,
contact block and loan number. Candidate photo frame 14 moves from y=75 to y=50 mm,
matching the other two frames, while retaining its 25 x 25 mm size. It now ends
15 mm above the collateral description frame at y=90 mm. Apply this to both copies;
preserve the extracted source coordinates and record this as an explicit design
correction rather than a coordinate-conversion fix.

The owner also requested a paper timestamp. `document.generated_at` is a registered
v4 scalar, captured once with first-issue evidence and displayed with seconds,
timezone and UTC offset. A Generated footer is added to both candidates: JCL Both
and JSK Original `(10, 195, 128, 8)` mm; JSK Duplicate `(92, 185, 46, 18)` mm to
clear its summary label. These are added frames, not part of the 35 extracted
source frames. Actual background/printer calibration remains pending. Exact PDF
reprints preserve this generation timestamp rather than showing the reprint time.

Image/QR fit refinements, static-stock declarations and paired activation remain
pending. V4 visible business coverage is now implemented: internal identifiers and
verification text are optional on paper; compact description/weight bindings can
replace the table. Complete internal payload evidence is still validated. Every
front must retain business/license/customer identity, number/date/principal, rate,
tenure and signature space. Candidate reports therefore flag only missing business
identity/terms and signature areas, which must be covered by visible frames or
reviewed stationery. Do not treat candidates as accepted JCL/JSK templates. See the
plan for isolated test commands and manual-runtime limits.

## Minimal editor and implementation order

One page: template name; paper/stock/copies; Original/Duplicate/back tabs; canvas;
frame list; selected-frame properties; sample selection; Save draft, Preview and
Use this template. Existing English/Hindi Django/HTMX/Bootstrap conventions apply.
Keyboard/touch numeric controls are required alongside drag/resize. JSON is not
required for any mapped frame, duplication, paper choice or activation.

1. Provision isolated feature database/media/port; establish legacy schema and
   historical reprint regression fixtures using synthetic records.
2. Add v4 value-only/optional-background/geometry behavior and v2 stock profiles.
3. Add the narrow payload/media/evidence extension and source snapshot migration.
4. Add copy-aware editor, paired activation, and draft-only mapping import.
5. Compare PDF and paper output; accept semantic differences explicitly, confirm
   owner self-service customization, then propose merge.

Synthetic examples must cover: short and long customer text; multiple addresses;
multiple gold/silver items; absent versus unreadable media; approved versus later
photos; amount words with paise; out-of-bounds/overflow; different license/rate;
foreign-Workspace objects; concurrent first print; changed Party/assignment after
issuance; old layout/profile versions; and no customer data in exported packs.
Mock backgrounds alone cannot establish Tamil artwork or real-printer parity.

This design completes the mapping/engineering-decision slice. Asset retrieval,
owner review of actual stationery/semantic differences and physical calibration
remain acceptance work. Do not call the experiment production-ready from this
document or from passing unit tests.
