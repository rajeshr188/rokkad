---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Girvi Template Management Workflow and Usage Guide

Last updated: April 2026

## Purpose

This guide documents the **recommended day-to-day workflow** for creating, updating, testing, and operating Girvi loan print templates.

It is intended as a future reference for:
- tenant owners/admins managing ticket layouts
- developers supporting template issues
- team members onboarding into the Girvi print system

---

## 1) What the template system does

The Girvi print system combines:

1. **background PDF assets** designed externally
2. **frame metadata** stored in the app
3. **loan data injection** at print time

### Main objects

- `LoanTemplate`
  - stores the print mode, page size, and uploaded PDF assets
- `TemplateFrame`
  - stores which field to print, where to place it, and how to render it

### Core rendering flow

1. user prints a loan
2. the default active template is selected
3. frame values are resolved from the loan
4. content is drawn into the configured frame rectangles
5. the generated content is merged with the background PDFs

---

## 2) When to create a new template

Create a new template when:
- your business wants a different ticket layout
- you need a different print mode or page size
- you are redesigning the base print background
- you want to test a new format without changing the current live one

> Best practice: **clone an existing working template first** when making layout changes to a live setup.

---

## 3) Roles and access

Template management is intended for **tenant owner/admin** users.

These users can:
- create templates
- upload assets
- add/edit/delete frames
- preview and test-print templates
- activate/deactivate templates
- set a template as the default
- clone a template for safe editing

---

## 4) Recommended end-to-end workflow

### Step 1 â€” Prepare the visual design externally
Design the ticket layout in an external tool such as:
- Google Docs
- Microsoft Word / Office
- any PDF-friendly design tool

Then export the final backgrounds as PDF files.

Typical assets:
- `base_template` â€” original/front background
- `dup_template` â€” duplicate/front background
- `terms_template` â€” original back page
- `form_d3_template` â€” duplicate back page

---

### Step 2 â€” Create the template record in Girvi
Go to the template management screen and create a new `LoanTemplate`.

Set:
- **template name**
- **print option**
- **page width / page height** in centimeters
- uploaded PDF assets needed for that print mode

Do **not** make it default immediately unless it has already been tested.

---

### Step 3 â€” Choose the correct print mode
Use the print mode that matches how the business wants the ticket printed.

| Print option | Meaning | Typical assets |
|---|---|---|
| `O` | Original only | `base_template` optional but recommended |
| `OT` | Original with back page | `base_template`, `terms_template` |
| `D` | Duplicate only | `dup_template` |
| `DF` | Duplicate with Form D3 back page | `dup_template`, `form_d3_template` |
| `BS` | Both copies single-sided | `base_template`, `dup_template` |
| `BD` | Both copies double-sided | `base_template`, `dup_template`, `terms_template`, `form_d3_template` |
| `BA` | Both on one A4 landscape page | `base_template`, `dup_template` |
| `BDA` | Both on A4 with back pages | `base_template`, `dup_template`, `terms_template`, `form_d3_template` |

> Missing PDFs are often handled as warnings rather than hard blockers, but using the correct assets gives the most reliable output.

---

### Step 4 â€” Create starter frames
Use **Create Starter Frames** to seed the default working frame set.

This provides a baseline layout for common fields such as:
- loan ID
- date
- customer info
- amount
- amount in words
- description
- QR code
- image blocks

This is the fastest way to start a new layout because you adjust existing frames rather than placing everything manually.

---

### Step 5 â€” Adjust frames carefully
Edit `TemplateFrame` rows to position each field correctly.

Each frame controls:
- `frame_name`
- `template_type` (`Original`, `Duplicate`, `Both`)
- `field_type` (`Text`, `Image`, `QR`, `Table`)
- `x_pos`, `y_pos`, `width`, `height`
- font settings and boundary visibility

### Coordinate rule
Stored coordinates use **PDF space**:
- origin is **bottom-left**
- values are in **centimeters**

The browser preview converts that to top-left display coordinates for easier editing.

---

### Step 6 â€” Use the preview tools
There are now **two kinds of preview**:

#### A. Browser grid preview
Use this for:
- fast visual placement
- seeing frame boundaries
- checking spacing with the centimeter grid

#### B. Real PDF preview
Use **Open Real PDF Preview** when you need to compare the layout against the actual rendered output.

Use this especially when:
- text wraps unexpectedly
- images look off
- QR placement seems right in the browser but wrong in print

---

### Step 7 â€” Check the Print Readiness panel
Before promoting a template, review the **Print Readiness** section on the template detail page.

Possible states:
- **Ready** â€” safe to use
- **Ready with warnings** â€” works, but some recommended assets/frames are missing
- **Needs attention** â€” fix the blocking issues before making it default

The panel highlights:
- missing frames
- missing PDFs for the selected mode
- invalid or incomplete setup

---

### Step 8 â€” Run a test print
Use:
- **Test Print With Latest Loan**

This generates a real PDF using the latest available loan record and helps catch problems before users hit them in live printing.

If there is no loan yet, the system will warn and ask you to try again later.

---

### Step 9 â€” Set as default only after validation
Once the template looks correct in:
- grid preview
- real PDF preview
- test print

then set it as the **default** template.

This makes it the template used by the normal loan print flow.

---

## 5) Safe workflow for changing a live template

When a template is already in active use:

1. **Clone the template**
2. edit the cloned copy
3. preview and test-print the clone
4. activate it only after validation
5. set the new one as default if approved

This avoids breaking the live print output during experimentation.

---

## 6) Common frame usage reference

Typical frame names and what they represent:

| Frame name | Usage |
|---|---|
| `loan_id` | Loan identifier |
| `loan_date` | Loan date |
| `customer_info` | Name, relation, address, phone |
| `customer_name` | Name only |
| `loan_desc` | Loan item description block |
| `amount` | Loan amount |
| `amount_words` | Amount in words |
| `weight` | Weight summary |
| `pure` | Pure-weight summary |
| `value` | Current value |
| `loan_qr` | QR code from loan ID |
| `customer_pic` | Customer photo |
| `loanitem_pic` | Loan item photo |
| `license_no` / `license_name` / `license_address` | Shop/license details |

For developer reference, these values are resolved through the frame provider registry in:
- `apps/tenant_apps/girvi/documents/loan_ticket.py`

---

## 7) Troubleshooting guide

### Problem: preview looks right but print looks different
Use **Open Real PDF Preview**. The browser preview is helpful, but the actual PDF renderer is the final source of truth.

### Problem: print fails completely
Check:
1. Print Readiness panel
2. whether the template is active/default
3. whether a frame expects missing loan/customer/license data
4. server logs for the failing `frame_name`

### Problem: no background PDF but output still prints
This can be expected. In some modes the renderer can still produce content on a blank page even if a background asset is missing.

### Problem: frame cannot be saved
Usually this means the frame goes outside the page bounds or uses invalid width/height values.

### Problem: no sample output available for preview/test print
Create at least one loan so the system has a sample record to render.

---

## 8) Recommended operating practices

1. Keep one **stable default** template at all times.
2. Use **clone-first** for any non-trivial change.
3. Use **starter frames** when building from scratch.
4. Verify both the **grid preview** and the **real PDF preview**.
5. Use **test print** before making a template default.
6. Keep PDF backgrounds versioned externally if design changes frequently.
7. Avoid unnecessary field proliferation unless the business really needs it.

---

## 9) Developer maintenance notes

Relevant implementation files:

- `apps/tenant_apps/girvi/models/template.py`
- `apps/tenant_apps/girvi/views/template.py`
- `apps/tenant_apps/girvi/views/prints.py`
- `apps/tenant_apps/girvi/service_modules/printing.py`
- `apps/tenant_apps/girvi/documents/loan_ticket.py`

Related docs:
- `current_implementation.md`
- `assessment_and_roadmap.md`

---

## 10) Summary

The safest and most effective workflow is:

1. create or clone a template
2. upload the correct PDF assets
3. seed starter frames
4. adjust frame positions
5. use browser preview + real PDF preview
6. run a test print
7. only then activate/set default

This keeps the Girvi print system reliable while still allowing flexible business-specific ticket customization.

