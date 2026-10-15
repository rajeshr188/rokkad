---
status: complete
owner: project
updated: 2026-10-15
tags: [loans, party, collateral, excel, release, production]
related: [../adr/2026-10-15-filtered-loan-excel-summary.md, loan-summary-export-release-20261015.md]
---

# Collateral summaries production release

The owner's commit, push and production instruction covers the Excel collateral
columns and compact loan-list/Party previews. The scoped combined source includes
the already deployed grace-payment fix, its tests and the corrected
admitted-directory preview assertion. The unrelated
WhatsApp onboarding documentation remains excluded. The existing encrypted R2
pre/post backup job remains explicitly approved in this conversation.

Application source `b029d4a52771cb3355c4509ee6b7033f0e8c1186` is pushed on
`release/collateral-20261015` (also pushed on the working branch) and deployed at **15 October 2026, 17:27:41 IST** as
`rokkad:collateral-production-20261015-b029d4a52771`, image ID `sha256:5fae9fdf6d0eca65387562bbf627762f0eb9e77365a6b65ad6fb1ffccefbe3cd`.
All six groups pass in [the exact-source CI run](https://github.com/rajeshr188/rokkad/actions/runs/38725011043),
including 2,491 Loans cases. Local validation passes 61 affected
cases, four directory JavaScript checks, import boundaries and current document
links. CI selections overlap and their counts are not summed.

Excel appends recorded item descriptions, quantities and custody, plus separate
held gross/net grams for Gold, Silver, Bronze and Other. Returned/transferred/
disposed rows are excluded from holdings; unknown gross and unconfirmed paper
handover stay unavailable. Row weights are never multiplied by quantity. The
directory and Party active/closed lists show a shared two-item preview and a
remaining-entry count. Party previews load after pagination; Khata return labels
use its own actual return/handover operations. Existing loan numbers, financial
columns, filters, permissions and risk calculations remain unchanged. The existing
JSK grace-payment correction is preserved: plain full-access grants permit payment
without removing grant evidence, while restrictions and separately provisioned
grants retain review. Both public purchase suites now run in the billing CI group.

The isolated production-copy rehearsal restores 1,068,145 rows
across 222 tables and preserves all
219 original business projections.
Financial source rows also stay exact after a bounded risk-worker check. The
restricted read-only feature checks reconcile financial values and per-metal
collateral weights for 104 active-loan rows
across three Workspaces. Both list previews render. Rehearsal exports take
3.209, 2.731, 0.758 seconds under the
restricted reader. No raw workbook or borrower row leaves the private server.

The original collateral CI found one outdated dictionary-equality assertion among
2,491 Loans cases. The corrected test still requires a single admitted ordinary
loan, no unresolved source duplicates and both retained snapshots, and now verifies
its returned-item preview. No application behavior was changed for that correction.

A concurrent, owner-approved grace-payment deployment changed the live web image
while the first release was testing. The baseline guard refused the switch. The
owner confirms that work is finished and requests preservation. Its three runtime
modules are committed with their tests/docs, its exact live image is independently
recovered, and native/closed/contract readers pass on the actual restored database
before updating the existing backup recovery record. The combined image is built
from committed source and independently recovered again. Current web and worker
predecessors are tracked separately; recovery retains their exact original bindings.

No migration is pending or applied. The coordinated checkpoint and switch take
418.883 seconds. The switch captures a fresh
private checkpoint, preserves 219
original business projections and verifies native, closed, feature and release
readers before switching web, monitoring and four scheduled readers. Environment
values and protected configuration are preserved apart from the reviewed image
and static-volume bindings. The retained predecessor image supports recovery
without restoring or overwriting customer rows.

Production read-only acceptance checks pass for 3 Workspaces,
104 collateral/financial export rows and both
list previews. Both live readers match all 1871 committed runtime
files, use effective UID 10001 and the restricted database role, and have no new
error lines. HTTPS and all six timers pass. Independent encrypted application
image download, local-key decryption, checksum verification and exact image reload
pass; the key stays local and temporary plaintext image files are removed.
Pre/post encrypted operational backups, remote download verification and retention
pass. Both disposable rehearsal databases and the local task test database are
removed while dumps, proofs and recovery artifacts remain. JCL/JSK/Lakshmi grace
grants stay through 22 October, 23:39:08 IST; WhatsApp remains disabled.
Read-only pre/post billing-page checks preserve the grace-compatible purchase
history guard and current legitimate billing state; no provider operation, mandate,
order, payment or customer/register correction is performed by this deployment.
At grant expiry the temporary grant is absent; legitimately paid access can continue.
