---
status: accepted
owner: project
updated: 2026-10-17
tags: [loans, closing, contracts, custody]
related: [2026-10-08-unified-closing-and-completed-recording.md, ../flows/multiple-loan-release.md]
---

# Explicit closing mode and shared saved-contract checks

The owner approved one coherent closing flow after a saved started-week agreement
worked in current release but failed the completed-closure monthly-contract gate.
This refines the [8 October decision](2026-10-08-unified-closing-and-completed-recording.md):
origination preferences and current-recording commitments no longer choose a
closing mode implicitly. Optional owner restrictions still govern permission to
record completed activity; they do not establish when a settlement happened.

Use **Close / release loans** from the Loans list, closing history, or the prominent
**Close / release loan** action on an authorized active loan. Select one or several
loans, then explicitly choose current collection/return or recording a completed
settlement. Selecting a different mode or group starts a fresh review. Recording
completed activity requires an actual date, with no initial date filled in by the
shared screen. Entry source is not a closing-mode or financial-rule selector.

Current single release retains its existing concession and request-key contract.
Current multiple release retains one combined payment and per-loan collectors,
signed quote, sorted locks and atomic completion. Completed single and multiple
entry use the same existing independent-settlement batch adapter and actual-date
review. Their total is reconciliation, not a new collection. No new batch mode,
financial engine, table, migration or portability profile is introduced.

Full settlement uses the existing canonical date-aware release calculator for
every supported saved agreement. The completed monthly receipt/renewal gate does
not apply to full release. Unsupported calculations still fail in the canonical
quote/writer; original policies, opening limits, later activity/accrual/custody,
source review, permissions, RLS and optional recording restrictions remain enforced.
In particular, started-week interest is calculated from the saved agreement; it is
never converted to full-month interest to make completed closing possible.

Financial settlement without established customer handover retains PAPER_CLOSED
and last-known storage. Confirmed earlier returns retain their actual day without
inventing a time. Already-issued single and multiple forms retain their original
posting, evidence, signature and retry meanings. Existing records are not rewritten.
The owner explicitly left JSK WH02306 unchanged; this decision authorizes workflow
implementation, not a correction of that loan or another production transaction.
