---
status: accepted
owner: project
updated: 2026-09-22
tags: [ui, django, htmx, accessibility]
---

# Native Django partials for the redesign

The owner selected Django 6 native template partials with HTMX and the latest
stable Bootstrap for the pre-cutover redesign. Use ordinary Django templates,
views, forms and existing services. No additional partial-template package or
client-side application framework is needed.

Define a partial beside its full-page context with `partialdef ... inline` and
render `template.html#name` for a known HTMX target. Ordinary navigation, boosted
requests and history restoration receive a complete document. The same authorized
view builds both representations; the request header grants no access. Vary caches
by the representation headers and disable storage of private business responses.
Prevent HTMX localStorage history snapshots on pages containing borrower records.

Use progressive GET forms/links first. Synchronize replaceable searches, preserve
focus, announce result changes and provide visible error recovery. Session-expiry
redirects must navigate normally rather than place a login page inside results.
Keep filtered exports and page links bound to the displayed server result.
Financial writes retain their current service, CSRF, approval and idempotency
boundaries; partial rendering does not alter transaction semantics.

Bootstrap 5.3.8 is verified as the latest stable version at this checkpoint and is
pinned with SRI in the active shared base. Existing local HTMX 1.9.10 supports the
first slice; a separate application-wide HTMX 2 migration is not claimed. Older
legacy shells remain for inventory and later consolidation. English/Hindi use
Django gettext and LocaleMiddleware, with explicit language submission and a
matching document language. Preserve original customer names and source evidence.

References: [Django native partials](https://docs.djangoproject.com/en/6.0/ref/templates/language/#template-partials),
[Bootstrap release](https://getbootstrap.com/docs/5.3/getting-started/introduction/),
[HTMX private history](https://htmx.org/attributes/hx-history/).
