---
status: accepted
owner: loans
updated: 2026-09-30
tags: [loans, form-e, printing, evidence, fw-013]
---

# Form E pages are preserved print evidence, with handwritten later updates

The owner accepted both A4 layouts and the next increment: permanent page numbers,
saved full/partial batches, exact reprints and a daily annotation aid. Form E was
deployed on 30 September after owner migration, runtime isolation, private reads
and live preview checks. Opening actual books remains a branch administrator action.

One immutable `PledgeBook` belongs to one licence's series. Opening records its
physical label, layout, start date, first physical page and earlier paper-book
reference. All-series reporting remains a preview only. This avoids overlapping
licence-wide and series-specific books. The opening form requires acknowledgement
of the physical sample, scope and handwriting space. Layout cannot change after
opening; later volume/rollover operations require a separate explicit design.

Each landscape sheet has one permanent page number. Each facing portrait sheet
has its own number, so a pair consumes two. Evidence appendix pages are not book
pages. The nominal capacity is five ordinary loans per sheet/pair; shared measured
pagination determines whether the next entry fits. Whole long entries continue
across sheets in the same batch. Full-page mode leaves the final underfilled group
pending; partial mode closes it visibly. Preview allocates nothing.

`PledgeBookReview` appends an administrator's original-source reference, assessment
and missing-field supplements. It is bound to the original projection's digest;
changed original evidence invalidates it. Known frozen facts cannot be overwritten.
Mixed article fields retain their original text and append identified supplements.
Unknown facts may remain unknown only with an explicit signed-in review and notes;
review is not a completeness certification. Unsupported origination/renewal mapping
and ambiguous disbursal attempts remain blockers rather than invented facts.
No financial balances, Party profiles or loan events are changed by a book review.

Finalisation requires administration, export permission and business-write access.
It locks the book and selected loans, recalculates the reviewed fingerprint and
rejects stale confirmations. `PledgeBookBatch` retains actor/time, scope, renderer
version, snapshots/digest, original private PDF/hash and permanent page interval.
`PledgeBookEntry` links each loan exactly once to its batch and physical page range.
Identical request retries return the original batch; changed requests fail. A second
request key cannot allocate the same reviewed queue after the first succeeds.
The database additionally serializes page allocation and rejects gaps/overlap,
foreign parent/series links, duplicate loan entries, and updates/deletions.

All four tables have direct Workspace ownership, forced RLS and registry coverage.
The batch FileField is retained, excluded from automatic cleanup and classified as
issued documents in storage inventory. Downloads resolve the Workspace and export
authority, verify the stored hash and return no-store bytes. Missing or damaged
artifacts require recovery; the application never silently re-renders a reprint.

Daily activity is a current read-only, printable aid, filtered by recording date
(default, to find late entries) or actual business date. It includes amounts,
partial/full release distinctions, available recipients, reversals and renewal
warnings, plus saved page references when present. Earlier paper entries remain
outside digital allocation and use the opening reference. No acknowledgement per
annotation, automatic physical filing claim, printer integration, or routine page
revision is introduced. Handwriting is not part of the saved PDF.

Archived closed-loan mapping, unsupported renewal/origination reconciliation,
reviewed Tamil statutory headings and physical/legal acceptance remain explicit
limits. The new review path does not invent historical completeness. See the
[staff guide](../flows/form-e-pledge-book.md) and
[implementation](../implementation/form-e-pledge-book.md).
