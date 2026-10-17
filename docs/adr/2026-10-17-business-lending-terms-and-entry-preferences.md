---
status: accepted
owner: project
updated: 2026-10-17
tags: [loans, origination, setup, preferences]
related: [../implementation/origination-complexity-review-20261017.md, 2026-10-17-origination-review-and-safe-recovery.md]
---

# Business lending terms and independent entry preferences

The owner accepted the complexity review and its delivery order, while requesting
more detail before changing number assignment. Implement the existing setup journey
and narrow change actions first. Official number assignment remains unchanged.

Present effective business lending terms together, resolved for a selected register
and date using existing calculation, metal-rate, fee and product readers. Show
actual sources and exceptions. Do not introduce a lending-program table, another
policy resolver, workflow framework or automatic product activation.

An operational DIRECT/PAPER default must be editable without creating financial
policy or metal-rate revisions. Add one explicit Workspace-owned LoanEntryPreference
model with optional licence/register scope and DIRECT/PAPER/INHERIT choices.
This is current presentation state, not a dated financial contract. Existing
financial-policy preference values remain a per-scope fallback until an explicit
preference is saved. Explicit INHERIT skips the retained value at that scope.
Record actor/before/after through the existing preference audit. Retain forced RLS,
scope guards, source-bound review and concurrent stale-change checks.

Old financial configuration fields and published profiles remain readable; new
screens hide the legacy preference field and expose its independent action.
New operational preferences require a new setup/package version, with old profile
exports held rather than silently dropping them. Exact recovery includes the new
model and retains its existing exact-schema/guard requirement.

Rate-only changes append only selected metal rates at the chosen scope. Narrow
agreement amendments copy the effective full calculation policy, changing only
the selected terms and disclosing complete-override behavior. Saved agreements,
monitoring policies and numbering are unaffected. Existing review signatures,
retries and compatibility actions remain supported.

Delayed official numbering is a separate decision requiring the business's
pre-payout document/register practice, stable draft identity, review/retry design,
concurrency and compatibility evidence. Never renumber saved drafts, recycle an
issued number, or change historical paper claims as part of this delivery.
