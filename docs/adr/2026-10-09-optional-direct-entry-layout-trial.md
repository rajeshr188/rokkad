---
status: accepted
owner: project
updated: 2026-10-09
tags: [loans, presentation, direct-entry, trial]
related: [2026-10-07-shared-loan-entry-and-explicit-origination-correction.md, ../implementation/shared-routine-loan-editor-lo02.md]
---

# Optional direct-entry layout trial

The owner accepts simplifying direct New loan entry but requests retaining the
familiar interface for existing staff and choosing which layout to retire later.

Keep Current as the default and offer Simplified (trial) at the same New loan
route. This is a presentation choice, independent of direct/paper origination,
workspace workflow, product, permissions and financial policy. Remember the choice
in the authenticated browser session under both Workspace and user identity; do
not introduce a Workspace-wide rollout setting or persistent preference model.

Both layouts use the same bound forms/formsets, submission identity, financial
commands and shared payout review. A layout change is an explicit nonfinancial
action: it preserves the current entry purpose and entered facts, saves no draft,
consumes no number and does not approve or pay. Enhanced switching retains actual
File inputs locally. Without JavaScript, native Apply layout preserves ordinary
fields but truthfully requires photograph reselection after the page reload.

The simplified view groups routine item facts, collapses permitted rate exceptions,
shows numbering beside series, and offers compact product/date/tenure controls.
Required appraisals remain visible according to the selected valuation method;
unknown setup exposes the controls rather than assuming appraisal is unnecessary.
Existing entered values and errors expose the relevant exceptions. A missing
standing tenure is disclosed; the legacy field fallback is not presented as a
configured agreement. Available standing tenure is guidance when an entered tenure
differs; switching layouts must not silently replace the entered agreement.

Existing calculation, appraisal suggestions, valuation/LTV, photo requirements,
authorization, frozen review, exact retry and posting rules remain. Do not maintain
two financial implementations or silently retire either layout. Evaluate the trial
with staff before a separate owner decision on default or retirement. Production
rollout remains a separate release task.

## Owner acceptance and retirement (9 October)

The owner evaluates the trial, accepts the simplified layout and explicitly asks
to keep it and remove Current and the switcher. This supersedes the dual-layout
and session-preference decision above. Routine direct New loan now always uses
the accepted compact editor; there is no layout choice, preference writer or
legacy direct layout branch. Existing session values and layout query parameters
cannot restore Current. Saved-draft editing and shared payout review remain as
before; their shared field rendering is not an alternative New loan layout.

Already-open trial `layout_change` submissions remain nonfinancial, preserve
their current purpose and facts, and render the accepted editor. This small
compatibility guard avoids interpreting an old presentation request as a draft
save. Origination-purpose selection remains independent and available. Financial
forms, commands, authorization, frozen agreements and retry contracts do not
change. Production rollout remains separate.
