---
status: accepted
owner: project
updated: 2026-08-16
tags: [contact, girvi, notify, notify-v2, party, loans, dea, retirement]
related:
  - 2026-06-18-party-domain-model.md
  - 2026-08-09-girvi-capability-extraction-into-loans.md
  - 2026-08-14-legacy-notify-retirement-boundary.md
  - ../plans/contact-girvi-legacy-notify-retirement.md
supersedes:
  - 2026-08-09-girvi-capability-extraction-into-loans.md temporary Girvi runtime boundary
---

# Retire Contact, Girvi, And Legacy Notify

Date: 2026-08-16
Status: Accepted

## Context

Rokkad now has long-term replacements for three compatibility-era applications:

- `party` is the canonical external and internal business-entity model;
- `loans` is the target operational pawn-loan platform;
- `notify_v2` is the target notification platform.

The legacy `contact`, `girvi`, and `notify` applications still have runtime,
route, template, seed, permission, test, migration, and data dependencies across
the project. Deleting any package before removing its consumers would prevent
Django startup or silently remove accounting, identity, or notification
behavior.

The project is still in development. A fresh development database is therefore
the preferred final schema cutover, but code must remain coherent at each
reviewable phase and must not mutate posted accounting evidence in place.

## Decision

1. Retire `apps.tenant_apps.contact` after all surviving consumers use `party`.
2. Retire `apps.tenant_apps.girvi` after required operational capability is
   either owned by `loans` or explicitly classified as intentionally removed.
3. Retire only legacy `apps.tenant_apps.notify`. Keep `notify_v2` and remove its
   Girvi-specific integrations while retaining its generic delivery platform.
4. Keep DEA as the sole accounting owner. Remove Girvi-specific period-close,
   payment-voucher, seed, and posting-rule behavior after proving that no
   surviving source uses it.
5. Do not dual-write during cutover. Each capability has one write owner.
6. Do not add compatibility shims that preserve retired routes or model names
   indefinitely. Temporary adapters must have an explicit removal phase.
7. Use a clean development database rebuild for final table removal. If a
   database must be retained, stop before destructive schema removal and make a
   separate archive/retention decision.
8. Keep `party`, `loans`, `notify_v2`, and DEA independently testable throughout
   execution.

On acceptance, this decision completes rather than reverses the capability
extraction decision: Loans remains the selected target, while Girvi ceases to
be a runnable capability reference after the retirement gates pass. The earlier
PORT/REPLACE/RETIRE classification and no-dual-write rules remain binding.

## Target Ownership

| Capability | Target owner |
| --- | --- |
| Person/organization identity and roles | Party |
| Customer and supplier operational references | Party |
| Pawn-loan lifecycle and collateral | Loans |
| Lender funding/repledging | Loans only if accepted and implemented; otherwise intentionally retired |
| Generic notification intent and delivery | Notify v2 |
| Voucher, journal, posting, reversal, and period controls | DEA |

## Non-Goals

- Preserve every Girvi feature under a new name.
- Copy Girvi records into Loans without an approved mapping and reconciliation.
- Recreate legacy Notify concepts inside Notify v2 solely for compatibility.
- Rewrite historical migrations in the same change that removes runtime code.
- Delete or mutate posted journals merely because their source application is
  retired.

## Execution Preconditions

Execution must resolve the following before destructive schema removal:

1. whether existing development databases may be discarded;
2. the disposition of Girvi capabilities not present in Loans, especially
   TakenLoan/funding and repledging;
3. that legacy Notify history need not remain available after the development
   database reset;
4. that temporary loss of retired Girvi/contact/Notify URLs is expected rather
   than redirected to misleading replacements.

## Consequences

- The active Party rollout changes from compatibility coexistence to complete
  Contact replacement.
- Girvi event-driven DEA work is cancelled rather than completed.
- Legacy Notify retirement no longer waits for Girvi parity; Girvi producers
  are removed and surviving producers move directly to Notify v2.
- Some existing tests document behavior that is intentionally being deleted and
  must be removed or rewritten, not made to pass unchanged.
- Final application deletion remains gated by a fresh-install migration proof.
