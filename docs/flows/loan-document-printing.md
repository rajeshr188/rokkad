---
status: active
owner: project
updated: 2026-09-23
tags: [flows, loans, documents, printing]
related: [../STATUS.md]
---

# Custom loan documents: operator entry point

After approval, use the large **Print loan ticket** button directly below the
loan heading. It remains prominent for active loans with approval evidence,
including loans approved and disbursed together. Drafts and imported loans without
approval evidence do not show it. The **Loan documents** card retains ticket
access for other eligible states and reprints. Key facts and repayment
schedule appear when a saved schedule exists, including supported imported loans.
Each PDF opens in a new tab; check customer/loan identity, then download or print
from the PDF viewer. A loan ticket describes approved terms, not proof of disbursal.

The loan's collateral, valuation and history sections are expandable; the Loan
documents card and prominent ticket action remain visible. Release-document
section links open the containing history section automatically.
Printing does not record payment or change the loan's financial state. Existing
document issuance/reprint evidence remains authoritative. Physical printer settings
and paper alignment still need operator acceptance.

Open the Workspace's Settings, Documents & printing, then the Starter guide
on Document layouts. The same guide is linked from layout creation, Assets,
the overlay editor, and print-profile creation/detail screens.

The maintained beginner tutorial is rendered from
`templates/loans/setup/documents/_beginner_guide.html`; advanced reference and
recovery live in `templates/loans/setup/documents/guide.html`. Keep instructions
in the application rather than maintaining a second copy of the full manual.

The tutorial follows this journey:

1. Choose Flow or Exact PDF overlay and create a draft.
2. Prepare a blank form; upload a revision-scoped background asset and select it.
3. Match logical page size, position registered fields in millimetres, save each
   block, and preview representative data.
4. Configure Original/Duplicate fronts and Terms/D3 backs where needed.
5. Publish the layout, create and preview a compatible loan-ticket print profile,
   verify physical output when available, and publish the profile.
6. Assign the layout and profile at the intended scope; use ordinary document
   Print actions and inspect issued evidence. Reprints preserve stored PDFs.

Maintenance checks: new starters are A4; current profile copies occupy A5;
page-size changes do not rescale overlay blocks; dragging requires Save block;
the canvas shows only Original front; multi-page uploads do not auto-map copies;
profile preview needs a published layout and approved sample loan; profile
assignment supports Workspace/Series while layout assignment also supports License.
Printer guidance does not control the driver. Physical acceptance remains separate
from software validation and was deferred by the operator.
