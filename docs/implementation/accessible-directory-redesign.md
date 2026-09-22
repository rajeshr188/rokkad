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


## Customer entry and introduction

The second slice covers customer creation/editing and the onboarding introduction.
The Party form starts with name, record type, contact, relation and optional photo.
More details retains code/legal/tax/risk/status/credit-hold controls; it opens on
edit or a failed submission. No field, default, authorization gate or save service
was removed. The former duplicate live summary is replaced by a short explanation
of the next step: save, then add addresses/identity evidence on the customer record.

`components/forms/accessible.html#field` and `#errors` are native template partials.
Labels, required markers, help/error associations, grouped choices and linked
errors share markup. The error summary receives focus; selecting an error opens
any containing disclosure and focuses the control. Browser JavaScript is not
required to submit or validate. Text survives invalid submissions; files require
reselection. Empty POSTs now bind the form rather than appearing as a new GET.
Borrower entry pages disable HTMX history snapshots and have no-store responses.

The onboarding shell identifies progress as account introduction, names the
current step, and links existing operators to their Workspaces. The quick guide
explains finding a customer, preparing/reviewing a loan and returning for service.
Preferences remain optional and preserve their existing stored keys/history;
completion redirects and lending/access checks are unchanged. There is no new
permission, lending-readiness calculation or automatic Workspace selection.
The flow document now describes shared-schema RLS instead of schema/DEA seeds.

Customer form/help/errors and quick-guide copy use gettext with Hindi entries.
The existing Email translation incorrectly meant postal address and is corrected.
The unchanged profile/company/team form bodies and wider setup/detail screens are
not yet fully translated or redesigned. Language changes reload an unsaved form;
choose the language before entry. No cross-language draft persistence is claimed.

Validation: 78 focused tests pass (35.960s), covering Party UI/private media,
onboarding preferences/completion/company/team and the shared shell. Five new
checks cover invalid/empty POST recovery, input escaping and retention, Hindi
editing with credit-hold/status preserved, introduction/readiness distinction and
Hindi preference errors without progress or permission changes. The 699-file
import-boundary check and gettext compilation pass; gettext retains four existing
catalogue metadata warnings. This is not a whole-repository test result.

Browser review on the isolated local rehearsal confirms the desktop customer form,
English invalid-phone recovery and linked focus, Hindi labels/required errors and
error-summary focus. Phone (390px) and tablet (820px) layouts have no horizontal
overflow; tablet help moves below the wider form. English and the default viewport
are restored. Only invalid customer submissions were made; no customer, loan,
financial event or source evidence was created/edited. Onboarding is covered by
server-render/behavior tests; its complete signed-in browser journey and physical
phone/photo/screen-reader/operator acceptance remain pending. Private run evidence
is in `outputs/ux-customer-entry-20260922/`.

Next connect the actual branch-readiness guidance and customer detail/KYC journey
to the redesigned first-loan flow, then collections/full release. Do not treat this
introductory guide as completion of operational onboarding or the wider redesign.
