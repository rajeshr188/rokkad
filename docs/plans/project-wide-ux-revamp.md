---
status: active
owner: project
updated: 2026-09-22
tags: [ux, ui, product, roadmap]
related: [active.md, ../implementation/browser-acceptance.md, ../STATUS.md]
---

# Project-wide UI/UX revamp

## Current priority: redesign before production cutover (September 22)

The owner requested a thorough UI/UX and user-flow redesign for accessibility,
ease of use and onboarding **before cutover**. Staff use desktop, tablet and phone;
the required interface languages are **English and Hindi**. This is the next product
workstream. The old Linode production app stays live. Preserve the accepted data
and media rehearsal; take a fresh final snapshot only after the redesigned flows
and production readiness are accepted. Server procurement can wait until a hosted
review or timed deployment rehearsal is needed.

Build on the existing counter-focused shell and ordinary Django/Bootstrap stack.
Evaluate complete tasks with novice users moving from paper registers. A visual
refresh alone does not satisfy this request. Existing approvals establish a useful
baseline, not acceptance of all current flows or a reason to skip accessibility.

### Audit and delivery sequence

Implementation has started with the owner's selected Django native partials,
HTMX and Bootstrap 5.3.8. The [first directory slice](../implementation/accessible-directory-redesign.md)
provides the progressive full-page/fragment, responsive and bilingual baseline.
Customer creation/editing and the onboarding quick guide now use the same field,
error-recovery and bilingual patterns. Camera/photo preview now works through the
existing customer create/edit forms. Branch-readiness guidance, identity form
accessibility and the customer-to-loan draft handoff are implemented. Single-loan
collections/full-release guidance now follows the same field/error patterns, with
explicit settlement, custody and concession boundaries. Next simplify the loan
directory and servicing overview for daily counter work. Terms review, payment-form accessibility and grouped
printing guidance now extend the first-loan journey; its complete live payment
walkthrough and physical printing remain pending. Detailed setup forms, remaining translations and physical-device/operator
acceptance remain open; these slices do not complete the whole-product redesign.

1. Inventory live routes and actual owner/staff journeys using isolated data.
   Record concrete friction with route, role, device, language, task, observed
   behavior and proposed fix. Include successful paths, invalid inputs, missing
   setup, empty data, denied access, interruptions and retry recovery. Separate
   observed failures from hypotheses; do not report a source-only audit as browser
   or assistive-technology acceptance.
2. Define the shared navigation, terminology, form/error patterns and English/Hindi
   language behavior. Put daily counter work first and owner administration behind
   its existing permissions. Keep the active branch visible. Prototype onboarding
   through the first loan and a returning customer's release at desktop and phone
   sizes before spreading new patterns across screens.
3. Implement the first complete journey: sign in/join branch, see the next required
   setup action, find or add a customer, enter collateral/photos, review server
   calculations, approve/disburse and print. Keep optional detail available without
   asking new users to understand every policy screen first.
4. Extend the tested patterns to daily search, customer/loan details, interest and
   elapsed-period explanations, supported collections/full release, item handoff,
   reversals, closed history, custody, Rates and notifications. Import/export review
   needs plain errors and outcomes; a new legacy Migration Center is not required.
5. Complete owner setup, team/access, account recovery, billing, documents and
   settings. Separate owner onboarding from an invited staff member's introduction
   and from a migrated branch resuming work. Do not force migrated users to create
   another Workspace or repeat import setup.
6. Run accessibility and task-based acceptance in both languages on desktop,
   tablet and phone. Then rerun migration, financial and isolation regression checks
   against the release before the final timed cutover rehearsal.

### Acceptance conditions

- Target WCAG 2.2 AA for the redesigned journeys, with automated checks plus manual
  keyboard, focus order/visibility, screen-reader, zoom/reflow, contrast and touch
  testing. A passing automated scan is not a conformance claim. Use the
  [W3C reference](https://www.w3.org/WAI/WCAG22/quickref/) for the exact criteria.
- Every field has a useful label; errors explain how to recover and link to the
  affected field. Preserve valid input and make browser-required file reselection
  clear. Loading, success and error states are perceivable without relying on color.
- English/Hindi selection persists appropriately, sets the page language, and
  covers navigation, onboarding, help, validation, status and action labels. Test
  Hindi text expansion, fonts and screen-reader pronunciation. Do not translate
  customer names/source evidence or silently change dates, amounts or identifiers.
  Review terminology with branch operators; translation is not just a language menu.
- Desktop workflows support keyboard operation; touch layouts do not depend on
  hover, hide the primary action or require navigating a wide desktop table.
  Test physical Android/tablet photo upload and actual receipt printing before
  release; simulated devices do not establish hardware acceptance.
- First-time operators can find an existing customer, create a supported loan,
  explain the displayed interest period, complete a full release and find its
  receipt without developer guidance. Record completion, assistance, errors and
  time against the current baseline; resolve critical task blockers before cutover.
- Setup completion reflects actual lending prerequisites. Account creation, an
  optional tour and Workspace creation must not imply readiness to lend.
- Keep existing authorization, RLS, immutable evidence, idempotency and financial
  services. Backend readiness rules remain authoritative. Do not present ordinary
  partial repayment on imported openings as supported or change money calculations
  merely to simplify a screen.

### Initial source review (not a completed live UX audit)

| Evidence | Finding / next verification |
| --- | --- |
| `templates/components/navigation/sidebar.html` | Daily actions and branch scope already exist; labels include Parties. Test customer-facing terminology with English/Hindi operators before renaming a shared domain concept. |
| `templates/onboarding/step_tour.html`, `apps/onboarding/views.py` | Feature Tour currently collects preferences. Align the promised learning experience with the actual task and distinguish it from lending setup. |
| `apps/onboarding/views.py:onboarding_complete` | The active completion route redirects to setup/list. The celebratory `complete.html` is not proof of the live completion journey; trace routes in the audit. |
| `docs/flows/workspace-onboarding.md` | Still describes tenant schemas and retired DEA seeds. Replace after tracing current services; do not use this obsolete description as the redesign contract. |
| September counter implementation | Shared shell and some desktop/mobile checks exist; complete keyboard, screen-reader, Hindi and physical device acceptance are not established. |

## Previous design checkpoint (September 8)

The user approved the counter-first visual direction and asked to implement the
shared navigation and loan workflow, with more collateral detail in the summary.
Implementation is now underway in ordinary Django templates and Bootstrap.
The first slice applies the shared Workspace presentation and navigation, live
draft summary, and persisted summaries through loan detail and financial/release
actions. The next slice now extends Party records/KYC navigation, Rates quote
and source screens, and Notify delivery/settings screens. Team, billing, account,
and setup screens now use the shared design after operator approval. Management
navigation is grouped by Workspace, Team, Configuration, Billing, and Account;
loan setup separates configuration, documents/printing, and operations/custody.

The counter-first [interactive prototype](../ui/prototypes/counter/index.html)
and [walkthrough](../ui/prototypes/counter/README.md) remain the design reference.
The functional checkpoint is committed as `9acb865` with 802 tests passing.
Prototype browser checks pass at desktop and narrow widths. The sample sequence
and visual direction are accepted for the shared shell and first-loan vertical
slice. Reference/setup screens currently demonstrate navigation and
layout only; their full workflows belong to later slices.

## When to start

Start the UX audit and design brief now. Start implementation as the next product
workstream after the current Notify application-boundary fixes pass their tests
and the existing work is reviewed as a coherent checkpoint. Do not wait for every
future lending variant or notification-provider pilot to finish.

Physical phone/camera and printer acceptance are deferred by the operator. They
remain pilot/release checks and do not block design work. Production private-media
serving must also be verified before a real-data pilot; this is separate from
whether we can improve screens on isolated data.

These are dependency milestones, not calendar promises. The first milestone is
the current boundary checkpoint; the next is a reviewed first-loan prototype.
The user's request asks for timing and a recommendation. This brief does not
start a project-wide visual rewrite or choose an unreviewed visual identity.

## Why the project needs it

The application has a tested functional lending path, but recent acceptance
found interaction problems that ordinary server tests missed: borrower search
lost Workspace context and an extra collateral row blocked one-item drafts.
The fixes establish the baseline; the redesign should make that path easier
to understand and less error-prone.

Observed screen issues for the UX audit:

- Lending screens use technical names such as "PawnLoan" and present many
  economic and administrative details together.
- Validation errors remain visible while fields are corrected until the next
  submission; the next prototype should make error recovery clearer.
- The mobile release screen is usable but long. It should emphasize amount
  collection and item handoff while keeping evidence accessible.
- Notify configuration mixes operational settings with staff-only administration.
- Navigation, action placement, tables, empty states, and setup guidance need
  a consistent treatment across the supported apps.

Confirmed preference (September 8): prioritize a staff member serving borrowers
at the counter. Review the task sequence with the user before locking the
prototype. Existing screenshots and isolated acceptance data
are the starting evidence, not a substitute for operator feedback.

## Delivery order

1. **Audit and shared patterns.** Inventory global/account and Workspace screens.
   Define navigation, page headings, typography, spacing, form fields, tables,
   empty/error/loading states, primary actions, and responsive behavior. Keep
   ordinary Django templates and existing Bootstrap unless a concrete need
   justifies changing them.
2. **First-loan prototype.** Show Workspace selection/setup, borrower search and
   creation, collateral entry/photo, terms review, approval/disbursal, repayment,
   and release. Review the sequence and one desktop/mobile visual direction
   before applying it across the project.
3. **First vertical slice.** Implement the reviewed shared shell and first-loan
   journey. Preserve the passing HTTP/browser workflows, permission boundaries,
   immutable evidence, financial calculations, and duplicate-submission guards.
4. **Project-wide rollout.** Apply the proven patterns to Party detail/KYC,
   Rates, Notify, then team, billing, account, and remaining setup screens.
   Global marketing/auth pages should share the visual language while keeping
   their distinct navigation and purpose.
5. **Operator polish and release.** Check keyboard/focus behavior, accessible
   labels/contrast, mobile devices, camera permission paths, printer output,
   and real operational observations. Revise based on findings.

Party, Loans, Notify v2, and Rates are the supported business apps. The revamp
must not revive retired Girvi, Contact, DEA/accounting, or inventory modules.

## First slice acceptance

- An operator can identify the active Workspace and the next valid action.
- Setup explains the prerequisites needed to create the first loan.
- Borrower search, row add/remove, validation recovery, and photo fallback work.
- Settlement shows a clear amount and explicit item-handoff confirmation.
- Core pages work at desktop/mobile widths and with keyboard navigation.
- Existing access, isolation, money/evidence, and browser regression checks pass.
- Secondary details remain available without overwhelming the primary task.

The first-loan prototype is approved and implemented locally. Review the live
administration and setup slice next, then refine labels, ordering, and
frequent-task shortcuts from operator feedback. Physical acceptance remains deferred.
