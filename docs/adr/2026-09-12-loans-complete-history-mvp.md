---
status: accepted
owner: project
updated: 2026-09-12
tags: [loans, portability, mvp]
---

# Bounded complete-history Loans portability

The owner authorized proceeding with both active and historical Loans after Party
portability closeout. This decision selects the scope; it does not claim a released
importer or authorize missing-evidence reconstruction.

Use FLEXIBLE_PARTIAL_PAYMENT with NONE amortisation, FLEXIBLE payment frequency
and REDUCE_PRINCIPAL, covering complete disbursal/repayment/accrual histories and
an optional evidenced full release. ACTIVE and CLOSED are both outcomes. Reject
unsupported connected events rather than silently truncate histories. Opening
positions, reversals, capitalization, renewals, auctions and installment products
remain later profiles. Preserve original financial facts and source actors without
inventing live actions, accounts or official document issues.

Reuse destination setup through explicit compatible mappings; preserve source
numbers as aliases and use the previously proposed separate historical numbering
namespace. A Loans-owned historical command is necessary because native commands
use current dates/quotes and allocate new numbers. The command must reconcile
canonical balances, obligations, tranche and custody evidence atomically and leave
active imported loans serviceable through native commands.

Read-only inspection found absent immutability triggers on six core evidence
tables. Characterize and close the relevant database protection gaps before adding
historical writes; no disabled triggers, owner-role runtime or blanket mutable-model
lockdown. This prerequisite is now addressed by the
[evidence guard follow-up](2026-09-12-loans-history-evidence-guards.md).

The [bounded contract](../contracts/loan-history-mvp.md) records required evidence,
source mappings, acceptance gates and the immediate implementation step. The
[existing roadmap](../plans/data-portability.md) remains the architectural baseline.
No wire schema, migration or historical import command is released by this decision.
