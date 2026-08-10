---
status: active
owner: loans
updated: 2026-08-09
tags: [loans, documents, printing, operator-guide]
related:
  - ../plans/loans-configurable-documents-plan.md
  - ../implementation/loans-configurable-document-operations.md
  - ../adr/2026-08-06-loans-versioned-configurable-documents.md
  - ../adr/2026-08-09-loans-logical-layout-and-print-profile-separation.md
---

# Loan Document Layouts: Starter Guide

This guide is for Workspace Owners and Admins who configure printable PawnLoan
documents. Normal loan staff do not need this setup area; their existing Print
buttons automatically use the assigned published layout.

## Before You Start

Open **Loans > Setup > Document layouts**, or visit:

```text
/loans/setup/documents/
```

You need:

- Owner or Admin access;
- at least one approved loan for ticket preview;
- the corresponding completed event for receipt, release, auction recovery, or
  renewal preview;
- PNG/JPEG logos or backgrounds, or a small valid PDF letterhead background;
- access to the physical printer used by the business before production
  assignment.

## The Safe Mental Model

```text
Layout -> Draft revision -> Preview/test print -> Publish -> Assign -> Print
```

- A **layout** is the named document design.
- A **draft revision** is editable.
- A **published revision** is frozen and cannot be edited.
- An **assignment** decides which published revision is used.
- An **official issue** stores the exact PDF that was first printed.
- A later reprint returns that original issued PDF, even if the default layout
  has changed.

Never try to repair a published revision. Clone it, correct the new draft, test
it, publish it, and change the assignment.

## Layout Versus Print Profile

The approved target architecture separates two operator concerns:

- **Document layout:** regulated content, wording, fields, tables, signatures,
  geometry, logical Original/Duplicate identity, Terms/D3 back content, and
  logical-surface backgrounds.
- **Print profile:** which logical copies are printed, A5 sequence or A4
  landscape side-by-side packaging, simplex/duplex order, orientation, scaling,
  and printer guidance.

The intended workflow is:

```text
Create and publish logical layout
-> create and publish workspace print profile
-> assign layout and print profile
-> preview/test-print resolved combination
-> use normal loan Print action
```

Print profiles are versioned and auditable. They are not ordinary mutable
preferences. An official issue records the resolved layout and profile and
stores the exact PDF bytes, so later assignment changes affect only future
issues.

**Current implementation note:** resolved print profiles now package new
configurable loan-ticket issues. Manage them under **Loans setup > Print
profiles**. Existing published layouts retain embedded `copy_mode` and
sheet-composition settings only for explicit audited legacy recovery; do not
manually remove those settings from existing definitions.

Create and preview a draft profile first. Publish it only after the PDF looks
correct, then assign it to the entire workspace or one Series. A Series
assignment wins over the workspace assignment. The assignment screen refuses
an incompatible effective layout/profile pair. To change a published profile,
clone it and publish the clone; never edit historical evidence.

Use **Loans setup > Issued documents** to inspect which layout and profile
produced an official document. Downloading the exact artifact from that page
returns the immutable stored PDF even after assignments change.

Before the parity pilot, open **Integrity diagnostics**. An active ticket
assignment that prints only Original or only Duplicate is a blocking finding.
Choose one of the `BOTH`/side-by-side sheet presets or Original/Duplicate copy
mode. If there is no configured assignment, the fixed fallback already emits
both required copies.

## First Setup: Create A Loan Ticket

1. Select **Create starter layout**.
2. Enter a clear name, such as `Main Counter Loan Ticket`.
3. Select **Loan ticket** as the document type.
4. Select **Create draft**.
5. Review the generated structured layout definition.
6. Select **Preview** to render it using an approved sample loan.
7. Select **Test print** and print it on the actual paper and printer.
8. When satisfied, select **Publish and freeze**.
9. In **Assign default scope**, choose the required scope and select
   **Assign layout**.

Do not publish merely to see what a layout looks like. Preview and test print
work while it is still a draft.

## Use The Visual Flow Editor

Open a schema-v2 draft and select **Visual Flow editor**. The editor changes
the same validated JSON used by Advanced JSON; it is not a second template
format.

The first editor surface supports:

- A4, A5, or Letter page size and bounded margins;
- primary/border colors, approved font, and type sizes;
- top-level block movement and removal;
- adding a registered field, field grid, outlined section, field-plus-QR
  columns, spacer, page break, or signature row;
- direct Preview PDF and Test print actions when an approved sample loan is
  available.

Removing or moving a block cannot bypass schema rules. If an edit would remove
mandatory evidence, create an invalid structure, or use an unknown binding,
the draft is not saved. Use **Advanced JSON and publishing** for headers,
footers, table-column details, conditions, overflow, or deeper nested edits
until those property panels are added to the visual surface.

## Choose The Correct Assignment Scope

Resolution uses the most specific applicable assignment:

```text
Series -> License -> Workspace -> Built-in fixed PDF
```

Use:

- **Workspace default** when every license and series should use the same
  design. Leave both License and Series blank.
- **License default** when one regulatory license needs different wording or
  letterhead. Select License and leave Series blank.
- **Series default** when a counter, branch-like series, paper stock, or printer
  needs a distinct format. Select its Series; the matching License is enforced.

A series assignment overrides its license assignment. A license assignment
overrides the workspace assignment. If none exists, Loans uses the built-in
fixed PDF.

## Add A Logo Or Background

While the revision is a draft:

1. In **Assets**, enter a stable lowercase key, such as `business.logo` or
   `ticket.background`.
2. Choose **Image / logo** or **Page background**.
3. Upload the file.
4. Add the same asset key to the layout JSON:

Logo block:

```json
{
  "type": "image",
  "asset_key": "business.logo",
  "width_mm": 25
}
```

Page background property:

```json
"background_asset_key": "ticket.background"
```

Supported assets are PNG/JPEG images and bounded PDF backgrounds. Invalid,
oversized, corrupt, duplicate, or cross-workspace assets are rejected.

## Fill An Existing PDF Form With Absolute Overlay

When creating a layout, choose **Exact PDF overlay** instead of Flow document.
The starter draft expects a background asset with the key
`form.background`. Upload the business/regulatory PDF as a **Page background**
using that exact key.

Overlay coordinates use whole millimetres from the **top-left corner** of the
selected page:

```json
{
  "type": "field",
  "binding": "borrower.display",
  "x_mm": 28,
  "y_mm": 42,
  "width_mm": 100,
  "height_mm": 8,
  "font_size_pt": 10,
  "align": "LEFT",
  "overflow_policy": "SHRINK",
  "max_characters": 80
}
```

This places the top-left of the borrower rectangle 28 mm from the page's left
edge and 42 mm from its top edge. Width and height define the complete bounded
rectangle. Blocks extending beyond A4, A5, or Letter fail validation.

Absolute overlay currently supports:

- title and registered field rectangles;
- images and QR codes fitted inside rectangles;
- verification and signature rectangles;
- bounded tables with configured columns;
- conditional visibility and safe formatting;
- single, original/duplicate, and original/duplicate duplex output.

Flow containers, automatic page breaks, headers, and footers are deliberately
unavailable in overlay mode. An overlay table that cannot fit its rectangle
fails rendering instead of silently clipping or creating another page.

Open the draft and select **Visual overlay editor**. Its authenticated canvas
shows a raster preview of the first background page with scaled block
rectangles. Drag a rectangle to update X/Y, then select **Save block**. Use the
numeric fields for exact width, height, font size, alignment, binding, asset,
and text. The editor can also add or remove supported overlay blocks and change
page/background/copy settings. Every save revalidates the complete JSON draft.

Advanced JSON remains available for table-column configuration, conditions,
formatting, overflow, and duplex back-page blocks. PDF viewers may apply print
scaling, so production acceptance must use **Actual size / 100%** on the real
printer.

### Original, Duplicate, Terms, And D3 Logical Surfaces

Original, Duplicate, Terms, and D3 are logical loan-ticket surfaces. Keep their
content and background assets in the published layout:

- Original front
- Duplicate front
- Original back / Terms
- Duplicate back / Form D3

Each front block may apply to **Both copies**, **Original only**, or **Duplicate
only**. Every logical front must retain all mandatory fields, tables, and
verification; copy-specific decoration cannot remove legal evidence.

In the approved target architecture, a separate versioned print profile will
package these logical surfaces as A5 pages or A4 landscape sheets. Until that
runtime slice ships, choose the existing sheet-composition preset in **Page and
background**. It uses A5 as the logical page size:

The editor sets this logical A5 size automatically. An A4 landscape preset
still produces A4 landscape output by placing two logical A5 surfaces side by
side. When an existing A4 or Letter overlay first changes to a sheet preset,
the editor proportionally fits its existing block rectangles onto A5. Review
and fine-tune their positions against the uploaded A5 backgrounds afterward.
Sheet-mode text blocks use shrink-to-fit overflow so realistic values that wrap
on the narrower A5 surface reduce their font before preview is rejected.

| Preset | Output sequence |
| --- | --- |
| `A5_ORIGINAL` | Original front |
| `A5_ORIGINAL_TERMS_DUPLEX` | Original front, Terms |
| `A5_DUPLICATE` | Duplicate front |
| `A5_DUPLICATE_D3_DUPLEX` | Duplicate front, D3 |
| `A5_BOTH_SIMPLEX` | Original front, Duplicate front |
| `A5_BOTH_DUPLEX` | Original front, Terms, Duplicate front, D3 |
| `A4_SIDE_BY_SIDE` | One A4 landscape page: Original left, Duplicate right |
| `A4_SIDE_BY_SIDE_DUPLEX` | A4 front as above; A4 back: Terms left, D3 right |

For A4 landscape duplex, Rokkad preserves left/right positions but does not
control the printer driver's flip-edge behavior. Test both sides using the real
printer and select the driver option that keeps Terms behind Original and D3
behind Duplicate.

## Add A QR Code

For the official verification ID, add this block:

```json
{
  "type": "qr",
  "binding": "document.verification_id",
  "width_mm": 22
}
```

Test the printed QR with a real phone. Confirm it contains the exact Rokkad
verification ID shown on the document.

## Common Layout Blocks

Schema-v2 Flow layouts can group content into outlined or tinted sections,
proportional columns, and compact field grids. These containers remain in the
normal document flow and move together based on available page space.

```json
{
  "type": "section",
  "text": "Ticket summary",
  "style_variant": "OUTLINED",
  "blocks": [
    {
      "type": "field_grid",
      "grid_columns": 2,
      "bindings": ["loan.number", "loan.date", "loan.principal", "borrower.display"]
    }
  ]
}
```

```json
{
  "type": "columns",
  "columns": [
    {
      "width_percent": 70,
      "blocks": [{"type": "field", "binding": "license.display"}]
    },
    {
      "width_percent": 30,
      "blocks": [{"type": "qr", "binding": "document.verification_id", "width_mm": 20}]
    }
  ]
}
```

Column widths must total 100 percent. Containers may be nested only to the
validated depth limit, and page breaks cannot appear inside them.

For a configured table, select payload column indexes, labels, widths, and
alignment explicitly:

```json
{
  "type": "table",
  "binding": "collateral.items",
  "style_variant": "STRIPED",
  "repeat_header": true,
  "table_columns": [
    {"index": 0, "label": "Line", "width_percent": 25, "align": "CENTER"},
    {"index": 1, "label": "Pledged article", "width_percent": 75, "align": "LEFT"}
  ]
}
```

Table widths must total 100 percent. Invalid or missing payload indexes fail
the render instead of silently printing an incomplete table.

Use bounded page regions for compact information that must repeat on every
page:

```json
"header": {
  "height_mm": 15,
  "blocks": [{"type": "title", "text": "REGISTERED PAWNBROKER"}]
},
"footer": {
  "height_mm": 12,
  "blocks": [{"type": "field", "binding": "loan.number"}]
}
```

Headers and footers reserve body space and repeat on every generated page.
They accept only compact blocks; tables, signatures, containers, and page
breaks are rejected there.

### Safe formatting

Field, field-group, field-grid, and configured table-column values may use an
allow-listed `value_format`:

- `DEFAULT`
- `UPPER` or `LOWER`
- `DATE_DMY` or `DATE_MDY` for ISO dates
- `DECIMAL_2` for a plain numeric value

```json
{
  "type": "field",
  "binding": "loan.date",
  "value_format": "DATE_DMY"
}
```

Formatting fails closed when the source value is incompatible. For example,
`DECIMAL_2` does not attempt to guess or strip a currency prefix.

### Conditional presentation

Use a registered scalar binding with `PRESENT`, `EMPTY`, `EQUALS`, or
`NOT_EQUALS`:

```json
{
  "type": "section",
  "text": "Reversed document",
  "visible_when": {
    "binding": "document.status",
    "operator": "EQUALS",
    "value": "REVERSED"
  },
  "blocks": [{"type": "field", "binding": "document.status"}]
}
```

Required regulatory fields, required tables, and verification must also occur
outside conditional blocks. Conditions cannot make mandatory evidence
disappear from an official document.

### Overflow policy

Long values use one of:

- `WRAP`: normal multi-line flow;
- `SHRINK`: reduce the font after `max_characters` is exceeded, down to the
  renderer's readable minimum;
- `ERROR`: reject rendering after the limit is exceeded.

```json
{
  "type": "field",
  "binding": "borrower.display",
  "overflow_policy": "ERROR",
  "max_characters": 120
}
```

Use `ERROR` for identifiers or regulated boxes that must never wrap. Use
`WRAP` for addresses and descriptions. Use `SHRINK` only for bounded display
areas that have been physically test-printed.

```json
{"type": "title"}
```

```json
{"type": "field", "binding": "loan.number"}
```

```json
{
  "type": "field_group",
  "bindings": ["loan.number", "loan.date", "borrower.display"]
}
```

```json
{"type": "table", "binding": "collateral.items"}
```

```json
{"type": "spacer", "height_mm": 6}
```

```json
{
  "type": "signature",
  "text": "Borrower / customer | Authorized pawnbroker",
  "height_mm": 18
}
```

Only registered bindings and block properties are accepted. Python, model
paths, Django/Jinja expressions, HTML, and JavaScript are prohibited.

## Original, Duplicate, And Duplex Printing

Set `copy_mode` to one of:

```json
"copy_mode": "SINGLE"
```

```json
"copy_mode": "ORIGINAL_DUPLICATE"
```

```json
"copy_mode": "ORIGINAL_DUPLICATE_DUPLEX"
```

Duplex mode also requires `back_blocks`. Test duplex orientation and printer
edge binding physically; browser preview cannot prove the printer driver setup.

## Configure Other Document Types

Repeat the same process and choose one of:

- Repayment receipt
- Release memo
- Auction notice
- Auction recovery memo
- Renewal memo

Each type has different mandatory fields. Loans rejects publication if a
required regulatory/source field or required table is missing. Start from the
generated starter rather than building a definition from scratch.

## Correct A Published Layout

1. Open the published revision.
2. Select **Clone to new draft**.
3. Edit the new draft.
4. Preview and test-print it.
5. Publish the corrected revision.
6. Assign it to the intended scope.
7. Retire the old revision only after confirming the new assignment.

Retiring disables the old revision's active assignments. It does not delete
old issued PDFs or change historical reprints.

## Import And Export Layout Packs

Use **Export sanitized pack** to move a design between workspaces or keep a
reviewable design backup.

To import:

1. Open the Document layouts list.
2. Use **Import sanitized layout pack**.
3. Optionally enter a local layout name.
4. Upload the ZIP.
5. Review the imported draft.
6. Preview and test-print it locally.
7. Publish and assign it explicitly.

Imports never carry assignments, issued documents, users, tenant IDs, loan
data, or executable templates. They always remain drafts until reviewed.

## If Printing Fails

1. Do not repeatedly edit or replace stored files outside Rokkad.
2. Open **Integrity diagnostics** in Document layouts.
3. Resolve any layout, asset, issue, scope, or hash finding.
4. Clone and correct a bad published revision.
5. For an urgent print, an Owner/Admin may add:

```text
?renderer=fixed
```

to the existing PDF URL. This uses the built-in PDF and records an audit event.
It is a recovery action, not a silent fallback for broken configuration.

## Before Production Assignment

Complete the physical matrix in
[Loans Configurable Document Operations](../implementation/loans-configurable-document-operations.md):

- A4 and A5;
- simplex and duplex;
- original and duplicate copies;
- long borrower names and regional text;
- 25 or more collateral rows;
- image and PDF backgrounds;
- QR scan verification;
- margins and signature boxes;
- byte-identical reprint after changing the default.

Also run the tenant integrity gate:

```powershell
python manage.py tenant_command check_loan_document_integrity --schema=<schema> --fail-on-findings
```

Do not treat an on-screen PDF preview as physical printer acceptance.
