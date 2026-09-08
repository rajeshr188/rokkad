---
status: proposed
owner: project
updated: 2026-09-08
tags: [ux, ui, product, roadmap]
related: [active.md, ../implementation/browser-acceptance.md, ../STATUS.md]
---

# Project-wide UI/UX revamp

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

No calendar estimate is set until the screen inventory and prototype scope are
agreed. The recommended next UX deliverable is the first-loan prototype, not a
simultaneous rewrite of every page.
