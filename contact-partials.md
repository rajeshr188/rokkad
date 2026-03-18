# Contact App — Django 6 Native Partials + HTMX Architecture

## Templates
- templates/contact/customer_detail_improved.html — main detail page
  - item-level partials (used for optimistic single-row swaps):
    - customer-contact-item
    - customer-address-item
    - customer-proof-item
    - customer-relationship-item
  - section-level partials (full section container replacement — main CRUD target):
    - customer-contacts-section
    - customer-addresses-section
    - customer-proofs-section
    - customer-relationships-section
  - page partial: customer-detail inline (HTMX navigation target when HX-Target is the top container)  - profile header partial: `customer-hero` — wraps the avatar/name/edit-button hero strip; updated in-place after customer edit without a full page redirect  - inline JS listens for contactModalClose event and closes the modal after a successful POST

- templates/contact/customer_list_improved.html — list page
  - customer-filter-panel — filter sidebar/inline panel
  - customer-list-results — paginated card/row results (HTMX filter + pagination target)
  - customer-content inline — full page content (used when HX-Target is content, i.e. full HTMX page nav)

## View layer — common helpers (apps/tenant_apps/contact/views/common.py)
- CUSTOMER_DETAIL_TEMPLATE = "contact/customer_detail_improved.html"
- get_customer_for_detail(pk) — loads Customer with full prefetch: address, contactno, proofs, pics, relationships_created__related_customer
- render_customer_detail_fragment(request, customer, fragment_name, context=None, status=200, headers=None) — renders CUSTOMER_DETAIL_TEMPLATE#<fragment_name> with optional extra headers

## CRUD view pattern (address / contact / proof / relationship)
- All four sub-resource view modules import get_customer_for_detail and render_customer_detail_fragment from .common.
- GETs (form load): render partials/crispy_form.html into the modal (#modal-content).
- POST success: call render_customer_detail_fragment(...) with HTMX response headers:
  - HX-Retarget: #<section-id> (e.g. #customer-addresses-section)
  - HX-Reswap: outerHTML
  - HX-Trigger: contactModalClose
  This replaces the whole section and closes the modal in one response.
- DELETE / set-default: call render_customer_detail_fragment(...) with just the section name (no extra headers needed — no modal to close).
- Detail endpoints: render item-level partial with the specific object in context.

## Customer list view (apps/tenant_apps/contact/views/customer.py)
- _get_customer_list_context(request) — builds CustomerFilter + Paginator(12) context.
- customer_list():
  - export: returns TableExport response if _export param present.
  - HTMX with HX-Target == "content": renders customer-content fragment.
  - HTMX filter/pagination: renders customer-list-results fragment.
  - Full page load: renders full template.
- customer_detail():
  - HTMX: renders customer_detail_improved.html#customer-detail.
  - Full page: renders full template.- customer_save():
  - GET: renders `contact/customer_form.html` into `#modal-content` (has modal-header title + crispy form).
  - POST create success: `HX-Redirect` to new customer detail page (full nav, modal closes naturally).
  - POST update success: returns `customer-hero` fragment with `HX-Retarget: #customer-hero`, `HX-Reswap: outerHTML`, `HX-Trigger: contactModalClose` — refreshes hero in-place and closes modal.
## Key conventions
- No {% load partials %} — Django 6 native partials require no tag library.
- Fragment URL syntax: "template_path.html#partial-name" passed to render().
- Section containers use their partial name as their HTML id (e.g. id="customer-addresses-section") so HX-Retarget can reference them directly.
- Modal form action URL targets the sub-resource create/update view; hx-target="#modal-content" for GETs, success response retargets via headers.
