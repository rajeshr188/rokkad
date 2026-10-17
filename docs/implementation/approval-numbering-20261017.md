---
status: implemented
owner: project
updated: 2026-10-17
tags: [loans, numbering, origination, compatibility]
related: [../adr/2026-10-17-loan-number-at-approval.md, origination-complexity-review-20261017.md, business-lending-terms-20261017.md]
---

# Approval numbering and remaining origination simplification

## Result and boundaries

The owner approved the proposed numbering after reviewing its order, printing
and cancellation tradeoffs. New direct preparations retain their existing loan
identity as `Draft #<id>`, with a null official loan number. First agreement
approval issues a number using the unchanged locked allocator; SIMPLE confirms
approval and payout atomically, and EXTENDED assigns at approval before payout.
First approval order determines the official sequence, independently of actual
loan dates and draft preparation order. Cancelling an unapproved preparation
consumes nothing. A cancelled or reopened numbered loan retains its number.

The draft editor accepts register/product changes before first issuance, checks
scope/product/date/tenure and resolves the applicable item economics, preserving
collateral/photo identity and before/after preparation audit. Stale signed reviews
cannot confirm those changed inputs. Numbered register/product mistakes retain
the original history through linked replacement/cancellation. Replacements and
split preparations are unnumbered until approval, so unrelated approvals cannot
invalidate their review merely by advancing a counter. Old unconfirmed split or
replacement previews need a new review; completed retries retain their outcome.
Existing numbered submission/owner-review proofs remain supported.

Approval and renewal acquire the existing Workspace coordination lock before
loan/register/sequence locks, matching paper admission. A real concurrent paper
claim/direct approval exposed a lock-order deadlock; the aligned order passes
the combined race without changing allocation or financial calculations.

For an unnumbered preparation whose cash already moved, the existing completed-
payout form reviews an actual original number or a non-consuming next-number
suggestion. Confirmed recorded admission claims it through the ordinary paper
number service, in the same transaction as the retained completed facts. There
is no fabricated prospective approval. A previously issued draft number cannot
be replaced by that form. This preserves recovery after physical cash movement
without adding another workflow or inserting a placeholder into the wire format.

Draft details, directory, preparation navigation, human exports and collateral
labels show the draft reference. Drafts have no loan-ticket print action or PDF
preview. Ticket printing starts after approval assigns the permanent loan number,
including before payout in EXTENDED mode. Reopened drafts cannot print tickets.
Existing recorded agreements retain their original-number copy semantics.
Official tickets keep their approved-source evidence; retained artifacts are not rewritten.
Renewal reloads the successor after approval before creating its opening evidence.
Legacy expired-setup links lead to the ordinary editor or retained-number
replacement, never an in-place renumbering of an issued identity.

Paper original-number claims, duplicate/source checks, reserved historical ranges
and independent release counters remain unchanged. Issued numbers are never
renumbered. The existing guarded adoption of an unissued generated opening alias
as its verified original source number remains supported before servicing or
official document/label issue. No production customer corrections, setup changes, cash movement,
messages or deployment are part of this implementation.

## Paper reference and monitoring seam

Routine paper entry prefers a known economic setup reference covering the
original loan date. It no longer requires a second economic policy to be effective
today when that dated reference is available. If dated setup is absent, the
existing entry-day setup fallback remains explicitly labelled. Neither establishes
original approval or an original appraisal. The form retains this read-only
reference separately from current monitoring, with no routine risk choice.

Missing dated and current references remain explicit, requiring supported source
input. Do not manufacture an LTV limit from current monitoring thresholds or add
an appraisal. The existing recorded-contract wire format requires numerical
reference fields; removing them entirely would need a separately versioned
admission/portability contract. This implementation reduces the unnecessary
setup dependency within that contract and preserves known versus unknown facts.
Saved agreements and current monitoring resolution/calculations are unchanged.

## Migration and recovery

Loans 0094 follows the independently prepared Loans 0093 entry-preference boundary.
It permits multiple null numbers only in DRAFT/CANCELLED, rejects empty official
numbers, requires a number for approval evidence and prevents changing an issued
number or its register/product through raw SQL. It performs no data backfill or
counter rewrite. Downgrade refuses retained unnumbered preparations; do not invent
numbers to make an old runtime fit. Exact native recovery retains nullable draft
identities and uses the existing schema/guard fingerprint. Servicing contracts
still export only issued, supported operational agreements.

The separately pending setup package profile 5/data_portability 0032 remains
required for independent entry preferences. Numbering does not add a financial
servicing bundle format or another operational settings table.

Release must coordinate a business-write pause, owner-only migration and matching
web/worker images before writes reopen. Old readers assume numbered drafts; an
application-only rollback after new unnumbered preparations exist is not a safe
recovery plan. Retain and verify the matching pre-release application/database
recovery point. Active-loan monitoring contracts and worker scheduling do not
change in this release.

## Verification

The final print-boundary run passes 38 tests plus 12 desktop/mobile page checks.
It verifies draft ticket rejection, permanent-number printing at APPROVED before
payout, and reopened-draft rejection even when an official issue is retained.
The HTTP check runs before cached official-document lookup; saved artifacts are
retained. Existing document projections and issuance tests also pass.

The initial broad snapshot exercised 2,806 tests in 4,480 seconds and completed
with 22 failures and 24 errors, comprising 45 distinct cases (one repeated
subtest). All 45 cases pass together against the final code in 56 seconds; the
complete final failure-label set was compared with that passing rerun, with none
missing. This is full-run evidence plus reconciled final-code reruns, not a claim
of a single clean 2,806-test run on the final snapshot.

Coverage includes allocation order, reopen/cancel, grandfathered reviews,
retries, scope-edit stale reviews, restricted-role guards, null-draft native
recovery, original-number reservations, concurrent paper/direct allocation and
combined payout rollback. The earlier 249-test integration run identified two
fixture issues; both pass on final-code reruns. An additional integration run
passes 41 tests. Report exports retain official numbers where present and use
preparation references only for unnumbered rows.

The final number-allocation/concurrency run passes 17 tests, including populated
0094 upgrade, duplicate combined confirmation, concurrent split confirmation
and concurrent original paper claim/direct approval. Splitting preparations
leaves the counter unchanged. Seven frozen opening-contract tests pass after
restoring two JSONL fixtures to their exact committed bytes; `.gitattributes`
prevents Windows line-ending conversion. No exported evidence format changed.

Ruff, changed-file Black, migration drift, application boundaries, repository
hygiene, all-current documentation links and the 22 preserved originals pass.
The change remains uncommitted and undeployed in the isolated release worktree.

Formatting-only baseline patches are retained separately under ignored `.tmp/`;
original pending setup/navigation work and other worktrees remain preserved.
