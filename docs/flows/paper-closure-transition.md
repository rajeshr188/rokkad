---
status: active
owner: project
updated: 2026-10-08
tags: [loans, staff-guide, release]
---

# Close loans now or record completed closures

Open an active loan and choose **Close / release loan**. Choose **Collect payment
and return collateral now** for business happening now, or **Record a settlement
already completed** for a paper/outage transaction. Origination source does not
restrict this choice. Standing entry preferences supply the initial selection;
loan-level Rokkad-only capture and an effective Workspace recording commitment
favor current action. Changing the choice does not post anything.

Current action reviews today's exact settlement and collateral, then confirms
collection and handover together. For one combined payment covering several loans,
use **Release multiple loans** (up to 20). Do not record the same settlement twice.

For a completed individual closure, enter the actual closing date, settlement and
optional source reference/original closing number. If no original closing number
exists, leave it blank: Rokkad assigns a labelled recording number. Review the
financial split before confirmation. Choose what the source actually establishes:

- **Settled; cash and handover unspecified** clears reconciled debt, leaves customer
  return unconfirmed and preserves last-known storage for investigation. Later
  evidenced handover does not collect another payment or rewrite the original.
- **Cash received and all collateral returned** requires payer and recipient facts.
  Another recipient needs relationship and authority-to-collect evidence. The actual
  return date is retained; an exact time is not invented.

For several independent completed settlements, choose **Completed closures** in the
sidebar. Select up to 50 loans sharing one actual closing date. Each row retains its
own settlement, evidence basis, optional closing number and source reference.
Calculated amounts and suggested names must be checked against the source; they
are not historical evidence. Expand details for confirmed-return facts, different
references and authorized interest concessions. Select ready rows and confirm.
Every selected row saves or none does; unselected rows retain their inputs on this
screen. Leaving the page discards unsubmitted entries.

Bulk quotes expire after ten minutes; individual reviews expire after one hour.
Changed loan activity or review facts require review again. Identical successful
retries return the existing record. Corrections/reversals retain original evidence.
Interest concessions require settings-administrator authority and an explicit
reason. Settlement plus concession must reconcile exactly: principal, capitalized
interest and fees cannot be waived, and excess collections are not silently interest.
Existing correction profiles retain their limits; a concession-bearing settlement
cannot be rewritten through a correction profile that cannot represent its loss.

Blocked rows explain missing setup, interest recognition, financial activity or
chronology. Use the actual date; resolve the blocker instead of substituting today.
Imported openings require closure after their checkpoint. Legacy native contracts
retain completed-period finalization; supported modern contracts prepare their
eligible charges through the canonical settlement writer.

History, individual PDFs and reconciliation CSV distinguish settlement amounts
from established cash/return facts. No customer notifications are sent automatically.
Original batch totals remain after a reversal, with reversed rows labelled. The
CSV is for reconciliation; the connected **loan-servicing-bundle/1** export/restore
retains batch relationships and both evidence bases. Earlier narrow export profiles
retain their existing limits.

## Optional completed-recording controls

The Workspace owner opens **Completed-recording controls**. Leave the date empty
and restriction unchecked for unrestricted ongoing paper/mixed practice. No
retirement date is imposed. A dated operating commitment requires administrator
exceptions for settlements from that date; the all-recording restriction requires
exceptions regardless of date. Earlier backlog otherwise remains available.
These controls apply to both individual and bulk completed closures and are
rechecked under lock at recording. Authorized exceptions retain their reasons.
Clear both controls with a reason to reopen unrestricted recording. Choices are
Workspace-specific and do not rewrite existing records or loan-level book reviews.
