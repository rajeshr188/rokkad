---
status: active
owner: loans
updated: 2026-10-16
tags: [contracts, monitoring, portability]
related: [../adr/2026-10-16-monitoring-policy-lifecycle.md, fresh-business-setup-v4-rows.json]
---

# Monitoring policy lifecycle and setup version 4

LoanMonitoringPolicy adds two explicit, non-null fields:

| Field | Values/default | Meaning |
|---|---|---|
| scope_action | APPLY (default), RETIRE | Apply these settings, or stop applying this scope and continue to Workspace fallback. A retired Workspace scope has no fallback. |
| replaces_scheduled | false (default) | An authored successor may replace the previous future schedule from an earlier effective date. Ordinary command dates remain today or later. |

Both lifecycle actions require the latest predecessor, same Workspace/licence
scope, open-ended periods, increasing version, actor and reason. Neither changes
an existing row. Resolution selects the highest version applicable to the business
date; a retired licence falls through to the Workspace policy rather than an older
licence version. Replacing a schedule takes precedence from its effective date
onward; it does not reactivate the displaced future rows later.

Fresh setup schema 4 is [the exact row inventory](fresh-business-setup-v4-rows.json).
Business package `rokkad-business-package/4` uses it when retained policies have a
retirement or schedule replacement. Profiles 1–3 keep their published inventories
and reject export of these unrepresentable actions. Their restoration supplies
APPLY / false explicitly. Their older valuation-basis meanings are unchanged.
Source IDs/actors are remapped under ordinary destination authority; original
dates, reasons and lineage remain. Database guards remain enabled during restore.

The combined candidate uses snapshot V13, including the separately approved
represented-position coverage treatment; lifecycle support first appeared in V12.
It requires compatible lifecycle-aware readers. Ordinary monetary and valuation
formulas are unchanged. Native recovery remains an exact-schema inventory with a
schema fingerprint; an older database/application image is not a compatible
recovery writer after lifecycle evidence exists. Migration reversal is refused
when it would discard retained lifecycle/package evidence. Compatible web,
continuous worker and scheduled readers must be deployed together before staff
use the new actions. This document does not authorize a production deployment.
