---
status: active
owner: project
updated: 2026-09-09
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
