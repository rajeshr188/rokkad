---
status: active
owner: project
updated: 2026-09-22
tags: [ui, accessibility, htmx, party, hindi]
---

# Redesign foundation and customer directory

This is the first implemented slice of the
[pre-cutover redesign](../plans/project-wide-ux-revamp.md), using the owner's
[chosen stack](../adr/2026-09-22-native-template-partials-ui.md). It is not completion
of the whole application redesign or a WCAG conformance claim.

The shared base now uses Bootstrap 5.3.8 with integrity hashes, the active language
on the document, a keyboard skip link and one main landmark on Workspace pages.
Language selection requires explicit submission, retains the current path, and
preserves directory filters after partial navigation.

The customer/Party directory replaces the wide table with a responsive record list.
Name, relation, code, contact and textual status remain visible. Create/edit links
follow the existing Party permissions. Administrative import/export actions are
secondary; filtered exports retain the server result's filter set.

Search and filters use the existing authorized queryset. `party/list.html#results`
is a Django native partial; full GET pages still work without JavaScript. HTMX
updates results and the URL without replacing the search field, cancels superseded
requests, announces totals and moves focus after pagination. Normal pagination
uses Django's querystring encoding. Session redirects become full navigation;
errors preserve the inputs and offer retry. Private responses are no-store and
vary by HTMX representation headers; history snapshots are disabled for the page.

New directory/help/error strings have Hindi translations. Customer names and
configured role labels remain source data. Compiling the existing catalogue also
required fixing two misspelled PO keywords, duplicate definitions and a missing
password-reset format placeholder. Duplicate entries retain the first translation.
The catalogue is now checked with gettext; existing untranslated/fuzzy strings
outside this slice remain part of the wider bilingual audit.

## Validation and limits

The final Party UI/private-media and shared-shell suite passes 63 tests, including six added
checks for partial filtering, full-document history/boost fallbacks, authorization,
anonymous access, Hindi and encoded pagination. The combined shell/Party run has
64 passes and four failures. Those four management-shell expectations also fail
with the original HEAD templates: old accent bar, navigation counts and retired
management links. No full-suite success is claimed.

Local browser review confirms partial search/focus, result announcements,
pagination focus, Back restoration, empty-state recovery and English/Hindi switching
with filters retained. At 390px phone and 820px tablet widths the directory has no
horizontal page overflow. Local browser review uses the isolated migration rehearsal. It creates no customers,
loans, imports or financial events. Physical device, assistive-technology, complete
keyboard and whole-application bilingual acceptance are still pending.
The mobile menu receives focus, closing it returns focus to its toggle, and the
keyboard skip link focuses the content past navigation. Private execution evidence
is in `outputs/ux-foundation-20260922/`.

Next apply these patterns to the first-day setup/onboarding journey and customer
creation, then the loan and release workflows. Keep current domain services and
source evidence unchanged. No production deployment or cutover occurred.
