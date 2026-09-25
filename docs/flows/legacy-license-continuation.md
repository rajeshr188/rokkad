---
status: active
owner: project
updated: 2026-09-25
tags: [loans, migration, cutover, setup]
---

# Continue lending in imported licenses and series

Use **Loan setup → imported license → Verify for new lending**. This is a cutover
operation for a setup administrator, not an import shortcut or a normal renewal.

1. Finish the final frozen data import and reconciliation while source writes and
   destination business access remain closed. Include all three workspaces and
   media. Record the final dump hash and reviewed numbering report.
2. Check the actual license document against the displayed license number. Supply
   its current validity and issuing authority and upload PDF/PNG/JPEG evidence.
   If the imported number is only a grouping label, configure separate verified
   setup instead; do not invent a legal identity.
3. Review every loan and release sequence. Enter the numeric part of the last-used
   counter, including closed, cancelled, excluded and reserved numbers. The form
   shows prefix, width and existing reservation floor. For a genuinely unused
   sequence the reviewed last-used counter is zero. No values are assumed for you.
4. Confirm final-source completeness and submit **Verify and enable new lending**.
   A stale review requires a reload and fresh check. Re-select the document after
   validation errors. Prefix conflicts or exhausted ceilings need a reviewed
   numbering decision, not a counter reset.
5. Inspect the new regulatory revision and its numbering review, then the normal
   setup checklist. Existing series stay attached to this license. New loans use
   the verified revision and next reserved number; old loans retain their original
   revision, opening balances and servicing history.

The ordinary form records an attestation; it cannot freeze Linode or independently
verify the source hash/report. It requires the actual licence document before
activation. The explicit owner-authorized document deferral below is a separate
path; it has been used for the four production licences in this cutover.

An explicit Workspace-owner document deferral is also supported through the
operator service. It creates an **Owner attestation (document pending)** revision
without a substitute attachment, retaining the complete source and numbering
review. It enables lending under the owner's stated validity and leaves a visible
upload reminder. Use **Edit** to add the original document later; this appends an
amendment and preserves the attestation. Ordinary **Verify for new lending** still
requires its document. See the
[owner-attestation decision](../adr/2026-09-25-owner-attested-license-continuation.md).

## Print copies of imported loans

On an imported opening loan's details page, choose **Print imported loan copy**.
It uses the current assigned ticket template and paper profile with the frozen
source loan number/date, original item principals, rates and collateral facts.
Customer contact details/photo and printed business details use their current
records. Recorded source quantities print beside collateral descriptions; missing
counts are omitted. Unknown historical appraisal/photo evidence is not invented. Every page
has a small **Reprinted from imported records** footer, without the large preview
watermark. This is a reconstructed copy, not a saved original official issue.

**Preview imported ticket PDF** remains available with its explicit preview
watermark for layout checks. Neither action approves or disburses a loan, consumes
a number, saves an official ticket or changes its balances. Archive-only historical
records are outside these opening-loan routes.

The new-loan series picker shows the licence and number prefix (including **No
prefix** for numeric-only registers). Internal LINODE migration codes and sequence
counters are preserved.

## Calculation, fee and monitoring setup

The setup page has separate expandable forms and saved history. Calculation opens
first; the failed form or selected monitoring amendment opens automatically.
Each save changes only its policy family. Fields have linked corrections and
English/Hindi labels, and remain usable without HTMX or JavaScript.

- Calculation groups scope/date, monthly interest, part-month/compound rules and
  collateral valuation/rounding. Ratios use decimal notation; the page explains
  which controls apply only to slab or compound rules.
- Fees show how fixed amounts and percentages are entered, and whether a charge
  is deducted at payout. Starter values are suggestions until saved.
- Monitoring groups maturity/overdue warnings and collateral/evidence thresholds.
  It does not change economics. Amend through saved history to retain old versions.

Existing policy service validation, audit, permissions, effective-date rules and
frozen loan economics remain authoritative.
