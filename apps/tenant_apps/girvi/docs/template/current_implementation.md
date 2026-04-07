# Girvi Loan Template System: Current Architecture and Productization Plan

Last updated: March 2026 (implementation in progress)

> Formal assessment and roadmap: see [`assessment_and_roadmap.md`](./assessment_and_roadmap.md)
>
> Practical workflow guide: see [`template_management_workflow_guide.md`](./template_management_workflow_guide.md)

## Why this architecture exists

The current PDF rendering architecture is intentional and should be preserved:

1. Tenant users design a visual ticket in external tools like Google Docs or Microsoft Office.
2. That design is exported as background PDF assets (base, duplicate, terms, Form D3).
3. Structured data is then injected into defined frame coordinates on top of those PDFs.

This approach was chosen because direct in-app rendering of some language text (especially Tamil) was unreliable in previous attempts. The external PDF template plus frame stitching pattern gives predictable typography and layout fidelity while still allowing dynamic data insertion.

## Current implementation summary

### Data model

1. LoanTemplate stores template metadata and uploaded PDF assets.
2. TemplateFrame stores named data regions with position and rendering type.

Key files:

1. [apps/tenant_apps/girvi/models/template.py](apps/tenant_apps/girvi/models/template.py)

### Print flow for GivenLoan

1. User clicks Print from loan detail.
2. Print view resolves the default active template.
3. PDF renderer maps frame names to loan data, draws by coordinates, and merges with template PDFs based on print_option.

Key files:

1. [apps/tenant_apps/girvi/views/prints.py](apps/tenant_apps/girvi/views/prints.py)
2. [apps/tenant_apps/utils/loan_pdf.py](apps/tenant_apps/utils/loan_pdf.py)

### Print options currently supported

1. Original-only, duplicate-only, and dual-copy paths.
2. Optional back pages for terms and Form D3.
3. A5 and side-by-side A4 layouts.

### Tenant UI implementation status (March 2026)

Implemented now:

1. Tenant-facing LoanTemplate list/create/update/delete/detail/preview screens.
2. Template default and activation actions in product UI.
3. TemplateFrame list/create/update/delete per template.
4. Starter pack download action exposed directly in template workflow screens.
5. Coordinate-system guidance in preview and template detail.
6. Paper-size reference (A4/A5) and redesign workflow mapping in template form.

New onboarding enhancement implemented:

1. "Create Starter Frames" action on template detail.
2. Seeds a baseline set of required frames with visible boundaries:
3. loan_id, loan_date, customer_info, loan_desc, weight, amount, amount_words, loan_qr.
4. Idempotent behavior: creates missing starter frames and leaves existing matching frames unchanged.

## Current gap

Template management is mostly a Django admin operation today, but business intent is for tenant owner and tenant admin users to manage templates inside product UI.

## Productization objective

Expose template configuration and preview as tenant-facing workflows while keeping the current PDF engine and frame model unchanged.

## Plan

### Phase A: Tenant-facing template management

Status: Implemented.

1. Build LoanTemplate list/create/update/delete screens in app UI. ✅
2. Add template activation and default actions. ✅
3. Restrict access to tenant owner/admin roles. ✅

### Phase B: Tenant-facing frame management

Status: Implemented for baseline CRUD + starter seeding.

1. Build frame list and editor for each template. ✅
2. Support frame_name, template_type, field_type, x/y/width/height, font settings. ✅
3. Preserve current uniqueness constraints and model validation. ✅
4. Add starter-frame seeding action for first-time setup. ✅

### Phase C: Preview and coordinate correctness

Status: Implemented.

1. Add in-app preview page equivalent to admin preview. ✅
2. Address coordinate-system mismatch explicitly. ✅
3. PDF uses bottom-left origin. ✅
4. Browser preview uses top-left origin. ✅
5. Add conversion guidance and helper overlays. ✅

### Phase C.1: Onboarding and usability hardening

Status: Implemented.

1. Surface starter pack download in list, create, and detail workflows. ✅
2. Add explicit mapping guidance for uploaded PDF assets. ✅
3. Add paper-size references for page dimension input. ✅
4. Add starter frame generation for easier first-time frame placement. ✅

### Phase D: Safety and governance

1. Add duplicate or clone template action.
2. Add lightweight versioning or audit log for template edits.
3. Validate files and frame bounds before publish/default activation.

Status: Partially implemented.

1. Frame bounds validation exists at model level. ✅
2. Duplicate/clone template action. ⏳
3. Lightweight versioning/audit log for template edits. ⏳
4. Strong publish/readiness checks before default activation. ⏳

### Phase E: Rollout

1. Keep Django admin as fallback initially.
2. Roll out tenant UI to owner/admin users first.
3. Migrate operational use from admin to tenant UI after acceptance.

## Non-goals

1. Rewriting the PDF renderer away from the frame-stitching model.
2. Replacing Office/Docs-designed backgrounds with pure HTML template generation.
3. Broad font-engine experimentation during this transition.

## Risks and mitigations

1. Risk: Tenant edits break print layouts.
2. Mitigation: clone-first workflow, preview-before-publish, default rollback.

3. Risk: Coordinate confusion between preview and PDF output.
4. Mitigation: explicit coordinate legend and transformed preview overlays.

5. Risk: Template isolation between tenants.
6. Mitigation: enforce tenant-scoped querysets and permission checks in all template/frame views.

## Success criteria

1. Tenant owner/admin can manage templates without Django admin.
2. Existing print behavior remains unchanged for active templates.
3. Tamil and other multilingual content remain stable via background-PDF design workflow.
4. Print errors caused by template misconfiguration are reduced through validation and preview.