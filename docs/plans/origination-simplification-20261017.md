---
status: completed
owner: project
updated: 2026-10-17
tags: [loans, origination, corrections, plan]
related: [../adr/2026-10-17-origination-review-and-safe-recovery.md]
---

# Origination simplification

The owner-approved monthly-business scope is integrated with closing and deployed
as `a14b5a7f`. The original isolated implementation started at `ed585f33` in
`work/origination-simplification-20261017`; its worktree and unrelated WhatsApp
work remain preserved. See the [verified joint release](../implementation/loan-workflow-release-20261017.md).

1. Shared agreement review: calculation rules, source scope/date/version,
   distinguishing borrower details and signed before/after explanation. Existing
   stale-review, authorization and old-token behavior remain authoritative.
2. Reviewed calculation configuration and rate-only changes: read-only preview,
   narrower overrides, draft/date-range disclosure, explicit acknowledgment,
   source recheck under the existing lock and authorized idempotent completion.
3. Contextual correction impact/hold explanations and same-Workspace replacement
   of an unposted draft with mistaken reserved register/product. Preserve original
   identity/media/evidence, allocate a new number, atomically cancel/link old draft.
4. Explicit saved-rule capability checks and required monthly/started-week parity,
   extending concrete calculators/adapters only with truthful source, compensation,
   document, monitoring and recovery behavior. No implicit monthly substitution.

**Scope clarification:** the owner confirms all current paper agreements use full
monthly interest. The implementation retains that contract and the existing
monthly direct/paper correction parity. Setup and final review disclose different
direct rules' admission/correction limits. New weekly paper evidence and weekly
financial replay are conditional future extensions, not added speculatively.
See the [implementation and capability matrix](../implementation/origination-simplification-20261017.md).

Validation uses an isolated localhost `.test` database, synthetic records and
offline desktop/mobile captures. Production acceptance is read-only; no customer
correction or setup amendment is performed by deployment.
Formatter-only differences must be reviewable separately from behavior changes.

Local delivery is complete for the owner's confirmed monthly business scope:
368 regression tests, 88 final focused tests and 18 offline page/viewport checks
pass, with quality/documentation/isolation/recovery evidence in the implementation
record. Joint integration, commit/push and production release now pass seven
exact-source CI jobs, including 2,764 Loans tests, 481 combined local regression
tests, 366 fresh boundary tests and 30 browser checks. Weekly financial replay
remains the explicitly conditional extension described above.
