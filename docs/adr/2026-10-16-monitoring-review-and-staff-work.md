---
status: accepted
owner: loans
updated: 2026-10-16
tags: [loans, monitoring, workflows, evidence]
related: [2026-10-16-monitoring-policy-lifecycle.md, ../plans/loans-architecture-hardening-20261016.md]
---

# Review monitoring changes and reuse ordinary staff workflows

The owner accepts the architecture follow-up and its ordered improvements.

The separately approved [represented-position treatment](2026-10-16-represented-position-transaction-coverage.md)
supersedes compulsory book certification. These batch/capture tools provide
optional assurance; a supported represented position does not require them.

Paper/completed-payout entry displays the effective LoanMonitoringPolicy separately
from saved valuation/reference evidence. Existing admission fields, signed reviews
and financial exchange profiles retain their meanings. Economic-policy suggestions
are labelled saved references; they do not configure current monitoring or prove
original approval. Unknown reference values are not invented. Removing mandatory
reference fields from an older financial admission shape requires a separately
reviewed compatible financial profile, not silent reinterpretation of old inputs.

Monitoring setup uses read-only preview and explicit confirmation. Bind actor,
Workspace, proposed settings, lineage, business day and source identities. Preview
shows affected active scopes, excluded overrides, changed values, displaced future
instructions, held-metal price evidence and up to 25 collateral observations using
the shared observation calculator. This is today's evidence under proposed rules,
not a financial/risk simulation or forecast. Confirmation rechecks source identity;
stale review is rejected. Preview acquires no write locks or new evidence rows.

Readiness for active loans is separate from first-loan setup and includes stopped
and legacy registers. Configuration visibility is not a worker heartbeat. Expose
assessment, financial, valuation and transaction counts separately. Ordinary loan
entry does not pay the additional portfolio-diagnostics query cost. Monitoring
readiness never becomes permission to post a receipt or certify missing history.

Extend the existing signed batch transaction review with future-capture choice and
bounded imported-cohort selection. Explicit Workspace, series, retained import
namespace and cursor select at most 50 active loans. Preview exceptions separately;
only eligible loans can be confirmed, through their existing per-loan commands.
Successful retries do not create duplicate reviews. Each review retains cohort
source identity in its reference and binds its own financial/capture fingerprint.
The next batch is a separate deliberate confirmation, not unattended bulk assurance.
Accepted checkpoints do not assert earlier receipts. Already-issued ordinary batch
tokens retain their submitted argument shape.

The database book-review guard uses the accepted opening checkpoint as its earliest
supported date, falling back to original loan date for native history. This also
permits an optional check of a closed zero checkpoint whose original date is
unknown, without permitting claims before the checkpoint. The independent
0090_transaction_review_history_boundary and 0090_recorded_position_notice
branches change different guards; 0091_merge_position_and_review_boundary joins
them. Neither branch replaces the other's guard or changes a retained review row.

Keep existing DPD semantics: any overdue obligation can create collection attention;
watch/substandard thresholds classify risk and can raise its priority. Fixed
transition buckets describe operational ageing. Explain and characterize these
different meanings instead of silently deferring collections. Paginate all open
alerts, prioritize critical/older work and filter existing current evidence into
measured risk, valuation repair, transaction checks and pending assessments. No
extra persisted incident taxonomy or automatic borrower message is introduced.

Expose completed-payout and financial-correction blockers from the same concrete
prerequisites used by commands. A ready-for-review disclosure grants no authority
or guarantee that supplied correction facts will reconcile. Unsupported connected
histories stay held.

Worker diagnostics are read-only, explicitly scoped and honest about unavailable
liveness or exact dirty-age information. Retain current selection/invalidation /
claims until representative measurements justify a compatible scheduling change.
The shelved large capacity programme and production configuration are unchanged.
