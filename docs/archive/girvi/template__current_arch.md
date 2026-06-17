---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Girvi Loan Template System: Current Architecture

Last updated: April 2026

> Formal assessment and roadmap: see [`assessment_and_roadmap.md`](./assessment_and_roadmap.md)
>
> Practical workflow guide: see [`template_management_workflow_guide.md`](./template_management_workflow_guide.md)
>
> Current operational summary: see [`current_implementation.md`](./current_implementation.md)

---

## 1) Architectural intent

The Girvi print system is intentionally built around a **background-PDF + positioned-frame overlay** model.

This design should be preserved because it provides:
- reliable visual fidelity for business-designed ticket layouts
- predictable multilingual rendering where pure HTML-to-PDF approaches were inconsistent
- controlled placement of dynamic fields such as loan data, QR codes, photos, and summary blocks

In practice:
1. a tenant prepares the visual ticket in an external design tool
2. the design is uploaded as PDF background assets
3. `TemplateFrame` rows define where dynamic data should be injected
4. the renderer draws those values onto the PDF at print time

---

## 2) Core domain objects

### `LoanTemplate`
Represents one printable layout configuration.

It stores:
- template name and activation/default flags
- `print_option` (for original / duplicate / A4 / back-page modes)
- page dimensions
- uploaded PDF assets such as `base_template`, `dup_template`, `terms_template`, and `form_d3_template`

### `TemplateFrame`
Represents one printable region inside a template.

It stores:
- `frame_name` identifying the business field to render
- `template_type` (`ORIGINAL`, `DUPLICATE`, `BOTH`)
- `field_type` (`TEXT`, `IMAGE`, `QR`, `TABLE`)
- `x_pos`, `y_pos`, `width`, `height`
- font and boundary settings used during rendering and preview

Primary model file:
- `apps/tenant_apps/girvi/models/template.py`

---

## 3) Runtime print flow

The live print path is now organized under Girvi-owned modules instead of shared utilities.

### Current end-to-end flow
1. the user clicks **Print** from the loan screen
2. `print_loan()` resolves the requested or default active template
3. `LoanPrintService` performs readiness and rendering orchestration
4. the document renderer resolves frame values from the `GivenLoan`
5. ReportLab draws the values into the configured frame rectangles
6. PyMuPDF combines the rendered overlay with the uploaded PDF backgrounds
7. the final PDF is returned to the browser

Primary runtime modules:
- `apps/tenant_apps/girvi/views/prints.py`
- `apps/tenant_apps/girvi/service_modules/printing.py`
- `apps/tenant_apps/girvi/documents/loan_ticket.py`
- `apps/tenant_apps/girvi/documents/release_forms.py`

Legacy compatibility note:
- `apps/tenant_apps/utils/loan_pdf.py` is retained only as a compatibility layer and should not be treated as the long-term ownership location for Girvi print logic.

---

## 4) Module ownership and responsibilities

### `documents/loan_ticket.py`
Owns the main Girvi loan-ticket rendering logic.

Responsibilities:
- resolve printable values from the loan object
- support text, image, QR, and table frames
- handle original / duplicate / A4 composite output modes
- provide compatibility fallbacks across older and newer `GivenLoan` APIs
- expose the frame-value provider registry for future field expansion

### `service_modules/printing.py`
Owns orchestration and guardrails around printing.

Responsibilities:
- resolve which template should be used
- evaluate template readiness
- produce user-facing readiness summaries
- centralize rendering entry points
- return structured print results for the views layer

### `views/template.py`
Owns tenant-facing template management workflows.

Responsibilities:
- list/create/update/delete templates
- manage frames per template
- seed starter frames
- clone templates safely
- run test-print actions
- serve browser preview and real PDF preview
- block default activation when blocking readiness issues exist

---

## 5) Supported output modes

The system currently supports the following print modes:

| Option | Meaning |
|---|---|
| `O` | Original only |
| `OT` | Original with terms/back page |
| `D` | Duplicate only |
| `DF` | Duplicate with Form D3 back page |
| `BS` | Both copies, separate/single-sided |
| `BD` | Both copies, double-sided |
| `BA` | Both copies side-by-side on A4 |
| `BDA` | Both copies on A4 with back pages |

These modes are driven by `LoanTemplate.print_option` and determine which background assets are expected and how the final PDF is composed.

---

## 6) Productized tenant workflow now available

The original engine has now been successfully exposed through the tenant UI.

Implemented capabilities include:
- tenant-facing template CRUD
- frame CRUD for each template
- starter-frame generation for first-time setup
- browser preview with measurement grid
- real PDF preview for fidelity checks
- test-print with the latest available loan
- template cloning for safe experimentation
- readiness assessment before promoting a template to default

This means day-to-day template operations no longer depend on Django admin for normal business use.

---

## 7) Coordinate system and preview behavior

A key architecture detail is the coordinate conversion between preview and final PDF output.

### Stored / render coordinates
- PDF rendering uses a **bottom-left origin**
- frame dimensions are stored in **centimeters**

### Browser preview
- the on-screen preview uses a **top-left visual layout**
- the UI converts coordinates so admins can position frames more intuitively
- the visible grid helps estimate spacing quickly, but **real PDF preview remains the source of truth** for final fidelity

This distinction is important whenever text wrapping, image fit, or A4 composite layouts are being tuned.

---

## 8) Extensibility model

The renderer now uses a provider-style field resolution approach rather than relying on one large hardcoded mapping block.

This gives a cleaner path for adding new frame names such as:
- additional business/license fields
- loan summary variations
- customer/ornament details
- future derived values

Primary extension point:
- `FRAME_VALUE_PROVIDERS` in `apps/tenant_apps/girvi/documents/loan_ticket.py`

Recommended rule:
- add new printable fields through the provider registry first, rather than scattering template-specific logic across views or HTML.

---

## 9) Safeguards currently in place

The current architecture includes several operational protections:

- active/default template resolution is centralized
- readiness checks detect missing required frames or PDF assets
- test-print lets admins validate against a real loan before rollout
- clone-first workflow reduces risk when changing a live template
- compatibility fallbacks prevent breakage across older `GivenLoan` method variants

These safeguards are now part of the normal product workflow, not just developer-only practices.

---

## 10) What should remain unchanged

The following architectural decisions are considered correct and should be preserved:

1. keep the **background-PDF + frame overlay** model
2. keep Girvi print logic owned inside `apps/tenant_apps/girvi/`
3. keep rendering orchestration in the service layer rather than views
4. keep tenant-specific template operations inside the product UI
5. keep browser preview as an aid, but use real PDF preview/test print for final validation

---

## 11) Remaining optional enhancements

The major productization work is complete. Remaining items are optional polish rather than architectural gaps:

- lightweight template version history / audit trail
- richer help text for supported frame names and expected values
- additional field providers if business needs expand
- further documentation cleanup for onboarding and support teams

---

## 12) Summary

The Girvi template system is now in a good architectural state:
- the core rendering strategy remains appropriate for the business problem
- ownership has been moved into the Girvi domain
- tenant-facing management workflows are in place
- readiness, preview, clone, and test-print features reduce operational risk
- future extension points are clearer and more maintainable than before

This should be treated as the stable baseline architecture for future Girvi template work.

