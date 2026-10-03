---
status: active
owner: project
updated: 2026-10-03
tags: [khata, release, validation, pilot]
---


The later [document-navigation checkpoint](khata-document-navigation.md) records the current
local runtime; earlier checkpoint identities/counts below remain dated evidence.
# Khata completeness and release review - 2 October 2026

The later [action-guidance checkpoint](khata-action-guidance.md) records the
locally verified guidance runtime and delivers recommendation six's prerequisites
and draft experience. Opening acknowledgement remains design-only. The
[operational-report checkpoint](khata-operational-reports.md) delivers
cash/custody reporting from recommendation five. The [collection/event checkpoint](khata-collection-worklist.md)
delivers the worklist/readable-event portion of recommendation four below. Optional reminders remain separately queued;
operator/hosted/physical gates and other dated findings retain their boundaries.


The [measured read-performance checkpoint](khata-read-performance.md) superseded
the earlier local runtime identity and addressed the initial eager
source/custody loading findings. Earlier checkpoints/review findings remain dated
evidence; hosted/operator/physical acceptance is still separate.


## Current completeness review

The owner requested a review of feature, workflow, user flow and operations after
the register/detail-tab improvements. This is a source/document/test-evidence
review, not authorization to extend financial rules or activate production.
No application behavior or pilot business records change in this review.

**Assessment:** the agreed first-version financial/custody lifecycle is implemented
in the local candidate. It is suitable for a controlled fictional operator trial.
It is not yet evidenced as ready for real-money operations. Exception handling,
large-holding workflows, collection follow-up and deployment/operator acceptance
are the principal remaining concerns. Avoid a percentage-complete claim: supported
scope, operational convenience and production acceptance are different measures.

At this review, the candidate was `khata-local-20261002-0d22c65edc36`. Its recorded 395 Linux
regressions pass in 183.149 seconds, with desktop/mobile, viewer and no-JavaScript
browser acceptance. This is the selected regression suite, not an assertion that
every repository test or every real-world scenario has been exercised. See the
[tab/usability checkpoint](khata-collateral-usability.md#tabs-verification-and-current-local-identity).
No new application tests are run merely for this read-only review.

The owner subsequently selected [phased improvements](../plans/future-work.md#improvement-delivery-sequence).
The first [exception-guidance slice](khata-corrections.md#exception-guidance-follow-up-2-october)
is delivered locally; recommendations below remain the review baseline.

### Coverage against the agreed scope

| Area | Assessment | Relevant implementation/evidence |
| --- | --- | --- |
| Setup and numbering | Implemented: independent/associated series, permanent workspace-unique numbers, association freeze, ordinary-number preservation | [Account services](../../apps/tenant_apps/loans/services/khata_accounts.py), foundation/concurrency tests |
| Draft, receipt, approval and first cash | Implemented: separate immutable facts; combined optional photo receiving; interest begins on first actual payout | [Opening services](../../apps/tenant_apps/loans/services/khata_opening.py), opening/operator/UI tests |
| Later withdrawals | Implemented: unused entitlement and actual-principal LTV limits, current prices/photo/overdue/lending checks | Opening/calculation/concurrency tests |
| Interest | Implemented: monthly rate independent of payment frequency; anniversary dues, simple interest, original first-month floor, actual-day fractions, exact segments/rounding, oldest-due partial receipts | [Calculator](../../apps/tenant_apps/loans/domain/khata.py), [collection services](../../apps/tenant_apps/loans/services/khata_servicing.py), calculation/collection/revision tests |
| Limit/rate changes and reductions | Implemented: proposal, approval and activation; dated splits, actual repayment within a limit reduction, no entitlement refill; retained LTV and due clearance for reduction returns | [Revision services](../../apps/tenant_apps/loans/services/khata_revisions.py), revision/custody tests |
| Exchanges and handovers | Implemented: explicit same-metal IN/OUT groups, approved current valuations, owner WARN/BLOCK, reservations separate from actual returns | [Custody services](../../apps/tenant_apps/loans/services/khata_collateral.py), custody/isolation/concurrency tests |
| Settlement and closure | Implemented: actual principal plus unpaid closing interest, annual early closure and first-month minimum; interest stops at settlement, closure waits for handovers | Settlement/custody tests |
| Shared reads and evidence | Implemented: borrower/portal/dashboard summaries, separate debt/limit/entitlement, paginated register/history/browser, private photos/labels, immutable PDF reprints and native recovery | [Summary selector](../../apps/tenant_apps/loans/selectors/khata_summary.py), integration/history/document/recovery tests |
| Corrections | Deliberately bounded: whole interest receipt nonreceipt/refund and exchange cancellation before handover, on ACTIVE accounts with strict later-operation refusals | [Correction services](../../apps/tenant_apps/loans/services/khata_corrections.py); not general editing/reversal support |
| Real operational acceptance | Incomplete evidence: hosted candidate, actual operators, off-device recovery/cameras and paper printer/QR checks remain open | [Manual acceptance record](../flows/khata-test-pilot-acceptance.md) |

### Recommended improvements, ordered by practical risk

1. **Define the exception/support workflow before real-money use.** Mistaken
   payouts, accepted collateral facts, activated revisions, settlements and
   completed handovers cannot currently be repaired through the supported
   correction screen. Even receipt/exchange correction is conservative about
   later operations. Publish exact supported/refused examples, identify who owns
   resolution and show linked blocking sources. Decide which additional bounded
   compensating workflows are essential for the pilot. Never resolve a typo by
   editing immutable records or inventing a cash/custody movement. The current
   correction service requires ACTIVE state; broader correction wording in older
   design documents must not imply that closed accounts can be corrected.

2. **Make pending returns an item-driven workflow.** The handover form currently
   lists held items and reservation sources separately, with the service validating
   their pairing. A staff member can select an unrelated held item and receive a
   refusal. Offer searchable pending-return rows with photo, UUID/Item ID, source,
   and a contextual Hand over action that preselects the exact pair. Keep actual
   recipient/reference and final confirmation. Reuse searchable selection for
   reduction returns and photo attachment; exchange already has that improvement.
   Preserve one-item actual-handover facts if group entry is introduced later.
   See [current form choices](../../apps/tenant_apps/loans/web/khata_forms.py).

3. **Prove performance with realistic long-lived accounts.** Register filters and
   pagination occur after full portfolio summaries; summary reads prefetch complete
   operations, periods, selections and collateral. Detail also builds the complete
   custody/photo/document choices despite rendering a single tab. History's SQL
   pages bound its visible rows, not all account replay. Benchmark representative
   hundreds/thousands of items, years of operations and many accounts, recording
   latency, memory, query counts and competing operator requests. Shared Workspace
   locks in previews/commands also warrant contention measurement. Start with lazy
   tab data and database filtering where correct; add reconciled read projections
   only if measured need justifies them. Never use paginated history as balance
   authority. [Summary reads](../../apps/tenant_apps/loans/selectors/khata_summary.py)
   and [detail view](../../apps/tenant_apps/loans/web/khata_views.py) establish this
   concern; no load-test failure is claimed.

4. **Add a collection and attention worklist.** The register already filters due,
   overdue and pending returns. Expand this into actionable upcoming/due/overdue
   accounts with next due date, unpaid amount, days overdue and a receipt shortcut.
   Show current undercoverage and recorded warned-exchange shortfalls separately;
   a replacement-value warning is not additional cash debt. Current History rows
   do not expose the full warning/group evidence, so offer a readable event detail
   with exact IN/OUT groups, valuation date, policy, warnings and consent references.
   Reuse Notify v2 for optional collection reminders through Loans-owned intent;
   the inspected notice dispatch currently has no Khata-specific integration.
   This is follow-up convenience, not permission to add penalties, compound
   interest, forced top-ups or auction/default behavior.

5. **Provide explicit Khata operational reports.** Existing report selectors are
   PawnLoan-focused. Add a date-filtered Khata cash-movement daybook for withdrawals,
   interest receipts, reduction principal and settlement, with corrections/source
   references, plus a custody/pending-return report and export. This remains
   operational lending evidence, not a general ledger. Current balance selectors
   only support today; arbitrary historical outstanding reports require a separate
   tested as-of replay design. Source-prefix saved documents and history date
   filters do not by themselves implement that report.

6. **Make the next valid step apparent.** Actions are filtered by broad state and
   role; buttons such as Finalize completed interest or Activate approved agreement
   can appear when their business prerequisites are absent. Services correctly
   refuse them. Show the current proposal/approval/activation status, dated approval
   validity, next due date and an explanatory action suggestion. Filter stale/used
   approval choices in the form while retaining server revalidation. Interest
   receipt already finalizes elapsed periods atomically, so explain that separate
   finalization is an optional evidence action. Add searchable borrower selection,
   borrower outstanding and an indicative opening charge/due-date explanation to
   the Khata draft; its present borrower field is a normal ModelChoice dropdown.
   Borrower agreement acknowledgement at opening is also worth designing: the
   explicit consent reference currently belongs to change approval.

7. **Give owners a safe series pause/retire control.** Setup lists status and
   creates series but does not expose an audited active-status management action.
   The services already honor inactive series for new lending. Provide an
   authorized reasoned control with clear effects on drafts, withdrawals and
   increases; preserve interest collection, settlement, handover, numbering and
   historical association. Do not offer a counter reset or silent reassociation.

8. **Support large-label batches without reducing readability.** Label issuance
   supports ONE/ALL/EACH and refuses more than 100 held items in an issue. ALL and
   EACH select the entire holding, so an account above the cap cannot currently
   print a bounded multi-item subset; individual issuance remains possible. Add
   selected-item batches/chunks with explicit membership, stable order and saved
   issue identities. Retain the 100 x 60 mm size, 6 pt floor, complete text and
   private/current-custody QR boundary. A combined label cannot accommodate an
   unlimited item list. See [label service](../../apps/tenant_apps/loans/services/khata_labels.py).

9. **Complete acceptance and reconcile living documentation.** Run the manual
   monthly/annual scenarios with separate approver/cashier/releaser accounts, warning
   and blocking policies, stale approvals, concurrent actions and recovery. Record
   hosted HTTPS, actual camera behavior and physical print/scan evidence separately.
   Retain a reviewed reproducible release identity and remote CI before deployment.
   Older delivery checklists still say UI/integration/recovery/numbering are pending,
   and the agreement ADR says the annual leap-day rule needs resolution although
   the implemented/tested calculator clamps and restores it. Reconcile current
   summaries with checkpoints without marking unperformed acceptance complete.

Small additional presentation work: make the active mobile tab remain visible,
keep return links in the relevant tab, and add searching/pagination for an account's
growing saved-document list. These follow the existing tab/browser patterns.

### Preserve the agreed exclusions

Routine backdating, paper-history import, standalone principal repayment,
same-limit repayment/renewal, revolving redraw, advance/excess interest credit,
fees/penalties, funding/repledging, cross-metal exchange and standalone excess
returns are outside the current implemented first-version boundary. Their absence
is not automatically a defect. In particular, repayment is supported with a
formal limit reduction; broader same-limit renewal is not currently implemented.
New scope needs a confirmed rule, source-evidence design and boundary tests.
Ordinary/flexible JCL, JSK and Lakshmi behavior remains a preservation requirement.

**Suggested sequence:** operator/exception acceptance and pending-return usability;
representative load checks; collection/event-detail and cash/custody reporting;
then remaining conveniences and any separately agreed financial extensions.

## Prior label/pilot checkpoint

Later preparation: the owner selected a new test workspace and 100 x 60 mm labels.
See the [source/recovery checkpoint](khata-test-candidate-20261002.md) and
[manual acceptance record](../flows/khata-test-pilot-acceptance.md). The pending
table below records the original label-review checkpoint; local fictional recovery
does not substitute for deployed candidate/off-device or physical acceptance.
The subsequent [Linux image and persistent local pilot checkpoint](khata-image-pilot-20261002.md)
records the frozen image, 372 passing Linux regressions and the localhost test
workspace. Statements below about candidate preparation describe this earlier
review; hosted, off-device and physical acceptance remain open.

Local development/review checkpoint only. No named production workspace is selected,
no deployment/production migration is performed, and no pilot is activated.
The current workspace contains accumulated uncommitted work; a reproducible release
candidate and remote CI are still separate requirements. Passing local software
checks does not prove deployment, saved backup, physical print acceptance or
workspace-specific statutory readiness.

Inspected local Git baseline: `3209eec64f95743b4e111e08c1ec31bbd565725e`, branch
`release/2026-09-24-rc1`, with accumulated dirty/untracked work. This baseline is
not a release identity for the implemented khata code. The 346 selected regressions
and 12 final label/readiness cases pass, followed by all 25 ordinary collateral/
media/combined-label cases. Migration/system consistency and 944 documentation
links pass. No production migration or real-account write is performed.

## Delivered evidence

| Area | Concrete result | Scope/limit |
| --- | --- | --- |
| Core money/custody | Numbered drafts, approval, actual payouts, simple agreed-limit interest, monthly/annual anniversary dues, approved revisions/reductions, grouped same-metal exchanges, settlement and actual handovers | Separate khata models/services; existing PawnLoan workflows are unchanged |
| Corrections | Whole interest receipt nonreceipt/refund and unhanded exchange compensation, with dependencies, reasons and actual resolution references | Payout/revision/settlement/completed-handover/complex corrections remain refused |
| Operators | Scoped reviewed forms and permission/write-availability rechecks; actor/account/workspace/action/day-bound signed confirmations | No routine historical dates, charges, funding or paper import |
| Shared reads | Borrower/portal/dashboard totals, deduplicated borrowers and paginated register/detail | Actual debt is distinct from agreed limits and unused entitlement; pawn-only reports keep their scope |
| Documents | Immutable private A4 source documents/statements and preserved original bytes | Operational evidence, not khata statutory books/notices or auction authority |
| Physical labels | One selected item, one combined held-collateral label or one 100 x 60 mm page per held item; complete text, UUID/current-custody QR and pending-return state | At most 100 held items per issue, 6 pt floor; oversized content fails rather than truncates |
| Recovery | Thirteen native tables, original photos/PDFs/labels, guard/schema fingerprints and P/U/interest/custody reconciliation | Trusted exact-identity restore into an empty khata destination with matching prerequisites; not a clone/merge/import |
| Software review | Read-only migration/RLS/runtime/guard/storage/series/balance/native-evidence assessment, available as a page and CLI | Application authorization is distinct from database-role safety; owner connection fails the runtime check |

Migration 0040 adds the LABEL kind and held-item/source/identity/custody guards to
the existing document table. Existing A4 guard definitions remain unchanged;
immutable UPDATE/DELETE protection covers every kind. No new table/file registry
entry is needed. The khata document registry gate advances to 0040. Native backups
are guard-version-bound: restore a pre-0040 backup into its matching old schema,
verify it, then migrate forward. Never waive a guard mismatch to admit a backup.

SQL/restricted-role tests cover forged item UUIDs/descriptions/scan paths/custody,
duplicate selection and immutable updates/deletes. Service/UI checks cover exact
reprints after return, draft labels without approved-term/cash claims, idempotency,
oversized refusal, permission/cross-workspace scan boundaries and native label
recovery. A fictional three-page combined/individual label sample is rendered and
visually checked, including Tamil text and a pending return. Text remains inside
the 100 x 60 mm page and at least 6 pt. Software cannot certify physical paper scans.
Validation counts and current results are recorded in [Status](../STATUS.md).

## Remaining acceptance gates

| Gate | Current disposition | Required evidence |
| --- | --- | --- |
| Reproducible candidate / CI | Pending | Selected build/commit with the accumulated local changes reviewed, compatibility checks and remote CI |
| Named workspace and operators | Pending | Owner accepts the pilot workspace, licence-associated/independent series, limit/rate/LTV/frequency and authorized approvers/cashiers/releasers |
| Supported correction scope | Pending owner acceptance | Explicit acceptance of refused corrections and a practical support/forward-fix process; no source editing or fake cash compensation |
| Statutory/default boundary | Pending workspace review | Required external records/procedures for this product; no claim that independent numbering removes obligations |
| Backups and recovery | Local fictional round trips pass; real rehearsal pending | Verified full DB/private-media backup, independent archive checksums and disposable restore with original identities/routes |
| Migration and role safety | Local dedicated-test migration passes; deployment verification pending | Owner-only migration 0040 plus all earlier slices; restricted web/worker role with forced RLS/guards checked in the actual candidate environment |
| Printer and QR | PDF visual checks pass; hardware acceptance pending | Printer/driver/stock/scaling/operator/date and paper scans of item/account QR with correct authenticated custody |
| Monitoring and rollback | Pending named pilot | Stage opening/collection/exchange/reduction/settlement observations; forward-compatible correction/rollback after evidence exists |

The safe next production action is to review a concrete named-pilot candidate and
complete these gates. This checkpoint does not authorize deploying the current
dirty workspace, changing production data or automatically enabling every workspace.

See [the operator/pilot flow](../flows/khata-labels-and-pilot-review.md),
[the implementation sequence](../plans/khata-delivery-design.md), and
[the design scenario inventory](../plans/khata-agreements.md).
