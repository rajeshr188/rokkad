---
status: active
owner: loans
updated: 2026-09-22
tags: [loans, documents, templates, ux, experiment]
related:
  - ../adr/2026-09-22-ticket-template-authoring-experiment.md
  - loans-configurable-documents-plan.md
  - ../flows/loans-document-layout-operator-guide.md
---

# Client-managed ticket template experiment

## Outcome and boundary

Clients can reproduce their stationery through an ordinary visual template/frame
editor, duplicate a template, and change it without JSON or developer assistance.
JCL and JSK are concrete acceptance examples of the same general-purpose editor,
not branch-specific rendering code. The owner authorized an isolated experiment;
merging into `rls-mvp` requires their acceptance of the result.

Feature branch: `feature/ticket-template-designer`.
Baseline: `8b0e1ba3`, also named
`checkpoint/rls-mvp-before-ticket-designer-20260922`.
The original checkout remains on `rls-mvp`; feature files live in
`.worktrees/ticket-template-designer`. This first slice is design documentation
only. No renderer, schema, runtime setup or saved template has changed.

## Evidence and acceptance examples

Read-only inspection of production commit
`4312573fa2dca9f8bea3abd1ab84aadb5bd1e1cd` and the owner's September 21 dump found:

| Example | Existing configuration | Required successor behavior |
| --- | --- | --- |
| JCL | Default `jcl_loan`; Original `org.pdf`, Duplicate `dup.pdf`; `BA` | Complete Original/Duplicate on A4 landscape, printed on plain paper |
| JSK | Default `jsk_loan`; no backgrounds; `BS`; different positions per copy | Two A5 data-only pages, Original then Duplicate, aligned to preprinted stationery |

JCL also stores Terms and D3 assets, but `BA` does not print their backs. Preserve
the distinction between saved assets and selected output. Recheck settings at
implementation time because production remains live. Production UI review reached
a fresh JSK loan's Print action; a Chrome extension blocked PDF visual inspection.
Neither visual parity nor physical printer acceptance has been established.

Production frames already provide customer/contact/relationship text, customer
and collateral photographs, amounts in words, QR, descriptions, weights and
separate Original/Duplicate positions. Reuse reviewed assets and coordinates
where possible; never put borrower data, photographs, credentials or production
PDFs into Git. Legacy coordinates use bottom-left centimetres with decimal
precision; current overlays use top-left whole millimetres. Conversion must
account for origin, units, rectangle height and legacy frame padding.

## Proposed operator journey

1. Open **Ticket templates** and create or duplicate a template.
2. Choose **Plain paper** or **Preprinted stationery**, paper size and copies.
3. Select Original, Duplicate or optional back tabs; upload an optional PDF/image
   background. A stationery guide may be shown for positioning without being
   printed. Do not require an artificial blank PDF for data-only output.
4. Add fields, text, photos, collateral information, QR and signature spaces.
   Drag/resize or use keyboard-accessible position/size controls and fine nudges.
   Touch users must have a non-drag editing path. Show overflow clearly.
5. Preview a selected representative loan and test-print. Preview remains marked
   and does not issue a business document. Explain actual-size printer settings.
6. Select **Use this template**, choosing workspace scope by default with existing
   license/series targeting available when needed. Show the resolved paper/copy
   settings before activation.

Saving keeps a draft. Editing an active template creates a new draft without
modifying its published revision. Activation composes the existing layout/profile
publication and assignment services while retaining their authorization and audit.
Normal staff continue using the loan's Print action. The editor must provide
English/Hindi controls; uploaded Tamil artwork remains intact. Dynamic regional
text needs separate visual validation, not merely a successful PDF-byte test.

## Required frame capabilities

| Capability | Bounded requirement |
| --- | --- |
| Content selection | Allow-listed loan/customer fields; literal text remains separate from financial values |
| Field appearance | Value-only or label-and-value; editable presentation labels without changing meaning |
| Customer information | Name, relationship, address and contact selected through Party-owned rules |
| Photos | Authorized loan/customer media, defined selection and missing-photo behavior |
| Loan information | Number/date, principal, amount in words, terms and required collateral details |
| Copies | Original, Duplicate or both; independent positioning where required |
| Geometry | Precision sufficient for legacy coordinates, bounded page rectangles and printer alignment |
| Overflow | Readable wrapping/shrinking or a clear blocking error; no silent loss of customer/collateral information |
| Stationery | Optional printed background; guide-only artwork must never leak into the data-only print file |

Use current layout blocks as the frame representation. Do not add a parallel
`LoanTemplate`/`TemplateFrame` model hierarchy or reintroduce Girvi imports. Keep
the existing renderer/issuance pipeline and fixed/Flow support. Reuse Django
forms, native partials, HTMX and existing Bootstrap patterns.

## Decisions to resolve before renderer changes

- Define which business fields must appear, and which audit identities belong in
  stored evidence instead of the visible ticket. Existing validator requirements
  remain effective until explicitly revised and tested; static stationery must
  not silently bypass required business information.
- Define the source and snapshot timing of customer details/photos so a later
  Party edit cannot silently change an issued document. Never substitute current
  loan balances or appraisal values for approved contract evidence.
- Define a compatible schema extension for optional backgrounds, value-only
  fields, fine coordinates and media bindings. Preserve published v1/v2/v3
  definitions, assignments and historical artifact reads.
- Define how preprinted output is represented in issue evidence. Keep the exact
  data-only print bytes and relevant stationery/version references. A complete
  proof preview is optional; a second official artifact is not required merely
  to begin the experiment and must never silently replace an issued file.

## Delivery order

1. Design slice (this commit): scope, journey, capabilities, isolation and gates.
2. Inventory/review existing template assets and positions, map supported/missing
   fields, and prepare synthetic acceptance examples; confirm the small schema
   and evidence decisions above.
3. Implement only missing overlay/data capabilities and their boundary tests.
4. Simplify authoring/activation in one editor over existing services; keep JSON
   optional for advanced maintenance, unnecessary for the supported user journey.
5. Reproduce both examples, test permissions/reprints/compatibility, then conduct
   owner visual and physical printer acceptance before proposing a merge.

## Isolation, fallback and merge gate

- Use a separate feature database, media root/private object prefix and web port
  before runtime experimentation. Do not copy rehearsal/production credentials
  or start against their database by default. Keep existing servers on their
  original checkout. No feature runtime environment is provisioned by this plan.
- Use ordinary owner-only migrations if needed; web/workers retain restricted
  roles and forced RLS. Never run experimental migrations on the accepted
  rehearsal or production. Git branches do not isolate databases or media.
- Preserve layout/profile immutability, scope checks, source evidence, hashes,
  exact-artifact reprints and compatibility with existing published documents.
- Verify cross-workspace read/write/media denial under restricted roles and
  unchanged financial/lifecycle/custody behavior.
- Match JCL plain-paper output and JSK preprinted positions, copy order, Tamil
  artwork and photos. Test long names/addresses, multiple collateral items,
  missing photos and printer margins using synthetic records.
- An owner must be able to duplicate and alter a template without JSON, preview,
  activate it and produce a new issue; old issues must retain their original bytes.
- Merge only after owner acceptance and appropriate regression checks, with a
  reviewed migration/asset rollout if required. A saved PDF is not evidence of
  a physical signature or successful paper printing.
- If rejected, retain or archive the feature branch and continue using the
  original checkout/checkpoint. No reset or data restoration is needed there
  while the isolation rules hold. Do not delete feature evidence automatically.

## Non-goals

No second printing engine, loan-domain rewrite, general-purpose publishing tool,
arbitrary executable template expressions, production cutover, new direct-printer
service or expansion of receipt/release design features in this first experiment.
Existing receipt/release printing must continue working. Additional composition
features require an observed client need.
