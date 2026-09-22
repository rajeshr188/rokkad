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
`.worktrees/ticket-template-designer`. The initial design and mapping slices are
complete. The first implementation adds the bounded precision overlay foundation
described below; it does not alter existing published layouts.

## Implemented foundation and isolated checks

Contact/photo evidence is now implemented for precision v4 tickets. First issue
uses payload v2 and migration 0016's nullable, immutable source snapshot; historical
rows stay null. Concurrent first prints serialize on the loan; saved PDFs are
returned before mutable facts/media are rebuilt. Ambiguous addresses require
selection; unavailable approved photos fail closed. Dynamic photos and customer
values are excluded from layout exports. The test launcher includes restricted
database guards and real concurrent-connection issuance checks (155 checks).

The next completed slice brings the suite to 159 checks: V4 business coverage is
separate from optional printed audit IDs/verification text, while full internal
payload/issue evidence remains required. The existing admin Evidence page now
exposes captured fields, photo evidence and issuer; loan print actions link to
ticket history. Stored PDF reads verify checksums before serving. Static-stock
declarations and paired activation remain pending.

Run `python scripts/review_ticket_frame_mapping.py` to regenerate the synthetic
HTML positioning aid and non-importable candidate definitions in
`outputs/ticket-template-tests/frame-review/`. No database or media credentials
are needed. It reports existing visible-evidence conflicts rather than changing
the client design to satisfy them. Real artwork, copy-aware editing, reviewed
static-stock coverage and paired activation are the remaining implementation
work before JCL/JSK visual/physical acceptance.

Create **Loan ticket > Exact PDF overlay** and select **Use precision ticket
overlay** to opt into v4. In the existing visual overlay editor, backgrounds are
optional; fields offer label/value or value-only display and an optional custom
label. X/Y/width/height accept 0.1 mm increments. Numeric inputs and drag positions
share that precision. Blank backgrounds produce data-only output; selected
backgrounds are printed with plain-paper profiles. For preprinted stationery,
profile v2 omits backgrounds from print output and shows them only in Design
preview. The editor selects a local draft/published profile for testing, or uses
the sample loan's assigned profile. Print preview/Test print use the actual stock
policy. Design previews are explicitly watermarked and cannot create an issue.
Text frames accept padding (0-24 pt) and explicit leading (6-48 pt, at least the
font size) in 0.1 pt increments; blank leading retains automatic spacing. Legacy
text frames use 6 pt padding and 12 pt leading. Explicit line breaks are escaped
text, not executable markup.

V1/v2/v3 retain their validation and canonical definitions; v3 remains the default
creation format. V4 currently accepts loan-ticket overlays only. Required
business fields and copy validation remain enforced; verification stays mandatory
in internal evidence, optional on v4 paper. No database
migration or issue snapshot extension is needed for these controls. Profile v1
retains its canonical definition and behavior; profile v2 makes stock explicit.

From the feature worktree, run the focused renderer, persistence, issuance,
profile and setup UI checks with:

```powershell
& ..\..\.venv314\Scripts\python.exe scripts/test_ticket_templates.py --env-file ..\..\.env
```

The launcher explicitly reads local development connection settings, requires a
loopback database host, and pins Django's test database to
`test_rokkad_ticket_template_feature`. Test setup uses owner-backed test settings;
it is not a web runtime configuration. It keeps synthetic filesystem media under
`outputs/ticket-template-tests/media`, uses memory email and preserves the test
database for subsequent runs. That output directory is ignored by Git. No env
file, production media or customer fixtures are copied into this worktree.

Synthetic checks include PDF coordinates, A5 actual-size copy positions, optional
background ownership, UI save/preview/publish/issue and byte-identical reprints
after replacement. Synthetic rendered images were inspected with MuPDF. No live
feature browser/server, full adversarial RLS rerun, Tamil artwork comparison or
physical printer acceptance is claimed. Provision a distinct runtime database,
restricted role configuration, media root and port before manual app testing;
do not launch this branch using the rehearsal environment.

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

## Selected decisions before renderer changes

Selected for this experiment in the
[frame mapping and implementation contract](../implementation/ticket-template-frame-mapping.md):

- Layout v4 adds optional backgrounds, value-only frames, decimal geometry and
  dynamic photo bindings; v1/v2/v3 retain their behavior.
- Profile v2 distinguishes plain/preprinted stock. Guides are optional and do
  not enter the data-only official PDF. Preserve one exact official artifact.
- Ticket payload v2 uses approved economics/collateral/photo evidence, plus
  Party details captured at first issue. One nullable immutable snapshot on the
  existing issue records the additional evidence; no parallel history model.
- V4 visible business requirements are separate from internal IDs/hashes.
  Reviewed fixed artwork/stock values must match the loan's authoritative facts.
- Initial paired activation targets Workspace or Series, matching existing
  profile scopes. Existing license overrides remain supported outside this
  simplified action; no implicit scope expansion.

The source inventory covers 12 JCL and 23 JSK frames. Differences in live
valuation, license-name semantics, quantity and one out-of-bounds JSK frame are
explicit acceptance findings. Actual artwork and paper calibration remain
pending. These are implementation targets, not changes to current validators.

## Delivery order

1. Complete: scope, journey, capabilities, isolation and gates.
2. Complete for source configuration: 35 frame mappings, candidate coordinates,
   missing capabilities and engineering decisions. Defined synthetic test cases;
   actual media inventory/visual review and executable fixtures remain pending.
3. In progress: optional backgrounds, value-only/custom-label fields, precision
   geometry, stock profiles/guides, text padding/leading and isolated checks are
   implemented, together with dynamic media/source evidence and first-issue
   serialization. Image/QR fit refinements and reviewed static-stock declarations
   remain before full JCL/JSK reproduction.
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
