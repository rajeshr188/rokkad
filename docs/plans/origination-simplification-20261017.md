---
status: active
owner: project
updated: 2026-10-17
tags: [loans, origination, corrections, plan]
related: [../adr/2026-10-17-origination-review-and-safe-recovery.md]
---

# Origination simplification

Owner-approved implementation in `work/origination-simplification-20261017`,
isolated from pending closing and WhatsApp work. Base `ed585f33`.

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
offline desktop/mobile captures. No live customer/setup changes or deployment.
Formatter-only differences must be reviewable separately from behavior changes.

Local delivery is complete for the owner's confirmed monthly business scope:
368 regression tests, 88 final focused tests and 18 offline page/viewport checks
pass, with quality/documentation/isolation/recovery evidence in the implementation
record. Integration with the independent closing candidate, commit/push and
production release have not been performed.
