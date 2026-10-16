---
status: accepted
owner: loans
updated: 2026-10-16
tags: [monitoring, policy, lifecycle, portability]
related: [../plans/loans-architecture-hardening-20261016.md, 2026-10-16-calculated-monitoring-default.md]
---

# Complete the immutable monitoring policy lifecycle

The owner authorizes the follow-up recommendations in order. Preserve the existing
scope/version/supersession chain instead of introducing a parallel policy system.

The subsequent represented-position coverage change advances the combined
candidate to V13. V12 below identifies this slice's initial reader contract;
release must use the latest combined contract and all compatible readers.

Add an explicit scope action: APPLY settings, or RETIRE the scope. Retiring a
licence override makes resolution continue to the Workspace policy, including
future Workspace amendments. Retained numerical fields on a retirement row are
audit/reference values and are not evaluated. A missing fallback remains unknown.

Within a scope, select the highest applicable version. Existing date-monotone
chains retain their exact results. An explicitly reviewed replacement may start
before its latest predecessor's future start, from today or later. The new version
replaces the earlier schedule from its own effective date onward. Staff see every
scheduled change displaced by this action; they can schedule a further change
afterward. Ordinary amendments keep their existing date order and overlap guards.

Cancelling scheduled changes appends a replacement effective today, retaining the
scope's currently effective settings/action. If the scope has not yet started,
append retirement instead. Thus cancellation is evidenced without deleting or
modifying a scheduled row, inventing a current policy, or resurrecting superseded
future instructions. Retiring an established Workspace policy is not an ordinary
setup action; cancelling its first future configuration can restore unavailable
monitoring. New lending/servicing authority is independent.

Use the existing service authority, Workspace parent NO KEY UPDATE serialization,
locked predecessor, author/reason, and immutable database guard. Past-dated normal
commands remain prohibited. Trusted portable restoration retains original dates
under the same lineage/scope guard. Source invalidation remains transactional.

Published business-package/setup profiles 1–3 retain their meanings and reject
unrepresentable lifecycle rows. Profile 4 carries the two explicit lifecycle
fields; old imports acquire APPLY / no schedule replacement, never a new default
meaning. Native exact recovery keeps its schema-fingerprint requirement. Snapshot
contract V12 identifies lifecycle-aware readers; monetary formulas are unchanged.
Deploy compatible web, worker and scheduled readers together before new lifecycle
commands are exposed. No old writer/reader should interpret retirement as APPLY.
