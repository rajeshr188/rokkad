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

## Customer photos, identity and first-loan guidance

Customer add/edit share `_form_photo.html` and `customer-photo.js`. Camera frames
are bounded to 1280 pixels on the longest side and passed as JPEG files through
the existing multipart ImageField. Local file selection and capture share a preview;
discard restores the saved preview, whose URL uses existing private authorization.
The capture request is generation-guarded against late permission responses and
asynchronous frame callbacks. Tracks stop on cancellation, capture, form submission,
page hiding and navigation. Object URLs are revoked. No new upload endpoint,
storage policy, model, permission or financial service was introduced.

The customer record now exposes address/identity review and an existing `?party=`
loan-draft handoff. Identifier/document auto IDs are distinct, linked errors reuse
the native form partials, and edit controls reflect current permissions. Saved
identity evidence is explicitly separate from verification. Branch setup and the
blocked-draft page explain the next prerequisite; imported records do not imply
new-lending readiness. Loan entry reuses accessible field/error markup, supports
Select2 error focus, offers customer/setup links in another tab to retain draft
inputs, and excludes private form responses from caching/history snapshots.

Validation: 128 Django tests pass across Party UI/private media, loan draft UI,
rate readiness, setup checklist and shared-shell rendering. The photo test creates
and replaces a valid multipart image and verifies that invalid replacement retains
the saved image. Identity checks cover unique IDs/error links and customer handoff.
Six camera JavaScript tests cover capture, cancellation/late permission, selection
races, discard, denied/insecure access and lifecycle cleanup; four existing rate
readiness tests also pass. The 699-file import-boundary check and gettext compilation
pass (four existing catalogue metadata warnings). Private logs and synthetic test
photo are in `outputs/ux-photo-journey-20260922/`.

Browser review used the isolated JCL rehearsal without saving business records.
A synthetic local image produced a preview and discard removed it. Edit exposed
the camera controls and authorized saved-photo URL. Keyboard navigation opened
identity review, then the customer-to-loan link correctly reached the missing-license
guidance and branch checklist. The setup screen was visually inspected at 390px;
the customer form had no horizontal overflow at that width. Browser automation
needed a fresh tab after a stale debugger connection; physical camera capture was
not exercised. Default viewport was restored. Full first-loan approval/disbursal,
remaining Hindi copy, physical camera/mobile and assistive-technology/operator
acceptance are still pending; no whole-product completion or cutover is claimed.

## Loan review, disbursal and printing

The saved draft/approved detail shows customer/date/tenure and a shared native
`_origination_review.html#review` partial before the next action. Its `amounts`
partial presents principal, advance interest, deducted fees and net payment without
template arithmetic. Draft reads call the existing `make_review`; approved reads
call `preview_approved_disbursal`, a read-only wrapper around the command's existing
frozen-economics parser. Missing/reconciling evidence errors are visible; no fallback
invents a net payment. Confirmation remains the existing authoritative command.

The owner review form preserves its signed review token and deliberate payment
checkbox. Both payment forms bind empty POSTs, label the actual payment date, use
accessible native fields/error summaries, and explain that recording payment sends
no bank transfer. Hidden-field errors are plain text rather than links to invisible
controls. The shared financial-action form retains preview/confirm values, action
URLs and reversal guards. Detail and payment reads are private/no-store and excluded
from HTMX history. The approval action remains POST-only with existing authorization;
no model, migration, workflow setting or financial calculation changed.

The new Loan documents card gates ticket links on approval evidence plus non-draft
state, and schedule links on persisted schedules. It keeps existing PDF endpoints,
issuance and reprint behavior, opens documents separately and explains the difference
between approved terms and payment evidence. New copy has compiled Hindi translations;
remaining older loan-detail/action text is not fully translated.

142 focused Django tests pass (55.607s), along with the 699-file import-boundary
check, diff whitespace checks and gettext compilation (four existing metadata
warnings). Run evidence is in `outputs/ux-loan-review-20260922/`.
Validation covers draft preview without approval/events, approved frozen amounts
without resolving current rates, invalid payment recovery, Hindi labels, private
responses and document availability before/after disbursal, alongside existing
stale-owner-review, permission, atomicity/replay, rate and PDF regression tests.
Test-rendered synthetic pages were captured inside a rolled-back test; they were
not admitted to a business workspace. Browser tooling blocked opening those local
HTML fixtures, so no visual acceptance of those fixture pages is claimed.

The separate live read-only browser check used the accepted JCL rehearsal. An
imported active loan displayed its available key-facts schedule without a fabricated
approval ticket; the document card and next action fit a 390px phone viewport with
no horizontal overflow. Default viewport was restored. The older ordinary development
server has a missing `loans_pawncollateralphoto.source_evidence` column; this pre-existing
schema mismatch was not migrated as part of UI work. The rehearsal web server was
restarted using its existing configuration. No production or accepted rehearsal
business record was changed. Full live origination/payment, assistive-technology,
physical device/printer and operator acceptance remain open.

## Collections and full release

`full_release.html` replaces the generic action-page presentation for single-loan
full release. Inline native settlement/collateral partials provide three numbered
sections with an exact dated quote, responsive selected-item list, cash field,
optional concession disclosure and existing physical-handoff checkbox. The template
does no arithmetic. The quote's interest/fees already includes catch-up interest;
the separate component is labelled as included. Quote failures/blockers disable the
button, while the unchanged command revalidates every POST and preserves retries.

Concession input visibility uses the existing `workspace.settings.manage` action
after the existing release access gate; backend concession authority is unchanged.
Submitted invalid fields retain their values/request key and linked errors. Empty
release/repayment POSTs are now bound, and both responses have no-store headers.
The repayment action page explains the difference between recorded-balance repayment
and full settlement and clearly labels its existing non-mutating allocation preview.
The detail page offers an anchor to release history/memos. No service calculation,
posting, model, migration or import evidence changed. Added copy/labels use compiled
Hindi translations; complete legacy-screen translation remains outside this slice.

99 focused tests pass (21.795s), covering loan UI, release concessions and authority,
opening release, repayment allocation, readiness and shell rendering. New checks
exercise empty POSTs, retained request keys, missing concession reason, hidden-field
errors, Hindi labels, unavailable quotes and forged staff concessions without events
or custody changes. The initial run's one failure was an assertion for the replaced
preview heading; its command/no-write assertions remain. Existing replay, atomicity,
settlement and restricted-role evidence tests pass. The 699-file boundary check,
diff checks and gettext compilation pass (four existing catalogue metadata warnings).
Private run evidence is under `outputs/ux-collections-20260922/`.

After restarting the local rehearsal web server with its existing configuration,
read-only Chrome review confirmed the imported-loan quote, selected collateral,
cash/handoff controls and optional concession disclosure. The 390px phone viewport
had no horizontal overflow and was reset afterward. No financial form was submitted,
no release was performed and no accepted migration/custody records changed. Complete
keyboard/screen-reader, real operator collection/handover and physical device/print
acceptance remain pending. Next simplify loan search and the servicing overview.

## Loan search and servicing overview

`pawn_loan_list` now serves a native `list.html#results` partial only for its known
HTMX target; boosted/history/ordinary requests retain a full document. Existing
Workspace access covers both paths. Responses are no-store and vary on all four
representation headers; `hx-history=false` prevents borrower history snapshots.
Search is synchronized, paginated with stable ordering and announced without
moving typing focus. Pagination/explicit search can focus the results. Session
redirects navigate normally, and failures expose retry guidance.

Responsive cards show loan/customer identity, state, date and entry principal.
Entry principal is explicitly the stored value from creation/import: an opening
import can carry forward principal instead of the original advance. No list-level
financial calculator or cross-Workspace count was introduced. Phone search extends
the existing query. The filter form rejects reversed date ranges; any filter error
suppresses results, with correction links that open/focus the advanced controls.
Ordinary GET and pagination links remain available without JavaScript. Staff only
see the new-loan button with `data.create`; services still authorize all writes.

Detail retains visible financial errors, balances and source explanations, while
moving less-used actions into a native disclosure and adding section jump links.
Recommended collection/full release stays prominent. Imported openings omit the
auction shortcut, matching the existing service limitation. Documents retain their
existing approval/schedule rules. No schema, financial command or import changed.
Added labels use the existing Hindi catalogue; legacy detail copy still needs its
remaining bilingual rollout.

Validation: 127 Django tests across `test_pawn_draft_ui`, `test_opening_release`,
`test_party_ui` and `test_shell_render_smoke` (93.191s). One added cross-Workspace
assertion initially saw a pending creation toast from before the fixture changed
Workspace. Consuming that message before the move fixed the fixture; the isolation,
phone/invalid-filter and Hindi tests passed on rerun (3 tests, 1.290s). Four Node
tests cover focus/announcements, session fallback, failed-search recovery and
opening a linked error's disclosure. Gettext compilation, diff checking and the
699-file import-boundary check pass; gettext retains four pre-existing metadata
warnings. Private logs are in `outputs/ux-loan-directory-20260922/`.

Read-only Chrome checks on the accepted rehearsal confirm live filtered results,
typing focus, keyboard activation of filter-error links, imported-action visibility
and no horizontal overflow at 390px/1280px. Desktop pointer activation of the error
link also passed. At the phone viewport, pointer activation did not reliably focus
its field through automation; keyboard activation did.
Physical pointer/touch and screen-reader acceptance remain open, as does complete
operator acceptance. The local server was restarted to refresh cached templates
and gettext. No financial form was submitted and no accepted migration data changed.

## Branch readiness, licenses and numbering

The setup hub uses the existing selector to highlight its first incomplete step;
the view does not introduce another readiness algorithm. The obsolete duplicate
metal-buying review row is removed. Documents/printing remain optional review
tasks, and secondary tools remain accessible through a native disclosure. A card
register fits phone widths and distinguishes legacy references. New-loan entry
retains the `data.create` visibility check; setup authorization is unchanged.

License creation, amendment and renewal share grouped native field/error partials
and the existing multipart POST/services. Labels and help now explain validity,
required evidence and file reselection after errors. Numbering forms separate
identity from prefixes/digits/limits; examples cannot be mistaken for reserved or
allocated numbers. License detail places actual read-only previews before history
and links back to the checklist. Empty POSTs now bind on all five forms. Series
service validation is caught outside the existing atomic service and rendered as
form errors; it cannot leave one counter or the series identity partly updated.
The seven page views use no-store responses and templates opt out of HTMX history.
No new endpoint, model, migration, financial calculation or service rule is added.

127 tests pass (23.723s) across setup UI, license/series services, number allocation,
regulatory evidence, draft UI and shell rendering. Added checks cover next-step
selection, empty submissions, private responses, linked errors, retained input,
Hindi labels and rollback when the release counter rejects a proposed limit after
loan-sequence configuration. Existing authorization, scope, CSRF, document evidence
and preview/no-consumption tests pass. An initial Hindi assertion ran before the
new catalogue was compiled; the final suite passes with compiled translations.
Gettext retains its four existing catalogue-header warnings. The 699-file boundary
check and diff checks pass. Logs: `outputs/ux-branch-setup-20260922/` (private).

Read-only Chrome review on the accepted rehearsal confirms the next-step link,
license form labels/grouping, legacy-reference restrictions, numbering-first detail
and existing series values. License entry, hub and series form have no page overflow
at 390px; desktop series layout was also checked at 1280px. The viewport was reset
and the setup hub left open. No settings or evidence were submitted. Hindi browser,
physical touch, screen reader and actual upload/printing/operator acceptance remain
pending for that slice. Calculation/fee/monitoring follows below; remaining legacy
detail translations, Rates/notifications and cutover acceptance remain separate.

## License continuation and policy guidance (September 22)

Imported-license detail now links to the evidence-backed verification flow described
in [the operator guide](../flows/legacy-license-continuation.md). The form makes
activation explicit, requires final-source and every sequence counter review, and
does not prefill legal validity or claimed source high-water values. It uses native
field/error partials, document-reselection help, no-store and no HTMX history cache.

Calculation/fee/monitoring use separate native disclosures and a shared Django
partial for grouped fields. Scope/date, interest, slab/compound settings, collateral
valuation/rounding, fees and monitoring thresholds are explained independently.
Errors bind only the submitted form, preserve entered values and reopen its section;
monitoring amendments preserve the existing service's immutable version handling.
Navigation progressively opens a linked disclosure; native forms remain usable
without JavaScript. English/Hindi fields and guidance include correctly escaped
template percentage translations and ISO values for native date controls.

Read-only local browser checks cover license verification and policy forms at 390px
and policy forms at 1280px without page overflow. English and Hindi policy rendering,
date values and disclosure navigation were checked; a collapsed-link issue and
Hindi date/percentage issues found in browser review were corrected. The viewport
and English language were restored; the policy page is left open. No business
settings, license evidence or financial forms were submitted in the rehearsal.
Physical touch, assistive-technology and novice-operator acceptance remain pending.

## Rates and notifications (September 22)

Rates forms replace crispy layouts with native grouped field/error partials. Source,
metal, prices per gram and effective time have English/Hindi labels and explanations.
Corrections and withdrawals still append service evidence. Source entry returns to
its detail with the next quote action, avoiding a stale source select in another tab.

Rates and Notify batch directories use 25-record pages, validated search/select
filters, stable ordering and phone-friendly cards. Invalid filters return linked
errors with no rows. Normal GET links/forms work without JavaScript. HTMX uses
`reference-results`, strict response markers, full-page history/boost fallbacks,
no-store/Vary headers and excluded history snapshots. A shared small script
announces results, manages busy/error states and focuses the result/error heading.
Browser review found and corrected the submit-event focus detection.

Notification detail separates recipient documents, digital sending and print/post
records; edit/export controls match existing permissions. Only eligible digital
jobs contribute to the send count. Settings puts connection readiness before
administration/diagnostics and does not claim delivery. WhatsApp setup groups
connection, callback secrets and enablement; errors link to fields and secrets
are never echoed. Empty setup/withdrawal POSTs now receive normal validation.

Validation: 82 Rates/Notify tests on a fresh database, then 33 targeted tests after
final refinements, all passed. Explicit module labels avoid the two namespace apps'
same-named `test_rls` discovery collision. Existing restricted-role isolation,
immutable quote and mocked delivery tests pass; new integration tests exercise
filters/paging, escaping, full/fragment responses, Hindi forms, empty submissions
and GET review without dispatch. Gettext compilation and supported-app boundaries
pass. Private logs: `outputs/ux-rates-notifications-20260922/`.

Local Chrome review used the accepted rehearsal without business POSTs. Empty
directories, rate entry and WhatsApp setup were reviewed in English/Hindi at 390px
and/or 1280px; checked pages had no horizontal overflow. Native datetime values
remain ISO in Hindi, password controls remain empty, and live Rates search moves
focus and announces results. English and the normal viewport were restored, with
the notifications directory left open. Populated quote/batch pages and pagination
are server-test coverage, not live operator acceptance. Physical touch, screen
reader, real provider callbacks, populated browser review and staff acceptance are
still pending. Shared shell/admin labels and technical provider errors may remain
English; this slice does not declare translation or whole-product completion.

## Owner/team setup and navigation (September 22)

Business profile becomes a small hub for setup, team and billing. Native grouped
forms cover creation/editing, invitations and role changes, with linked errors,
CSRF, explicit save/submit actions and excluded HTMX history. Role changes use
the actor's permitted choices and the existing audited service. Owner/self
controls remain guarded; team removal and invitation revocation disclose their
consequence before the existing POST action. The seat summary uses the actual
capacity snapshot fields. Editing a profile now binds request.FILES for logos.
Management views receive no-store headers. No domain policies or database schema
changed.

Shared navigation and setup labels now have Hindi translations. Custom workspace
and role names remain stored values. Dynamic rate-availability descriptions,
some page titles and deeper administration/provider errors remain English.

Validation: 195 organization/onboarding tests passed. Final owner/team and shared
shell checks passed all 29 tests on a fresh database after browser refinements.
Tests cover permitted role choices, invalid submissions without mutation,
audited-service delegation, owner restrictions, logo binding, seat numbers,
escaping, Hindi rendering and no-store behavior. Existing shell assertions were
updated for the current navigation and stylesheet rather than stale markup.
Browser review caught a replaced Select widget losing its choices; the native
widget is now declared on the field and an option assertion prevents recurrence.
Private logs are in `outputs/ux-owner-team-20260922/`.

Read-only Chrome review covered team and invitations at 390px, business profile
at phone width, profile editing and setup guidance at 1280px, English/Hindi
labels, the native role options and Hindi mobile navigation. Checked screens had
no horizontal overflow. Percentage guidance renders single percent signs. No
invitations, member changes or business-profile forms were submitted against the
accepted rehearsal. English and the default viewport were restored, with the team
preview retained. Populated member actions and logo binding have isolated server
test coverage; real email delivery, physical touch, screen-reader and staff task
acceptance remain separate pre-cutover checks.

## Collateral upload failure recovery (September 22)

The first manual JCL loan attempt exposed a transport error during the R2 photo
write. The atomic draft command already rolled back its database work, but the
provider exception escaped to Django's debug page. Collateral media now translates
SDK/filesystem failures into its existing domain error, so normal create/edit
adapters re-render bound fields and photo-reselection guidance. Provider URLs and
details are excluded from form errors. Cleanup failures are logged with the
unreferenced object name and do not mask the original failure; this does not claim
transactional rollback of remote storage or automatic orphan reconciliation.

The explicit rehearsal/production R2 configurations retain HTTPS verification and
use standard retries with two total attempts, 5-second connect and 15-second read
timeouts. These bound individual network operations, not the total multi-photo
form duration. See [Botocore configuration](https://docs.aws.amazon.com/botocore/latest/reference/config.html)
for timeout and total-attempt semantics. No extra application retry loop or TLS
bypass was introduced.

Actual R2 upload/readback succeeded with small and 2.1 MB synthetic images. The
full Django form path succeeded against the rehearsal storage, hash-verified its
photo, and then rolled back its diagnostic database rows and removed its own
object. Another probe timed out and returned the new form error. Connectivity is
therefore intermittent; a successful probe is not an availability guarantee.
Rehearsal remains on the restricted database role and the new server process
serves the normal loan form. The failed manual draft did not consume its number.

All 109 draft UI/service, collateral media and deployment checks passed on a fresh
database, including create retry, edit rollback and secondary cleanup failures.
Gettext compilation and supported-app import boundaries pass. These checks do not
claim uninterrupted network availability or completion of the staff walkthrough.
