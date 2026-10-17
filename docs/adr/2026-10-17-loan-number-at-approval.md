---
status: accepted
owner: project
updated: 2026-10-17
tags: [loans, numbering, origination]
related: [2026-10-17-origination-review-and-safe-recovery.md, ../implementation/loan-numbering-stage-proposal-20261017.md]
---

# Assign new direct loan numbers at first agreement approval

The owner approved delayed numbering after confirming that staff use official
numbers externally only after payout. Unapproved preparations need a stable
reference and ordinary scope correction, without consuming
the official register counter.

New direct PawnLoan preparations have a null loan_number. Their existing local
identity supplies the clearly labelled `Draft #<id>` reference, not another
counter or an official number. Only DRAFT and CANCELLED may be unnumbered.
First approval assigns the permanent number through the existing row-locked
allocator in the same transaction as the frozen approval. SIMPLE approval/payout
is atomic; EXTENDED approval assigns before its separate payout. Approval order
may differ from draft creation, actual date and payout order. Cancellation keeps
issued numbers; reopening/reapproval never reallocates. Database guards prevent
changing an issued number or its register/product, even after reopening.

Existing numbers, paper original-number claims, historical reservations and
independent release sequences remain unchanged. A numbered wrong-register draft
uses linked replacement/cancellation retaining the original. Its replacement and
split preparations are unnumbered until approval. The old in-place expired licence
transfer cannot renumber an issued identity; it requires the linked replacement.

Preserve the existing exception for an unused generated opening-import alias:
its verified immutable source evidence may establish the original paper number
before servicing or official document/label issue. A generated alias is not an
externally issued register number. The database guard checks that exact alias,
source profile/number, sole opening event and absence of issued evidence; it is
not a general renumbering permission. The existing authorized service and audit
remain responsible for adoption and collision/future-range checks.

An unnumbered, unconnected preparation can change register/product through the
ordinary draft command after Workspace, authority, product/date/tenure and
economic checks. Retain before/after preparation audit and invalidate prior
reviews. Connected money, approval, funding or physical evidence cannot use this
shortcut. Drafts cannot print loan tickets or draft PDF previews. Ticket printing
starts at approval with the permanent number, including before payout. Reopened
drafts cannot print tickets. Existing issued documents remain immutable.

The existing signed submission/review and outcome proofs remain authoritative.
Approval changes the number only after review validation, so it cannot invalidate
its own confirmation. Retained numbered reviews still validate the original
shape. Split/replacement previews bind the new numbering rule; stale old previews
need review again, while completed retries return their retained outcome.
Actual cash movement still needs its existing recovery/evidence workflow.

Loans 0094 changes nullability and guards without backfilling or renumbering any
loan. Exact native recovery remains schema-bound and includes unnumbered drafts;
financial servicing exports still require issued operational agreements. Downgrade
is rejected while unnumbered preparations exist, rather than inventing numbers.
No production correction, setup mutation or deployment is authorized by this ADR.
