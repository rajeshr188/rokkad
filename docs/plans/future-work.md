---
status: active
owner: project
updated: 2026-09-24
tags: [plans, future-work, ideas]
related: [active.md, completed.md, ../ROADMAP.md, ../STATUS.md]
---

# Future work

The main register for ideas we deliberately shelve and may pick up later. Record
enough context here to resume without reconstructing the conversation. An entry is
not a commitment, a scheduled task, or approval to implement it.

Use [active work](active.md) for work selected for delivery, [the roadmap](../ROADMAP.md)
for priorities, and [completed work](completed.md) for delivery history. Detailed
designs and decisions stay in their linked plans and ADRs. The older
[backlog](backlog.md) is historical input to review, not a second current idea queue.
Release requirements such as production media verification stay in their acceptance
plans; shelving an idea must not hide a release blocker.

## Register

| ID | Idea | State | Resume trigger | Where it stopped |
| --- | --- | --- | --- | --- |
| FW-001 | Optional owner-configurable license scope | Shelved; review and owner approval required | Owner chooses to revisit staff access across licenses | Direction documented; no license assignments or restrictions implemented |
| FW-002 | Razorpay setup and provider test-mode acceptance | Shelved at owner request; required before real paid onboarding | Owner starts Razorpay setup and explicitly resumes provider testing | Billing implementation and mocked tests complete; no provider setup or end-to-end rehearsal |
| FW-003 | Formal lender-specific NPA classification | Unscheduled design review; no implementation approval | Intended lender type needs regulatory NPA reporting | Existing per-loan operational DPD and collateral-risk classifications documented |
| FW-004 | Launch-scale loan monitoring capacity | Shelved at owner request | Better representative hardware is available and owner resumes testing | 300,000-loan baseline failed; million-loan fixtures prepared, latest retry stopped at owner request |
| FW-005 | Historical market-valued loan entry | Unscheduled policy review | Owner needs backdated origination or a historical Loans import contract | Current-day quote rule implemented; historical eligibility and exceptions remain undesigned |
| FW-006 | Party bundle history progress filter | Shelved at owner request; optional usability | Operators need to find unfinished attempts in a larger history | Saved history and cancellation work; filtering not implemented |
| FW-007 | Guided customer-facing legacy migration | Recorded at owner request; future work, unscheduled | Owner selects self-service migration onboarding for delivery | Customer spreadsheets and prepared loan imports work; source-specific loan preparation still requires an operator |
| FW-008 | Servicing-only subscription restriction | Deferred beyond the pre-cutover continuity increment | Owner selects a collections-only stage after read-only/grace acceptance | Full access, seven-day grace, read-only and audited administrator decisions implemented; action-level servicing exceptions undesigned |

## FW-008: Servicing-only subscription restriction

**Captured:** 2026-09-24. **State:** Deferred; unscheduled.

The approved pre-cutover increment provides normal grace, read-only access and
dated administrator decisions. A later stage could allow repayments, collateral
release and the documents needed to service existing loans while blocking new
lending. Define exact allowed actions, reversals, renewals, backdated operations,
document issuance, notification delivery and import/operator behavior first.
Do not equate this with GET versus POST, loosen lifecycle/RLS, or accidentally allow
new financial exposure. Add action-level tests and an explicit customer/admin
explanation before enabling it. Razorpay provider acceptance remains FW-002 and is
required before real paid onboarding. See the
[continuity decision](../adr/2026-09-24-subscription-access-continuity.md).

## FW-007: Guided customer-facing legacy migration

Reconfirmed on 2026-09-25 in the [loan journey reference](../flows/loan-journey.md#7-imported-history-and-deliberate-digitization)
and in-app staff guide. Manual old-paper loan admission and guided Excel loan
imports remain future work; the published product story distinguishes them from
the existing assisted migration foundation.

**Captured:** 2026-09-24. **Last reviewed:** 2026-09-25. **Decision owner:** project owner.
**State:** Future work; unscheduled. **Implementation approval:** not granted by
this entry. The owner explicitly requested that this gap be retained in the backlog.

**Problem.** Customers should be able to bring supported legacy data and complete
a guided migration without writing canonical JSONL, invoking server commands or
depending on an operator for every source mapping and reconciliation decision.
Existing portability is not a universal upload-any-spreadsheet-or-database importer.

**Existing foundation to reuse.** Party CSV/XLSX/JSONL mapping, previews, identity
checks, reusable presets and bundle commits; complete-history loan admission;
reviewed opening balances; historical-only archives; source-specific PostgreSQL
dump preparation; and the separate media migration pipeline. The hosted Linode
rehearsal used these capabilities plus operator preparation, not a generic customer
migration wizard. Preserve existing financial services and evidence contracts.

**Proposed user journey.**

The owner's two onboarding scenarios are explicit acceptance examples:

- **Start fresh digitally:** use a new series under an existing verified licence
  for new customers/loans; earlier paper loans remain outside Rokkad. No legacy
  import is required. Reporting covers only recorded loans, not the whole physical
  business portfolio.
- **New lending plus gradual paper migration:** continue normal lending while
  bringing earlier physical loans into the same Workspace, either by manual entry
  or Excel. Both proposed input paths must use the same historical admission and
  reconciliation services. A guided manual legacy-entry screen and generic loan
  spreadsheet preparation are future work, not the ordinary new-disbursal form.

For the second scenario, propose an **Add existing loan** entry point with manual
and spreadsheet options. Support explicit matching to borrowers already created
during new lending; the current import identity foundation does not itself provide
a customer-facing existing-Party binding editor. Preserve old licence/series/loan
references and protect the new live number range. Classify evidence as complete
supported history, a reviewed outstanding opening, or archive-only closed history;
active status alone does not select opening mode. Each admitted loan/batch needs an
explicit financial handover date and reconciliation so a payment is recorded once,
old interest is not charged twice, and original loan age is not reset. Different
loans may be prepared in later batches while new lending continues. Current opening
servicing requires dates strictly after the opening date; the proposed journey must
explain this boundary or separately review an extension. Show migration coverage
so partial digitisation is never presented as the complete business portfolio.

1. Choose a supported source format/template or adapter, see its coverage and limits,
   and upload source data into private Workspace staging.
2. Map columns and source identities; resolve borrower matches and duplicates;
   map destination licences, series, numbering and products through guided forms.
3. Classify each loan as supported complete history, a reconciled active opening,
   historical-only evidence, or blocked/unsupported. Explain the reason in ordinary
   business language; never infer eligibility from active/closed status alone.
4. Guide missing-evidence decisions and reconcile principal, interest, fees, original
   dates, continuation rules, collateral/custody and supported media references.
   Show source-to-destination totals and every unresolved exception before approval.
5. Preview without creating operational financial records, obtain explicit approval,
   and import through existing atomic, idempotent services. Show progress, safe retry,
   retained audit/source evidence, result links and post-import reconciliation.

**Acceptance boundary.** Start with an explicitly selected source/template and a
representative customer completing the flow without hand-written JSON or CLI work.
Test permissions, Workspace isolation, conflicting/repeated identities, changed
source files, missing versus zero values, partial failures, retry and reconciliation.
Show unsupported data/attachments honestly. Never execute an uploaded SQL dump
against the application database, invent historical transactions, overwrite posted
evidence, silently merge borrowers, or recycle reserved numbers.

**Open decisions / first step when resumed.** Inventory current adapters and import
screens, select the first supported customer source and batch sizes, and design a
single end-to-end journey using representative data. Define media coverage, operator
handoff cases and cancellation/resume behavior before selecting an active delivery
slice. This backlog item does not by itself become a production-cutover blocker or
promise arbitrary-source self-service migration.

**References:** [Party workflow](../flows/party-master-portability.md),
[loan setup preparation](../flows/loans-import-preparation.md),
[complete-history import](../flows/loans-history-import.md),
[prepared legacy openings](../flows/legacy-opening-import.md),
[portability follow-up](loans-portability-audit-followup.md).

## FW-001: Optional owner-configurable license scope

**Captured / last reviewed:** 2026-09-09. **Decision owner:** project owner.
**Priority/date:** unscheduled. **Implementation approval:** not granted.

**Problem and possible benefit.** A business with multiple licenses may want some
staff to work with only part of its loan portfolio while sharing borrower profiles.
This should be an optional business choice, not a restriction imposed on every owner.

**Where we left it.** Workspace remains the SaaS tenant, with PostgreSQL forced RLS,
membership and action permissions. Loan access is currently organization-wide subject
to those permissions. The role, private-media application and onboarding improvements
are published in checkpoint `4d15477`; they did not implement license scoping.
Production media verification remains a separate acceptance gate.

**Preserve these decisions.**

- Keep organizations/Workspaces as tenants and licenses inside them.
- Any license scope must be optional and configurable by the owner, with an
  organization-wide mode retained.
- Borrower profiles remain shared across the organization subject to view permissions.
- “All loans under assigned licenses” was one proposed mode, not an accepted universal
  rule. Do not infer creator-only or personally assigned loan access.
- License and branch are not automatically the same concept.
- A fresh design review and explicit owner approval are required before implementation.

**Open decisions for the next discussion.** Choose the supported scope modes; define
unassigned staff, new/expired licenses, owner access, and switching restrictions on
or off. Decide what financial information a shared borrower profile exposes. Review
existing-member migration, audit, in-flight work and background jobs. Determine whether
intra-Workspace database enforcement is needed in addition to application checks.

**First step when resumed.** Read the linked ADR and SCP review criteria, compare them
with the current implementation, and prepare concrete owner/staff examples for review.
Record the owner's selected behavior and explicit implementation approval. Only then
create an active delivery plan linked back to FW-001; do not start with schema changes.

**Acceptance outline if approved.** Test both unrestricted and selected scope modes;
enforce the approved behavior on direct URLs, services and jobs, as well as borrower
financial tabs, searches, reports, exports, photos/PDFs, collateral, releases and
notifications. Cover cross-license transfers, splits and renewals, membership/scope
revocation and configuration changes without rewriting historical loan ownership.

**References:** [tenant/access ADR](../adr/2026-09-09-organization-tenant-and-license-access.md),
[SCP-01/SCP-02 delivery register and review criteria](saas-access-media-and-onboarding.md#scp-optional-scope-last-and-subject-to-explicit-owner-approval),
[action-permission review](../implementation/action-permission-review.md).

## FW-002: Razorpay setup and provider test-mode acceptance

**Captured / last reviewed:** 2026-09-09. **Decision owner:** project owner.
**State:** Shelved. **Priority/date:** unscheduled.
**Resume authorization:** owner chooses to resume; proceeding with other review
improvements does not reactivate this work.

**Why shelved.** The owner has not started Razorpay setup and wants to focus on the
remaining project-review improvements. Do not request keys, create an integration,
expose a callback endpoint or run provider calls as part of unrelated cleanup.

**Where it stopped.** Workspace-bound checkout, paid-period expiry, verified known-
payment recovery, processed refund evidence and final owner review decisions are
implemented locally with mocked provider/mail tests. Development migrations through
subscriptions.0009 are applied. These changes remain uncommitted as of this entry.
No real Razorpay payment/refund or provider test-mode rehearsal has been performed.
The implementation is not accepted for real paid onboarding yet.

**What the postponed step means.** Establish the owner's Razorpay test environment,
configure test credentials and a webhook secret privately, provide an HTTPS callback,
and exercise checkout plus actual provider event delivery in test mode. Verify
captured payments, failed/abandoned attempts, repeated/delayed callbacks, partial/full
processed refunds, recovery and reviewed resolutions against the local records.
Mocked automated tests remain available without Razorpay setup.

**Preserve these constraints.** Workspace ownership/context, frozen order/amount/
currency/plan evidence, RLS, immutable financial evidence and idempotent handling
must remain intact. No live charges/refunds are authorized by this entry. Unknown
orphan/legacy contracts cannot be reconstructed by guessing; refund issuance,
chargebacks and proration remain outside current implementation.

**First step when resumed.** Read current billing flow/status, confirm the owner is
ready with a test environment, inventory the intended runtime and HTTPS callback,
and prepare a concrete test-mode acceptance checklist. Recheck provider documentation
at that time. Keep secrets out of Git, logs and documentation. Record the observed
outcomes and unresolved issues before declaring paid onboarding ready.

**References:** [checkout/recovery/review flow](../flows/subscription-checkout.md),
[billing decision](../adr/2026-09-09-workspace-checkout-evidence.md),
[hardening delivery plan](project-hardening.md), [current status](../STATUS.md).

## Maintaining and resuming entries

Assign a stable `FW-NNN` ID and add a register row when shelving an idea. Record the
reason, last known state, open decisions, references and first useful next step.
Use the states **Shelved**, **Ready for review**, **Active**, **Completed** or **Dropped**;
record approval separately so “Ready for review” never implies permission to implement.

When an idea is selected, update its state and link the active plan. When delivered
or dropped, retain the entry with its outcome and commit/decision link. Do not renumber
or delete entries merely to keep this list short. Update the last-reviewed date when
the decision or restart point changes. “Proceed” on another task does not reactivate
a shelved idea.

### Copyable entry template

```markdown
## FW-NNN: Idea title

- State: Shelved
- Captured / last reviewed: YYYY-MM-DD
- Decision owner:
- Priority/date: Unscheduled
- Implementation approval: Not requested / required / approved with reference
- Problem and benefit:
- Why shelved / resume trigger:
- Where it stopped (existing behavior, completed work, remaining work):
- Decisions and constraints to preserve:
- Open questions:
- First step when resumed:
- Acceptance outline:
- References (ADR, plan, files, commit):
- Outcome / active delivery link:
```

## FW-003: Formal lender-specific NPA classification

**Captured:** 2026-09-11. **Priority/date:** unscheduled.
**Implementation approval:** not granted by the monitoring capacity task.

Current Loan health derives per-loan DPD from contractual obligations and labels
Standard, Watch and Substandard using effective monitoring-policy thresholds.
Collateral LTV/shortfall is independent. The default Substandard threshold is
DPD >= 90, which must not be presented as a complete regulatory NPA decision.
The compliance-profile name alone does not implement regulatory rules.

Before implementation, identify the intended lender type and applicable framework,
then review classification boundaries, borrower-wide versus per-loan scope,
upgrade/cure rules, restructuring treatment, doubtful/loss aging and any reporting
or income-recognition obligations. Preserve canonical schedules, repayments and
reversal history. Do not silently change the operational thresholds or restore
retired general-ledger accounting. See [the current explanation](../flows/loan-health-monitoring.md#payment-performance-and-the-npa-distinction).

## FW-004: Launch-scale loan monitoring capacity

**Shelved / last reviewed:** 2026-09-12. **Decision owner:** project owner.
**Resume trigger:** better representative hardware is available and the owner
explicitly resumes capacity testing. Do not automatically restart long local runs.

**Target.** At least 100 organizations with 3,000-10,000 active loans each and
30-100 loans processed per organization/day. All affected active loans should
receive a current health assessment within one hour after a metal-price change,
while ordinary servicing remains usable. This target remains unproven; shelving
the test does not establish production capacity or waive launch acceptance.

**Where it stopped.** The valid 100 x 3,000 run assessed 121,869/300,000 loans by
3,589.09 seconds and failed the target, with zero reported errors and passing
sampled correctness checks. The million-active/200,000-closed fixture was prepared.
One upper-size attempt was invalidated by a 706-second measurement gap. The next
retry was stopped at the owner's request because it was too slow on this machine;
its last observation was 19,185/1,000,000 at 940.65 seconds, with no reported errors.
That partial retry is not an acceptance result and had no final monetary-validation
pass. Test clients are stopped and the temporary role is removed. The disposable
`test_rokkad_monitoring_load` database is retained locally (about 27.5 GB before the
latest wave); no normal development or production worker was started.

**Pickup notes.** Preserve the existing RLS, closed-loan exclusion, per-loan commits,
source-change guards and repayment/reversal rules. The
[capacity report](../implementation/monitoring-capacity-test.md) records workload,
environment, exact results, limitations and commands. Resume on documented hardware
with an uninterrupted test window; revalidate fixtures and runtime-role restrictions.
The full 300,000/1,000,000 matrix and realistic foreground traffic still need to pass.
Overlapping price changes, recovery/restarts and concurrent origination/releases
remain additional acceptance dimensions. Hardware alone is not an established fix:
measured candidates include the per-loan pending lookup and repeated financial
history reads. Assess those separately when capacity work resumes.

## FW-005: Historical market-valued loan entry

**Captured:** 2026-09-12. **Priority/date:** unscheduled; no exception workflow is approved.

The owner chose same-day quotes at approval. The first implementation uses today's
loan/disbursal dates for methods that consume Rates, as the recommended implementation
assumption. Appraisal-only date behavior is unchanged. A separate owner preference
about historical entry has not been confirmed.

Before enabling backdated market origination, define the business date versus
actual approval/disbursal time, historical quote applicability/knowledge, evidence
provenance, permissions and any exceptional review. Do not silently use today's
quote for historical economics or add a generic owner bypass. Coordinate with the
historical Loans import contract when that work is selected. Existing active/closed
loans and their immutable history are unaffected. See the
[origination decision](../adr/2026-09-12-origination-quote-freshness.md).


## FW-006: Party bundle history progress filter

**Captured / last reviewed:** 2026-09-12. **Decision owner:** project owner.
**State:** Shelved at owner request. **Priority/date:** unscheduled.

**Problem and possible benefit.** Filter saved Party ZIP bundle attempts by progress
so operators can find unfinished work without paging through completed attempts.
This is optional usability, not a prerequisite for Party MVP or Loans portability.

**Where it stopped.** Saved history, stable review URLs, pagination, live progress,
combined commit and cancellation are implemented. No filter has been added.
Individual CSV/XLSX/JSONL imports remain separate from bundle history.

**When resumed.** Reuse existing batch-derived progress with Workspace-scoped
queries and pagination. Preserve current permissions, immutable group membership
and completed evidence. No new stored status or background worker is required
merely to filter the list. Select the work explicitly before implementation.

**References:** [Party portability scope](data-portability.md#mvp-scope-closeout-2026-09-12),
[operator guide](../flows/party-master-portability.md).
