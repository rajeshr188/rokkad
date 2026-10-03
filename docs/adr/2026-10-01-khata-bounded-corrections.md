---
status: accepted-local
owner: loans
updated: 2026-10-01
tags: [khata, corrections, immutability, custody, authorization]
related: [2026-10-01-khata-agreement-design.md, ../architecture/khata-technical-design.md, ../implementation/khata-corrections.md, ../constitution.md]
---

# Bounded khata compensating corrections

The owner authorized correction safeguards after the custody/settlement backend.
The technical design requires explicit compensation, administrator authority,
source links, dependency checks and actual cash/custody evidence. Implement whole
interest-receipt correction and cancellation of an unhanded exchange. Refuse
other source kinds and settled accounts. This accepts local backend architecture,
not production activation or complete historical correction coverage.

## Decision

Append an immutable `CORRECT` KhataOperation with a protected, unique
`correction_of` relationship. Preserve the original operation, allocations,
valuation, selection, charge and files. A source can be corrected once; a
correction cannot itself be reversed in this version. Reuse existing UUID/hash,
Workspace/account locks and write restrictions.

Require existing Loans administration (`workspace.settings.manage`) for preview
and confirmation. Confirmation also requires `loan.repay` for interest, or
`data.edit` and `loan.release` for an exchange. Administration alone grants
neither money nor custody authority; no role-name authorization shortcuts.

Reject later uncorrected account operations with their identifiers, including
deposits, photos and finalization. A later correction with pending replacement
returns also blocks earlier work. Independent whole receipts can unwind
newest-first; complex chains are refused rather than automatically undone.

Correct interest only when its entire recorded payment was not received, or was
actually refunded in full. Require reason/reference. Preserve original receipt
allocations; canonical paid interest ignores the corrected source, restoring
unpaid dues. Charges, minimum, principal and entitlement stay unchanged. Current
overdue policy and settlement see restored dues. Re-record valid money through a
new ordinary receipt; partial refunds, credits and refund promises are deferred.

Cancelling an exchange releases original OUT reservations and IN membership
logically, preserving their rows. Reserve all replacements for actual return
under the correction source. Originals resume backing; replacements awaiting
return stop backing. Both remain physically held until actual handover. Current
same-day prices/photo policy and hard retained actual-principal LTV apply.
Replacement handover rechecks LTV and due-interest clearance while active; full
financial settlement preserves the pending return source without new reappraisal.

Historical `(item, role)` uniqueness would forbid legitimate reuse after
compensation. Replace it with an account-locked database guard for active
memberships, keeping `(operation, item)` uniqueness and immutable rows. SQL
recognizes corrections only before the operation being validated, preserving
checks of original frozen evidence after later compensation.

## Consequences

Migration 0038 extends existing forced-RLS tables; no new tenant table, generic
event framework or ordinary-loan change. SQL enforces source identity, whole
amounts/allocations, dependencies, complete replacement reservations and hard
LTV. Services additionally enforce authority, today's date and review freshness.

Payout/opening, charges, activated revisions/reductions, settlement, completed
returns and complex histories remain unavailable for correction. They require
separately specified cash/custody and interest outcomes. Pilot review must accept
supported/refused outcomes alongside UI/documents, summaries and native recovery.
See the [checkpoint](../implementation/khata-corrections.md).
