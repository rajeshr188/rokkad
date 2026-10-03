---
status: active
owner: loans
updated: 2026-09-30
tags: [fw-013, form-e, pledge-book, printing]
---

# Form E register, source review and preserved print batches

**Both layouts accepted, 30 September:** the owner requested that users can choose
either two facing portrait A4 pages or a single landscape A4 sheet. The local
preview now offers a Print layout selector. Both use the same evidence projection,
field meanings, permissions and cutoff; only presentation and pagination change.
Facing A4 remains the preview default, including old bookmarked queries. A physical
book now freezes its selected layout on opening; no Workspace-wide setting is added.

The owner selected Form E next after accepting deployment of the statutory notice
workflow. Print either layout single-sided at actual size; file portrait
Left/Right sheets facing, or append landscape sheets individually. Later payments/releases will be handwritten into the
physical entry; normal Rokkad recording remains required. Permanent saved batches
and the daily annotation aid were deployed on 30 September 2026. No real books
were auto-created; physical acceptance and opening scope remain branch decisions.

## Current delivery

**Reports > Statutory forms & notices > Pledge book (Form E) preview** selects a
licence, all or one series, loan-date range, activity cutoff and print layout. The
PDF button submits the current form values, including a newly selected layout.
Blank numeric prefixes display as No prefix. Facing pages repeat the full pledge number. No loan
numbers or business records change. PDF export also requires `data.export`.
All reads require matching Workspace context and normal data-view authority.

The bound is 100 entries per preview; exceeding it requests narrower filters,
never silently truncates. At most five ordinary entries fit one facing pair
(42 mm minimum row height) or one landscape sheet (27 mm minimum row height).
Landscape uses narrower columns; long particulars can reduce its entry count.
This is a trial capacity, not a final book setting. Long rows use more space and,
when necessary, continuation sheets or aligned facing pairs. An evidence appendix
uses the selected orientation too. Original filenames and sample
fixtures contain no customer information; fictional Tamil particulars are included
in the sample to check font shaping.

This is a current working projection, not an as-known-at-the-time reconstruction:
activity is filtered by business date using records available now. The preview creates no
permanent page numbers, stored PDFs or printed/filed acknowledgements. No language
choice is offered yet: headings are English and source text supports Tamil.

## Permanent books and review workflow

**Form E books & daily activity** opens the separate persisted workflow. One book
belongs to one series; licence-wide/all-series selection stays a read-only report.
Opening requires an administrator, physical sample acknowledgement, start date,
first physical page, label and earlier paper-book reference. Both layouts are
supported; book scope and layout are immutable. Up to five ordinary entries is
the default; shared measured pagination preserves long rows/continuations.

The pending queue excludes already assigned loans, orders by evidenced business
date/number and processes at most 100 entries with the total count visible. Full
mode closes groups where the next entry cannot fit and leaves the final partial
group pending; partial mode includes it. The UI recommends closing outstanding
partial pages during daily work rather than waiting for a full page.

Each row needs an administrator source review. It binds an original-evidence hash,
source reference, assessment and optional missing-particular supplements. Known
frozen fields cannot be overwritten. Composite article fields retain original text
and add identified supplements. Unknowns can remain explicitly unknown after review;
they and their follow-up remain in the PDF evidence appendix. Reviews do not certify
complete coverage. Unsupported origins/renewals and ambiguous/reversed payout
attempts remain blocked pending dedicated reconciliation. Loan events and Party
records are not edited. A changed original projection makes the review stale.

Finalisation checks administration, export and business-write authority; locks the
book and selected loans; recalculates the review digest; and rejects stale inputs.
It preserves the exact PDF, snapshot/hash, renderer version, actor/time, cutoff and
per-entry physical page range. Facing sheets consume two numbers per ordinary
pair; landscape sheets consume one. Continuations consume further numbers; the
evidence appendix does not. Retries return the existing batch; changing the request
or reusing an old selection with a different key cannot allocate it again.

`0030_pledge_book` adds four directly Workspace-owned models with forced RLS:
`PledgeBook`, `PledgeBookReview`, `PledgeBookBatch`, `PledgeBookEntry`. SQL triggers
reject update/delete and cross-parent links, serialize consecutive page ranges,
and reject gaps/overlaps; unique loan links prevent duplicate book entries. The
batch artifact is retained, private and registered as issued documents in storage
inventory (14 FileFields). Exact reprints verify its SHA-256; missing/damaged
files fail instead of regenerating. A failed command compensates only its newly
written artifact. Recovery remains necessary for storage/outer-transaction failures.

The daily list filters by recorded date (default) or actual business date, shows
both, detects late entries, and supplies saved book references, original loan date,
payment breakdowns, partial/full release distinctions, known recipients and
reversal/renewal warnings. It marks events already captured at the saved cutoff.
Entries predating the digital book point staff back to the earlier paper reference.
The read-only browser-print list is bounded to 500 events; narrower dates are required
above that. No mandatory annotation acknowledgement or automatic filing is added.

See the [staff guide](../flows/form-e-pledge-book.md) and
[decision](../adr/2026-09-30-form-e-preserved-print-batches.md).

## Published form and evidence mapping

Reference: [CRA's published Rules, Form E on PDF pages 21–22](https://www.cra.tn.gov.in/tnscs/Files/act/003b_Tamil%20Nadu%20Pawnbrokers%20Rules%201943.pdf).
Preserve the field meanings and distinguish subsequent payment/redemption entries.
The supplied photographed ledger is a layout reference, not a source of loan terms.
Current legal consolidation, reviewed Tamil headings and physical filing acceptance
remain separate from code validation.

| Particular | Implemented source / visible limitation |
| --- | --- |
| Pledge identity and date | Frozen approval number plus actual disbursal event date, or validated imported original date/number; leading zeroes retained |
| Pawner identity/address | Matching approval's first official ticket snapshot, or retained completed import identity/address with source-snapshot date and explicit pawning-day limitation. No mutable Party fallback. Missing/ambiguous evidence is Not recorded |
| Original advance | Gross disbursal snapshot or original imported item principal, never current outstanding balance |
| Interest terms | Frozen per-item monthly rates, falling back to frozen approval rate; mixed rates remain separate |
| Every dated payment | Individual repayment, release receipt and auction recovery events, principal/interest/fee split; concessions are separate and never counted as cash |
| Articles and weights | Frozen approval or reviewed opening articles; quantity, gross/net weights, unknown values explicit |
| Original article value | Approved appraisal, or imported valuation only when dated on original pawning day. A cutover valuation is not silently relabelled original value |
| Agreed redemption time | Native approval tenure, or recorded legacy tenure from matching accepted input. Missing-maturity owner assumptions are not labelled recorded original tenure |
| Redemption/sale | Dated release/auction events; reversals marked, original trace retained |
| Owner other than pawner | Not recorded; no assumption of ownership from borrower identity |
| Actual redeemer/buyer | Batch collector or auction buyer when recorded; recipient address remains unknown, not borrowed from today's Party profile |

Advance-interest/fee deductions are noted separately, not invented later payments.
Renewal events are flagged and are not represented as cash receipts or physical
redemption. Multiple disbursal attempts and reversals require review before a
permanent entry. Loans with unsupported origination evidence receive an explicit
gap row instead of substituted current facts. Legacy archived closed-loan claims
have no normalized licence/series link: show their Workspace-wide excluded count.
The preview is not a claim of complete historic book coverage.

## Remaining acceptance and rollout

1. Review physical prints of both fictional A4 samples for binding margin,
   text size and handwriting. Confirm the default capacity; never shrink or clip
   content to satisfy a nominal entry count.
2. Resolve original-identity/owner/recipient evidence capture, imported closed-record
   licence/series mapping and renewal/partial-handover coverage before claiming
   complete Form E output. Preserve provenance for reviewed corrections.
3. Add reviewed Tamil headings/wording, later volume/rollover handling and any
   evidence-backed correction workflow needed for unsupported cases. Existing
   stored pages and exact PDFs must never be changed to accommodate these additions.
4. Rollout completed on 30 September: private backup, owner migration
   `0030_pledge_book`, restricted runtime grants/RLS, private reads, live previews
   and cleanup-operator rebase passed. See [Status](../STATUS.md). Next select
   real book opening dates/page numbers and earlier paper references with each
   branch; no books were auto-created and historical completeness is not claimed.

Implementation: `models/pledge_book.py`, `services/pledge_book.py`,
`selectors/pledge_book.py`, `selectors/pledge_activity.py`, `documents/pledge_book.py`,
`forms_pledge_book.py` and `web/pledge_books.py` in Loans; `web/pledge_book.py` keeps
the read-only report. The renderer accepts projected evidence and performs no
database queries. Existing permissions and dependencies are reused.
