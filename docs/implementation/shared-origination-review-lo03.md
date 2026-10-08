---
status: implemented
owner: project
updated: 2026-10-08
tags: [loans, origination, review, verification]
related: [../plans/loan-origination-completion.md]
---

# LO-03: shared origination review and confirmation

On 8 October routine paper review becomes a separate visible step at the same
ordinary New loan route. The editor remains populated but hidden during review;
Edit details restores it and removes the signed review, requiring a new preview.
The server's nonfinancial edit action provides the same fallback without JavaScript.
Direct review and specialized archive/saved-draft admission keep their existing
commands. Simple entry collapses transaction/evidence explanations; recorded later
transactions open them for review.

The existing entry-presentation replacement retains actual File inputs for paper
preview responses; confirmation remains an ordinary multipart financial POST.
DOMParser's noscript elements are removed from enhanced replacements so fallback
file inputs cannot take the retained file out of the editor. Without JavaScript,
unique-ID review file controls allow same-file reselection. Old signed-photo checks
continue rejecting missing/changed files. Failed or edited-during-load previews
preserve current inputs; reviewed facts are not automatically refreshed.


## Staff behavior

In SIMPLE owner mode, **Review loan** on the shared New loan editor saves one
numbered draft and goes directly to its review. It creates no debt. The common
summary shows customer, series/number, actual loan date, tenure, individual item
principals/rates, monthly interest, advance deduction, deducted fees and proceeds.
**Confirm payout** requires deliberate payment confirmation and uses the existing
atomic approval/payout command. **Save draft** remains available to stop before
payment; saved drafts retain their review action. EXTENDED and non-owner preparation
retain their separate responsibilities and permissions.

Paper entry uses the same summary followed by original source, any known receipts
or closure, completeness, custody, counters and current selected photographs.
**Record completed payout** records supported actual history without approving or
paying again. Original proceeds are labelled separately from confirmed cash. Saved
draft recording, explicit LO-01 correction and archive preparation reuse this
review fragment; retained-native reviews use the shared agreement layout while
keeping their genuine historical evidence and narrower checks.

Repeated creation forms open the same saved draft or active loan. They do not
apply changed facts; the message directs edits to Correct draft. Keyboard Enter
selects the primary action rather than the entry-choice control. Explicit purpose
changes still save nothing, and a no-JavaScript Apply entry choice remains.

## Commands, evidence and compatibility

No new loan model, finance engine, workflow framework or permission is introduced.
`origination_summary` formats native resolved amounts and paper amounts using the
recorded writer's existing validator/item rounding. Calculations stay out of views
and templates. The presentation context is outside the signed paper review, so
its v1 structure, previously issued tokens and accepted writer/retry semantics
remain unchanged. Legacy native/historical routes also remain callable.

New SIMPLE web reviews keep the existing signing salt and v1 input fingerprint,
adding version 2 binding to owner, reviewed payout date, complete resolved contract
and photo requirement. Confirmation compares the entire frozen collateral economic
contract and quote identities, rather than only four totals. Approval retains the
server-created combined-review proof in its existing immutable JSON payload. An
active retry must match the proof on the current unreversed payout's approval;
a different or superseded review cannot pass as a successful confirmation.
Previously issued v1 tokens retain their original validation contract.

Failure during approval, revalidation or payout rolls back the approval, appraisal
and financial effects together. Review/draft preparation is not an issued loan.
Current-lending quote rules remain prospective; ordinary completed recording does
not require original-day digital quotes. Printed copies continue to use immutable
origination sources and distinguish original business dates from recording time.

## Verification and release boundary

Verification results are recorded in [Status](../STATUS.md). The new confirmation
tests cover draft-to-review-to-final HTTP flow, duplicate creation/final submission,
atomic rollback, changed input/photo policy, owner/date/loan/Workspace binding,
full-contract comparison, superseded active retry, invalid/expired review, v1
compatibility, native/paper PDF truth and exact database/media recovery of the
new proof. Adjacent suites cover existing direct UI, quotes, retained-native
reviews, paper item/history entry, saved/corrected origins, archive/terminal
preparation, documents and offline recovery.

Chromium checks use actual Django-rendered fictional pages at desktop/mobile sizes;
financial commands are separately exercised through Django HTTP tests. Checks cover
both agreement layouts and confirmation controls, stale paper-review removal,
keyboard review submission and no page overflow/errors. Browser screenshots and
logs are ignored local QA artifacts, not business acceptance evidence.

LO-04 servicing/monitoring equivalence and LO-05/06 real source, media/capacity and
release work remain under the completion plan. No migration, production correction
or deployment was performed by LO-03.
