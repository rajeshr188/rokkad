I’ll trace the print path end-to-end from the template models to the print view and rendered HTML so we can map exactly how a GivenLoan gets turned into a printable layout. I’m starting with the model and then following where it’s used.

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/models/template.py)

Searched for regex `TemplateFrame|LoanTemplate|print|render|givenloan|GivenLoan` (`**/apps/tenant_apps/girvi/**/*.py`), 200 results

Searched for regex `template frame|TemplateFrame|LoanTemplate|print` (`**/templates/girvi/**/*.html`), 10 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/views/prints.py#1-1), lines 1 to 420

Searched for regex `def print_loan|loan_pdf|TemplateFrame|LoanTemplate|templateframe|render_to_string|weasyprint|xhtml2pdf` (`**/apps/tenant_apps/girvi/views/**/*.py`), 7 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/urls.py#130-130), lines 130 to 220

Searched for regex `TemplateFrame|LoanTemplate|get_custom_jcl|generate_loan_pdf|frame|draw|print_option` (`**/apps/tenant_apps/utils/loan_pdf.py`), 200 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/utils/loan_pdf.py#1-1), lines 1 to 420

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/admin.py#30-30), lines 30 to 150

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/utils/loan_pdf.py#640-640), lines 640 to 980

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/utils/loan_pdf.py#980-980), lines 980 to 1160

Searched for regex `templateframe_set|TemplateFrame\.|LoanTemplate\.objects\.get_default|get_custom_jcl\(` (`**/apps/tenant_apps/girvi/**/*.py`), 3 results

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/templates/girvi/loan/loan_detail_1.html#40-40), lines 40 to 90

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/models/__init__.py)

Searched for files matching `**/templates/**/preview_template.html`, 1 match

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/templates/admin/preview_template.html)

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/utils/loan_pdf.py#420-420), lines 420 to 640

Read [](file:///c%3A/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/views/__init__.py)

Great point to pause and map this. Here is how LoanTemplate and TemplateFrame drive GivenLoan printing in your codebase.

**End-to-end flow**
1. User clicks Print on loan detail in loan_detail_1.html.
2. Route goes to loan pdf endpoint in urls.py.
3. View loads the GivenLoan, gets default LoanTemplate, and calls the PDF builder in prints.py.
4. PDF builder function is get_custom_jcl in loan_pdf.py.
5. That function reads TemplateFrame rows for the selected LoanTemplate and renders each frame into PDF positions, then merges with base/duplicate/terms/form template files based on print_option.

**What LoanTemplate does**
1. Defines template-level print behavior and assets in template.py.
2. Important fields:
3. print_option controls output mode, such as O, OT, D, DF, BS, BD, BA, BDA in template.py.
4. base_template, dup_template, terms_template, form_d3_template are the background PDFs in template.py.
5. is_default determines which template print_loan picks via get_default in template.py.

**What TemplateFrame does**
1. Each row is one drawable block on the page in template.py.
2. frame_name picks what content to inject, like loan_id, customer_info, amount_words, loan_qr, customer_pic.
3. template_type scopes the frame to original, duplicate, or both in template.py.
4. field_type decides renderer path: text, image, table, qr in template.py.
5. x_pos, y_pos, width, height, font settings control placement and text style.
6. Uniqueness is enforced per template, frame_name, template_type in template.py.

**How frames are rendered**
1. get_custom_jcl builds a data_mapping from a GivenLoan into printable values in loan_pdf.py.
2. For each frame, it builds a ReportLab Frame from x_pos/y_pos/width/height in cm in loan_pdf.py.
3. Text fields become Paragraph + KeepInFrame.
4. Image fields open and center-fit image paths.
5. QR fields generate qrcode image from mapped text.
6. It selects frames by template_type plus BOTH in loan_pdf.py.

**How print_option changes output**
1. BA and BDA create side-by-side A4 landscape pages for original and duplicate in loan_pdf.py.
2. O, OT, D, DF produce A5 outputs with optional back-page templates.
3. BS and BD produce two outputs and then merge pages in loan_pdf.py.
4. Final overlay and multi-page composition uses PyMuPDF helpers in loan_pdf.py.

**Admin side for configuring templates**
1. LoanTemplate and TemplateFrame are managed in Django admin in admin.py.
2. You get inline frame editing through TemplateFrameInline.
3. There is also a visual-ish admin preview endpoint in admin.py with template preview_template.html.

**Important gotcha to keep in mind**
1. ReportLab uses bottom-left origin for y coordinates, but the admin preview div uses CSS top positioning in preview_template.html.
2. That means preview may not exactly match final PDF placement unless this coordinate difference is handled consistently.

If you want, next I can create a concrete map for one real LoanTemplate: each frame row and exactly what GivenLoan field it prints, so you can tune layout faster.



You are absolutely right, and your original design choice is strong.

Using a user-designed PDF base plus programmatic frame stitching is a practical solution when multilingual font/rendering is unreliable in direct HTML-to-PDF pipelines, especially for Tamil. Your current architecture in template.py, loan_pdf.py, and prints.py is aligned with that requirement.

The real gap now is access surface, not core engine:
1. Engine exists and works.
2. Configuration is mostly exposed through Django admin in admin.py.
3. You want it as tenant owner/admin operation inside the product UI.

That is the right next direction.

A good way to evolve it:
1. Keep current data model and PDF pipeline as-is.
2. Build tenant-facing Template Management pages for LoanTemplate and TemplateFrame.
3. Add role checks so only tenant owner/admin can manage templates.
4. Add a visual preview page in app UI using the same frame data.
5. Add a Publish/Default action so only one active default template per tenant.
6. Add versioning or clone-template workflow to avoid accidental production breakage.

Key implementation notes:
1. Move admin actions into normal views/forms, not replacing rendering logic.
2. Reuse get_custom_jcl from loan_pdf.py as the single rendering source.
3. Add tenant scoping to LoanTemplate and TemplateFrame (if not already done in this app context) so templates are isolated by workspace.
4. Expose the existing preview concept from preview_template.html in tenant UI.
5. Explicitly handle coordinate mismatch between CSS top-left preview and PDF bottom-left coordinates.

If you want, I can start implementing this as Phase 4A:
1. Tenant routes + list/create/edit/delete for LoanTemplate.
2. Inline frame editor page for TemplateFrame.
3. Permission guards for owner/admin only.
4. Non-admin preview page wired to current renderer.