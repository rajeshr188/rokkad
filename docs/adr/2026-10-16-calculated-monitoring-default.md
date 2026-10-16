---
status: accepted
owner: loans
updated: 2026-10-16
tags: [monitoring, defaults, amendments]
related: [2026-10-12-current-monitoring-valuation-policy.md]
---

# Default new monitoring policies to calculated metal value

The owner requests current calculated metal value, with lower-of available as an
explicit alternative, across Workspaces. New policies therefore default to
`CALCULATED_METAL_VALUE`. Both model and database defaults agree. This supersedes
only the new-policy preserving default in the 12 October decision.

Retained policies, original lending snapshots and published setup profiles keep
their meaning. Existing policy history is not updated by the default migration.
Changing an existing business choice appends an authorized effective-dated
amendment with a reason, explicit predecessor and existing scope. Older amendment
callers retain the predecessor's choice. Published setup profiles 1/2 still restore
their explicitly defined preserving basis; profile 3 retains explicit choices.

Calculated value requires recorded weight/purity and usable fresh buying prices.
Lower-of requires both a usable calculated value and approved appraisal; it is not
an appraisal-when-available fallback. No policy change supplies missing prices,
verifies physical measurements, establishes original approval or confirms books.

Ordinary setup opens the latest open-ended Workspace policy for amendment when
one exists, retaining its scope, settings and predecessor. A separate new-scope
link remains available. Unlinked overlaps are rejected with an actionable Amend
message. Concurrent, backdated, foreign-scope and immutable-history guards remain.

The owner also authorizes current Workspace-default amendments in JCL, JSK and
Lakshmi. Use the existing restricted-runtime service with the requesting actor's
existing setup authority. Preserve every other limit and all original loan
financial evidence. Workspaces without a configured policy do not receive invented
thresholds. Web/worker deployment and owner migration 0088 deliver the new-policy
default; ordinary existing-policy amendments are independent of that deployment.
