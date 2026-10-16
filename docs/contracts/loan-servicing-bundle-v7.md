---
status: active
owner: project
updated: 2026-10-16
tags: [loans, portability, corrections]
related: [loan-servicing-bundle-v6.md, loan-agreement-correction-v1.md]
---

# Loan servicing bundle version 7

`loan-servicing-bundle/7` retains agreement financial corrections without changing
published versions 1–6. Like versions 5 and 6, it wraps the explicit underlying
financial profile 1–4 and maps all retained/current Party identities. It supports
the version-6 collateral evidence as well.

The fixed underlying row inventory and field definitions stay the same except:

- `PawnLoanDisbursalSnapshot.basis` additionally accepts `CORRECTED`.
- `PawnLoanInterestAccrual` additionally requires positive `agreement_revision`.
- `PawnLoanEvent.event_kind` additionally accepts `OPENING_CORRECTION`.

Version-7 export is mandatory when the graph contains a corrected native
disbursal or checkpoint correction. Old profiles refuse this evidence, including
attempts to disguise agreement correction metadata within otherwise old rows.

Native snapshots preserve the previous disbursal/event and genuine approval
references, revised tranches, actor, reason, source reference and request identity.
Their policy remains the original captured policy. Monthly revisions reference an
existing corrected agreement. Every original event/snapshot/accrual remains in the
source graph; compensation does not erase or manufacture a cash transaction.

Checkpoint correction preserves one original opening and a complete ordered
before/after chain. Source-local validation checks the preceding hash/amounts,
item mapping, original identity, frozen-rule constraints and corrected review.
Restore remaps explicit event/item/Workspace/Party references and recomputes the
preceding local opening hash. The original source packet and original hash remain
available in the immutable retained portable document. No pre-cutover history is
inferred. Remaining obligations retain their actual correction-event source.

Preview restore inserts and reconciles the ordinary guarded graph inside rollback.
Confirmed restore uses restricted Workspace authority and new local identities;
it is distinct from exact owner-only recovery. Current positions must reconcile
after restoration, and re-export must preserve the revised financial semantics.
Original issue artifacts and source claims remain retained rather than relabelled
as newly performed business actions.

Loans migrations 0079/0080/0081 and portability migration 0029 are required in addition
to the preceding collateral migrations. After new evidence exists, retain
compatible web/worker readers and stop new writes instead of downgrading it.
