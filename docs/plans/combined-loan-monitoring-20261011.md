---
status: completed
owner: loans
updated: 2026-10-12
tags: [plans, monitoring, risk, dashboard]
---

# Combined loan monitoring correction

The owner accepted one coordinated sequence for the 24 September loan-risk audit
and the [11 October JCL Financial health diagnosis](../implementation/financial-health-jcl-20261011.md).
Keep their evidence distinct, but fix their shared engine once. Direct, recorded
paper and accepted opening positions use the same current monitoring; unavailable
earlier history is not invented to make an assessment possible.

## Delivery order

| Slice | Scope and acceptance | State |
|---|---|---|
| MR-01 | Revalidate the old findings against current continuation, dashboard and monitoring code; retain dated evidence and identify remaining gaps. | Source review complete; boundary findings validated in MR-02. Other findings receive targeted tests in their slices. |
| MR-02 | Live assessment boundaries: access denial in one Workspace cannot stop other worker turns; reject historical/future live refresh before projection, event or alert writes. Historical selectors remain read-only calculations using currently available knowledge. | Verified locally; see [MR-02](../implementation/live-risk-boundaries-mr02.md). |
| MR-03 | Financial integrity and recovery: unsafe debt/DPD/LTV cannot be presented as a healthy result; worsening or unknown evidence cannot cure an alert; genuine recovery links its event; repeated material occurrences remain distinguishable. | Verified locally, including corrected zero-debt renewal compatibility and real-payment recovery; see [MR-03](../implementation/risk-integrity-recovery-mr03.md). |
| MR-04 | Preflight and database protection for immutable risk events and same-Workspace/loan/snapshot/event references, including restricted-role adversarial tests. | Verified locally across restricted DML and populated preservation/refusal rehearsals; live owner preflight remains before coordinated release. See [MR-04](../implementation/risk-evidence-guards-mr04.md). |
| MR-05 | Explicit current monitoring valuation selection through immutable monitoring policy amendments, distinct from frozen origination evidence; explain freshness, financial support, paper-book coverage and valuation separately. Preserve the existing basis unless an owner chooses a new one. | Verified locally: 207 broader cases and 13 final MR-05 plus five corrected projection checks pass. Preserving upgrade, prospective choice and independent paper coverage are proved; explicit choices require a newer business setup export profile. See [MR-05](../implementation/current-monitoring-valuation-mr05.md). |
| MR-06 | Coordinated release and explicit bounded recurring worker for selected Workspaces. Verify representative loans, coverage, errors, refresh delay, rollback and foreground cost before claiming production readiness. | Deployed: monitoring-only web/worker checkpoint, owner preflight/migrations, source-preserving pilot, graceful shutdown, prior-image reader recovery, exact-image recovery and both backups pass. The 68/39/17 test runs pass; initial catch-up has zero observed errors, while valuation/book coverage remains incomplete. See [MR-06](../implementation/monitoring-release-mr06.md). |
| MR-07 | Measure and reduce repeated source reads/repricing; add further assessment history only for a demonstrated need. | Deployed: exact five-file web/worker image, independent image recovery, isolated financial-source preservation, MR-06 reader recovery, graceful shutdown and both backups pass. Seven READ ONLY pairs have exact output parity with 35% fewer calculation queries; 80 distinct checks pass. No history table or policy change. See [MR-07](../implementation/monitoring-efficiency-mr07.md). |

MR-02 through MR-04 are the correctness gate before valuation/worker activation.
Each slice updates this plan and Status with actual test evidence. Local delivery
does not imply deployment of the other pending portability and dashboard work.

## Revalidation matrix

| September finding | Current evidence and selected treatment |
|---|---|
| F1: inconsistent obligations appear healthy | MR-03 rejects inconsistent financial risk/DPD, blocks unsafe LTV and clears failed current metrics under ERROR. Verified across saved/live paths and genuine repayment recovery. |
| F2: denied Workspace stops worker | MR-02 reports the denied turn and continues other explicit Workspaces; denial does not become a write bypass. Verified locally. |
| F3: non-today refresh changes live state | MR-02 rejects historical/future live HTTP, command and service writes, including the final write boundary, without disabling dated read-only calculations. Verified locally. |
| F4: historical calculation not historically reproducible | Unified continuation changed the older interest path substantially. Re-test supported checkpoint/date boundaries; distinguish a restatement using available source knowledge from a captured past assessment. No retrospective certification. |
| F5: risk evidence protection incomplete | MR-04 proves append-only events and matching Workspace/loan/snapshot/source/recovery/notice links under restricted database DML. Populated valid upgrades preserve evidence; invalid links stop preflight. Live inventory remains a release prerequisite. |
| F6: exposed policy fields/duplicated classification | MR-05 separates current valuation, removes the ineffective monitoring-grace input and preserves its old values. Actual grace comes from frozen product/accepted opening terms without shifting DPD; severity remains condition-derived and legacy mapping is retained. Verified without a strategy framework. |
| F7: false cure and repeated occurrences | MR-03 proves worsening/unknown evidence cannot cure alerts; genuine clearance links a confirming event, and identical later incidents remain distinct without unchanged-refresh duplicates. |

## Operating constraints

- Monitoring writes derivative assessments, internal events and staff alerts only.
  It does not post debt, fabricate appraisal/quote evidence, certify absent paper
  transactions, change original agreements or send borrower messages.
- Current assessment, usable financial calculation, checked paper-book position
  and adequate valuation are separate dimensions. A complete display requires
  the relevant evidence, not merely a successful worker pass.
- No silent market-only reassignment of imported appraisal-based loans. Review
  current monitoring choices through setup; original valuation stays unchanged.
- Use existing Django services, explicit Workspace context, restricted runtime
  and bounded worker turns. No new queue, microservice or regulatory NPA engine.
- Large-scale capacity testing remains deferred under
  [FW-004](future-work.md#fw-004-launch-scale-loan-monitoring-capacity).
  The September benchmark does not establish current production capacity.

## Evidence sources

The original audit is retained outside the checkout at
`C:\Users\rajes\Documents\Codex\2026-09-24\referenced-chatgpt-conversation-this-is-an\outputs\rokkad-loan-risk-audit.md`.
It reviewed a September source checkpoint, not the present code or a current
production benchmark. The October diagnosis is a restricted read-only inventory,
not an assessment refresh or policy change.
