---
status: accepted
owner: project
updated: 2026-09-30
tags: [portability, evidence, corrections, party]
---

# Complete retained import projections without rewriting history

The import audit found accepted piece counts absent from a newer operational
column, and retained borrower/address/tenure evidence unused by the working Form E
reader. The owner authorized the bounded corrections on 30 September.

## Decision

New opening imports populate the validated quantity. An explicit Loans service
can fill a null quantity on an existing imported opening, including after release.
It requires the matching Workspace context, setup-administration and data-import
permissions, active business-write access, the expected origin hash and exact
agreement with the frozen opening event and item identities. It locks the loan
and items, refuses contradictory non-null values, audits each changed loan and is
idempotent. It changes no financial/custody field, event, original document or PDF.
This is a nonfinancial projection repair; owner-only financial history admission
and its authorization are unchanged. Existing administrators with both named
permissions can perform this bounded repair without impersonating another owner.

An internal Data Portability reader exposes only identity/address particulars
from completed import rows and recorded tenure from matching accepted loan input.
Loans remains responsible for authorizing the report; the reader independently
requires matching Workspace context and bounds each call to 100 loans. It does
not select current Party values, guess among multiple source identities/addresses,
or promote an owner maturity assumption to recorded original tenure. The report
labels the identity as source-snapshot evidence, not proof of pawning-day details.
Missing evidence stays unknown; permanent source-review and print gates remain.

Ordinary customer status and contact/address default changes now record the
authenticated actor, affected object, before/after status or flags, and timestamp
in the existing AuditLog in the same transaction. Demoted defaults and deletions
are included. No phone number/address text is copied into these audit entries.
The eight old changes remain unattributed; this does not invent retrospective actors.

The unused JCL unnamed-series repair composes existing configuration/reservation
services under locks and preserved source evidence, retaining the empty prefix,
all used numbers and the existing ceiling. It neither renumbers loans nor creates
a new register or payout. No general new migration framework or schema is needed.
