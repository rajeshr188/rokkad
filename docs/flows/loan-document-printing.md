---
status: active
owner: project
updated: 2026-09-08
tags: [flows, loans, documents, printing]
related: [../STATUS.md]
---

# Custom loan documents: operator entry point

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
