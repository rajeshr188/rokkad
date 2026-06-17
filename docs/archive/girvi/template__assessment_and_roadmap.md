---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Girvi Loan Template System Assessment and Roadmap

Last updated: April 2026

> Practical workflow guide: see [`template_management_workflow_guide.md`](./template_management_workflow_guide.md)

## Executive summary

The current Girvi loan template system is a **good architectural fit** for the business problem.

It correctly uses:
- external PDF background assets for stable visual layout
- `LoanTemplate` + `TemplateFrame` for structured configuration
- a Girvi-local renderer in `documents/loan_ticket.py`
- tenant-facing UI for template and frame management

This design should be **preserved**, not replaced.

> Important assumption: **tenant scoping is not treated as a gap in this assessment** because template management runs inside each tenant/schema. Template defaults are therefore operationally schema-local rather than globally shared across customers.

---

## Scope reviewed

Primary files reviewed:

- `apps/tenant_apps/girvi/models/template.py`
- `apps/tenant_apps/girvi/views/template.py`
- `apps/tenant_apps/girvi/views/prints.py`
- `apps/tenant_apps/girvi/documents/loan_ticket.py`
- `apps/tenant_apps/girvi/service_modules/printing.py`
- `templates/girvi/template/template_detail.html`
- `templates/girvi/template/template_preview.html`

---

## 1) Current system review

### What is working well

#### A. Strong business-fit architecture
The existing template model is practical and appropriate for Girvi ticket printing:

1. users design the ticket visually in external tools
2. the design is exported as PDF assets
3. dynamic loan data is injected into named frames
4. the output is merged according to the selected print mode

This is especially useful when exact print fidelity matters and multilingual HTML-to-PDF rendering is unreliable.

#### B. Good separation of configuration vs rendering
The current split is conceptually sound:

- `LoanTemplate` stores print assets and page settings
- `TemplateFrame` stores layout coordinates and field metadata
- `loan_ticket.py` handles rendering and merge logic
- `views/template.py` handles UI management

This is the right foundation for long-term maintainability.

#### C. Product UI is already meaningfully improved
Compared with an admin-only workflow, the current UI now provides:

- template CRUD
- frame CRUD
- preview screens
- starter frame seeding
- coordinate guidance
- grid overlays for easier positioning

That is a strong usability step forward.

#### D. Existing validations already reduce obvious mistakes
There is already useful protection in place:

- frame geometry validation in `TemplateFrame.clean()`
- active/default template flags
- starter-frame blueprints
- preview support before production use

---

## 2) Key drawbacks in the current architecture

### 1. Renderer complexity is still high
`build_loan_ticket_pdf()` in `apps/tenant_apps/girvi/documents/loan_ticket.py` is doing too many jobs at once:

- template resolution
- loan/party data extraction
- frame-value mapping
- frame rendering
- print-option branching
- PDF merge orchestration
- exception handling

This works, but it makes change-risk higher than necessary.

### 2. Error handling is too coarse
At the moment, if something goes wrong during rendering, the flow often ends with:

- a logged exception
- `None` returned from the renderer
- a generic user-facing failure message

That is safe, but not very diagnosable for business users or maintainers.

### 3. Template readiness is not strongly enforced
A template can be marked active/default even if:

- required assets for the chosen `print_option` are missing
- important frames are missing
- a real sample print has not been tested

That creates avoidable runtime surprises.

### 4. Frame semantics are hardcoded
Frame names such as `loan_id`, `customer_info`, `amount_words`, and `loan_qr` are mapped in Python code.

This gives control and safety, but it also means:
- new printable fields require code changes
- advanced configuration remains developer-dependent

### 5. Preview is helpful but still approximate
The browser preview is now much better, but it is still not a perfect match for final PDF output because:

- HTML preview uses CSS rendering
- PDF output uses ReportLab and PyMuPDF
- line wrapping and font metrics may differ slightly

### 6. Governance features are still light
The system currently lacks full lifecycle tooling such as:

- template cloning
- version history
- change audit log
- explicit rollback workflow

These are not required for basic use, but they become important as more users manage templates directly.

---

## 3) Gap matrix

| Gap ID | Area | Current state | Impact | Severity | Recommendation |
|---|---|---|---|---|---|
| G1 | Renderer maintainability | **Improved**: renderer now split into smaller render/composition helpers, but mapping is still code-driven | Safer extension than before, but still room to simplify field providers | Medium | Continue modularization and introduce a registry/provider pattern for frame values |
| G2 | Error visibility | **Improved**: readiness summaries and frame-level logging now exist | Failures are more diagnosable, though operator guidance can still improve further | Medium | Keep improving structured logs and user-facing troubleshooting hints |
| G3 | Readiness validation | **Partially resolved**: readiness checks now exist before setting default | Misconfiguration risk is reduced significantly | Low/Medium | Add stronger publish workflow only if needed later |
| G4 | Template lifecycle | **Improved**: clone workflow now exists | Safer experimentation is now supported | Low/Medium | Add lightweight history/audit trail if operational demand grows |
| G5 | Preview fidelity | **Improved**: browser-grid preview plus real PDF preview now available | Preview confidence is much better | Low/Medium | Consider richer sample-loan selection later |
| G6 | Field extensibility | **Improved**: registry/provider pattern now drives frame-value resolution | New fields are easier to add with less main-renderer churn | Low/Medium | Continue documenting supported providers and extend only as business needs grow |
| G7 | Service-layer adoption | **Improved**: main loan print path now routes through `LoanPrintService` | Orchestration is more centralized | Low | Continue using service entry points for future print actions |
| G8 | Operational testing | **Improved**: test print and PDF preview actions now exist | Issues can be detected earlier by admins | Low | Expand sample-loan selection only if needed |

---

## 4) Phased enhancement plan

### Phase 1 â€” Stability and supportability
**Goal:** make the current system safer without changing the core model.

Status: **Largely implemented.**

Actions:
1. Add better exception messages around frame rendering and merge steps. âœ…
2. Log the failing `frame_name`, `template_id`, and print mode when a render fails. âœ…
3. Add a template readiness check before allowing â€œSet as Defaultâ€. âœ…
4. Add a â€œTest printâ€ action from the template detail screen. âœ…

Expected outcome:
- faster debugging
- fewer unexplained print failures
- safer production usage

### Phase 2 â€” Governance and authoring workflow
**Goal:** reduce accidental breakage during template editing.

Status: **Partially implemented.**

Actions:
1. Add â€œClone Templateâ€ action. âœ…
2. Add lightweight change history or audit notes. â³
3. Separate `draft` vs `active/default` workflow more clearly. â³
4. Add stronger warnings when critical files or frames are missing. âœ…

Expected outcome:
- safer experimentation
- easier rollback
- clearer operational ownership

### Phase 3 â€” Renderer modularization
**Goal:** improve maintainability without changing the external behavior.

Status: **Substantially implemented.**

Actions:
1. Split `build_loan_ticket_pdf()` into smaller helpers/services. âœ…
2. Separate frame mapping from render composition. âœ…
3. Separate print-option composition from low-level drawing. âœ…
4. Push print orchestration consistently through `LoanPrintService`. âœ…

Expected outcome:
- simpler maintenance
- easier testing
- lower risk when adding print modes or frame types

### Phase 4 â€” Better preview and extensibility
**Goal:** improve editor confidence and long-term flexibility.

Status: **Preview slice and field-extensibility slice implemented; advanced field expansion remains optional.**

Actions:
1. Add sample-render preview using the real PDF engine. âœ…
2. Improve field mapping with a registry/provider approach. âœ…
3. Add optional advanced fields without bloating the core UI. â³
4. Provide a clearer â€œsupported printable fieldsâ€ reference in docs/UI. â³

Expected outcome:
- better preview trust
- smoother future feature additions
- less renderer coupling

---

## 5) Recommended implementation roadmap

### Short-term roadmap (recommended next 2â€“4 PRs)

#### PR-1: Readiness validation and better print errors
Scope:
- add readiness checks for `print_option`
- improve render failure logs/messages
- identify exact failing frame in logs where possible

Recommended files:
- `apps/tenant_apps/girvi/documents/loan_ticket.py`
- `apps/tenant_apps/girvi/views/template.py`
- `apps/tenant_apps/girvi/views/prints.py`

#### PR-2: Clone template workflow
Scope:
- add clone action for `LoanTemplate`
- duplicate associated `TemplateFrame` rows
- make â€œclone then editâ€ the safest recommended path

Recommended files:
- `apps/tenant_apps/girvi/views/template.py`
- `apps/tenant_apps/girvi/urls.py`
- template management HTML files

#### PR-3: Service-layer consolidation
Scope:
- make `LoanPrintService` the canonical orchestration path
- keep views thin and predictable
- centralize default-template resolution and render result handling

Recommended files:
- `apps/tenant_apps/girvi/service_modules/printing.py`
- `apps/tenant_apps/girvi/views/prints.py`

#### PR-4: Render-accurate preview improvements
Scope:
- add a sample ticket preview generated by the real renderer
- keep the existing browser-grid preview as the editable layout aid

Recommended files:
- `apps/tenant_apps/girvi/views/template.py`
- `templates/girvi/template/template_preview.html`

---

## 6) Actionable PR-sized delivery backlog

### PR-1 â€” Print readiness and diagnostics
**Objective:** prevent avoidable runtime failures and make errors diagnosable.

**Scope**
- readiness validation for each `print_option`
- clearer logging in the renderer
- user-visible warning state on template detail pages

**Tasks**
- [x] Add a readiness evaluator for `LoanTemplate` that checks required PDF assets by print mode.
- [x] Flag missing critical starter frames or obviously incomplete configurations.
- [x] Show readiness status and missing-items summary in `views/template.py` / template detail UI.
- [x] Improve renderer logs to include `loan_id`, `template_id`, `print_option`, and failing `frame_name` where possible.
- [x] Replace generic failure messaging with a more actionable operator message.

**Acceptance criteria**
- A template can be reviewed for readiness before being marked default.
- Missing assets are visible from the product UI.
- When print fails, logs identify the failure context clearly.

**Verification**
- `manage.py check`
- renderer tests continue to pass
- new readiness validation tests for representative print modes

### PR-2 â€” Clone template and safe edit workflow
**Objective:** make template iteration safer for non-developer admins.

**Scope**
- add a clone action
- duplicate all frame rows
- ensure cloned templates start inactive/non-default unless explicitly promoted

**Tasks**
- [x] Add â€œClone Templateâ€ action on template detail/list views.
- [x] Duplicate `LoanTemplate` metadata and associated `TemplateFrame` rows.
- [x] Name the copy predictably, e.g. `Original Name (Copy)`.
- [x] Ensure cloned templates do not automatically become default.
- [x] Add a success message guiding users to edit the cloned version.

**Acceptance criteria**
- Admin can clone a working template in one step.
- All frame geometry is preserved in the clone.
- Production/default template remains untouched during experimentation.

**Verification**
- view tests for clone action
- manual check that copied frames match source count and values

### PR-3 â€” Service-layer consolidation and renderer modularization
**Objective:** reduce maintenance risk without changing output behavior.

**Scope**
- move orchestration fully behind `LoanPrintService`
- split `build_loan_ticket_pdf()` into smaller units

**Tasks**
- [x] Make `LoanPrintService` the canonical print entry point from `views/prints.py`.
- [ ] Extract frame-value mapping into a dedicated helper/provider.
- [x] Extract print-option composition (`O`, `OT`, `BS`, `BD`, `BA`, `BDA`) into smaller functions.
- [x] Keep low-level draw helpers in `loan_ticket.py` but simplify the top-level flow.
- [x] Preserve current behavior and compatibility fallbacks for refactored `GivenLoan` APIs.

**Acceptance criteria**
- The print view becomes thinner and easier to reason about.
- Renderer code is split into smaller testable units.
- Existing print behavior remains unchanged.

**Verification**
- `manage.py check`
- `apps.tenant_apps.girvi.tests.test_loan_ticket_renderer`
- `apps.tenant_apps.girvi.tests.test_payment_integration_pr1_pr2.PrintLoanViewTests`

### PR-4 â€” Preview fidelity and test-print workflow
**Objective:** improve confidence that what users see matches what prints.

**Scope**
- add a sample render preview or test-print action using the real renderer
- keep the current grid preview for layout editing

**Tasks**
- [x] Add a â€œTest Printâ€ action from template detail.
- [x] Allow previewing a template against a selected/sample loan.
- [x] Keep the current browser-grid overlay as the fast layout tool.
- [x] Document preview limitations where browser and PDF rendering can still differ.

**Acceptance criteria**
- Admin can validate a template with a real PDF output before operational use.
- Grid preview remains available for fast coordinate editing.
- Preview confidence improves for complex layouts.

**Verification**
- template view smoke checks
- manual PDF preview validation on a sample loan

### PR-5 â€” Optional extensibility improvements
**Objective:** make future field additions easier without destabilizing the core flow.

**Scope**
- improve maintainability of frame mapping
- better documentation of supported frame types and fields

**Tasks**
- [x] Introduce a registry/provider pattern for frame-name-to-value mapping.
- [ ] Centralize supported printable fields in one documented location.
- [ ] Add docs/UI help for field behavior, especially image/QR/table expectations.

**Acceptance criteria**
- New printable fields can be added with less branching in the main renderer.
- Admins have clearer guidance on what each frame type expects.

---

## 7) Recommended target architecture

### Keep these parts
The following should remain the core design:

- `LoanTemplate`
- `TemplateFrame`
- PDF asset + overlay strategy
- Girvi-local document rendering module
- tenant-facing template management UI

### Improve these parts
The following should evolve next:

- add publish/readiness checks
- improve failure visibility
- add clone/version workflow
- reduce renderer complexity through smaller units/services
- improve preview fidelity using the actual render pipeline

---

## 8) Final assessment

### Overall assessment
The Girvi loan template system is **well chosen architecturally** and already **usable in production-style workflows**. It does **not** need a rewrite.

The most valuable next steps are not structural replacement, but **hardening and operational polish**:

1. better readiness validation
2. better error visibility
3. safer editing workflow via clone/history
4. cleaner renderer/service boundaries

### Final recommendation
Preserve the current frame-driven PDF architecture and improve it incrementally through focused PRs.

This gives the team:
- low regression risk
- better operator confidence
- safer customization for tenant requirements
- a clearer path to long-term maintainability

