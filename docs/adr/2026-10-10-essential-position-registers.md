---
status: accepted
owner: project
updated: 2026-10-10
tags: [adr, portability, loans, opening, position]
---

# Versioned essential-position register adapters reuse Loans admission

The owner selects PC-03 in the [ordered portability plan](../plans/data-portability-completion-20261010.md).
Extend the existing bounded XLSX/CSV register workflow with two explicit source
templates. Published `outstanding-register/1` retains its unchanged-principal,
upfront-month, aggregate half-even rule.

`outstanding-register/2` captures original/remaining item principal and the actual
current-period base, source quantum, cumulative and current recognized/unpaid
interest, and current advance. Translate these verified facts to the existing
`loan-opening-review/4` contract; do not infer earlier receipts or period bases
from a single remaining balance. Only simple full-month, per-item half-up monthly
continuation with positive initial retained-item allocations is supported. A
fully repaid item still held at cutover is explicitly held: changing the existing
initial-allocation constraint needs separate domain work, without dropping
collateral or fabricating principal. Later repayment to zero remains supported.
Future advance must be explicitly zero in this bounded
spreadsheet; nonzero future coverage requires the existing per-period opening
review, not omitted advance or invented reallocations. Freeze source terms rather
than applying today's Workspace economics to the historical agreement.

`closed-register/1` captures one loan per row, stable source/customer references,
explicit zero principal/interest/fees and confirmed returned custody. Known
original terms are optional; absent original and closure dates, principal, rate
and tenure stay unknown. Use the existing owner-reviewed closed-position command
with `OWNER_CLOSED_POSITION` basis. No automatic vendor release interpretation,
JCL recovery exception, current monitoring policy, price approval or reconstructed
cash event is involved.

Reuse GuidedOpeningBatch, the existing private source rows/hash, explicit Party
bindings, Workspace locks, non-persistent preview, signed confirmation and atomic
batch commit. A source identity cannot acquire a second active/closed origin.
Database guards add only the named source profiles and require each result to
match its corresponding immutable Loans admission profile in the same Workspace.
Existing source/completion immutability and all ordinary Loans guards remain.
Reversing support is refused while new-profile batches are retained.

Closed admission uses ordinary number claims, including their series counter
rules. Active opening retains its existing number behavior. Staff can match an
inactive non-archived customer for closed records; active admission retains the
existing active-customer requirement. Wider vendor mapping, graph/media handling,
volume, complete Workspace transfer and production cohort acceptance remain later
work. This selection authorizes local development, not live data conversion.

See the [checkpoint decision](2026-10-05-reduced-principal-opening-checkpoint.md)
and [position-only decision](2026-10-09-loan-position-import-without-earlier-history.md).
