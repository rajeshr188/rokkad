---
status: accepted
owner: project
updated: 2026-09-25
---

# Series-specific monthly interest rates

JSK's WH register needs gold at 1.1% per month and silver at 3%, while its
unprefixed register retains the existing gold 2% / silver 4% defaults.

Extend the existing effective-dated metal rate policy with an optional series.
A series override must also identify that series' licence and Workspace, enforced
by model validation and a database trigger. Rate precedence is series, then licence,
then Workspace, independently per metal and loan date. Fallback queries explicitly
exclude series overrides. Existing policy rows are unchanged.

The setup screen has a separate series-interest form. Its authorized service appends
gold and silver policies atomically, locks the series and records an audit entry.
This does not override fees, valuation, loan products or calculation methods.
The same series-aware resolver is used by preview, draft creation/edit, approval,
split and renewal. Existing approval snapshots and disbursed economics remain frozen.
Drafts whose resolved rates change require resaving before approval.

Existing effective-date uniqueness applies per scope and metal. The migration is
additive; do not roll back to older application rate resolution while active series
overrides exist, because older code cannot distinguish them from licence overrides.
