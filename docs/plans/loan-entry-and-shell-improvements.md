---
status: completed
owner: project
updated: 2026-09-28
tags: [loans, usability, photos, navigation]
---

# Loan entry and shared shell improvements

The owner requests optional-by-default collateral photos, borrower outstanding
on new-loan selection, contextual LTV guidance after appraisal, and a compact
modern header/footer retaining the current colours and logo. They selected
mandatory-photo enforcement at approval, while allowing drafts without photos.

## Implementation boundaries

- One Workspace photo rule, editable by setup administrators and audited.
  Optional is the default. Mandatory means each collateral item needs a usable
  photograph at approval. Freeze the rule with approval evidence; existing
  approvals and issued PDFs remain intact. Apply consistently to renewals and
  missing-photo ticket output. Preserve photo-to-item mapping when only some
  draft rows have photographs.
- Borrower selection shows all active-loan recorded principal, interest, fees,
  total, loan count and a details link within the current Workspace. It is
  information, not a credit-limit gate or a settlement quote. Missing balances
  must be visible as unavailable rather than reported as zero. Stale responses
  must not show the preceding borrower's balance.
- Per-item valuation guidance follows valid gross/net/purity inputs, the actual
  series/licence/date policy and the current entered appraisal. Display the
  configured LTV percentage, eligible valuation and maximum principal. Refresh
  on input/policy-scope changes without overwriting staff-entered principal.
  Missing/stale quote evidence must not look like approval to lend.
- Use a compact shared header with a prominent Workspace switcher, account menu
  and accessible language controls. Replace placeholder social links and the
  oversized footer with a quiet copyright/help/privacy/terms row. Preserve
  mobile navigation, permission controls, keyboard access and form state.

## Recommendations

Keep the borrower total labelled as recorded outstanding, separate from projected
interest. Treat the per-item maximum as a suggested ceiling, not an automatically
filled loan amount. Start with one Workspace photo rule rather than per-series,
per-metal or per-user exceptions. Retain the existing brand and navigation paths;
make visual improvements in spacing, typography and hierarchy.

## Acceptance

Validate optional/mandatory approval and renewal, partially photographed rows,
ticket generation, cross-Workspace denial, all-loan balance totals, appraisal
edits, missing quotes, stale browser responses and mobile/desktop shell layouts.
Deploy only the reviewed increment, excluding unrelated recurring-billing work.

## Delivery

Completed and deployed on 28 September 2026 as
`rokkad:loan-entry-20260928-1b7e30d10d45`. The 254-test acceptance suite passed;
the final saved-loan photo wording passed the 21-test media suite. Browser review
covered desktop and 390px mobile, and JavaScript tests covered overlapping borrower
responses, clearing selection and failed reads. Production read-only checks in
all three workspaces confirmed optional defaults, borrower totals and LTV guidance.
See [Status](../STATUS.md) for deployment and verification evidence.

The owner subsequently approved a visual organisation pass preserving the form.
Delivered as `rokkad:loan-form-20260928-645aa7320997`: collapsed process guidance,
customer creation beside its field, the photo rule beside collateral, and compact
price status with expandable details and Recheck. Actionable price/policy/date
problems expand automatically. All 92 focused Django and seven JavaScript tests
passed, plus desktop/mobile and production read-only checks.
