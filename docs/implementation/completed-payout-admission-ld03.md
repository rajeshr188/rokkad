---
status: active
owner: loans
updated: 2026-10-05
tags: [implementation, loans, admission, ld-03]
related: [../plans/unified-loan-domain-correction.md, loan-servicing-eligibility-ld02.md]
---

# LD-03: admit a payout already completed

## Delivery boundary

The owner authorized LD-03 after LD-02 (`bb85c070`). The ordinary New loan paper
purpose remains the general completed-payout writer. An unpaid ordinary draft now
offers **Record completed payout**, using that same editor, signed review and
recorded-history service. It reuses the saved PawnLoan and its collateral rather
than issuing a replacement loan. Direct approval and disbursal keep their existing
price, LTV, license, product, photo and authorization checks.

The older **Record earlier payout** service remains an advanced retained-native
evidence route. Its historical quote/policy prerequisites do not apply to general
completed-payout recording. A genuine retained approval is preserved, and the new
recorded disbursal does not claim to have been approved by Rokkad on the original
day. No historical Rates or economic catalog rows are invented.

## Review, identity and financial admission

The existing Workspace lock serializes admission, followed by the saved draft and
items and the existing numbering locks. The source must be DRAFT/APPROVED with no
financial event or disbursal snapshot, no linked-renewal item origin and compatible
held custody. A reversed financial origin still requires correction, not another
admission. Borrower, series, product, number and original date remain fixed; item
membership and IDs are retained. Unsupported identity changes require explicit
draft correction before review.

The signed intent binds the target draft, actor and Workspace. Review binds saved
draft/item facts, policy pointer, genuine approval fingerprints, photo hashes and
issued-document fingerprints. Stale source evidence or changed calculations rolls
back the entire admission. An unapproved draft can receive supported actual terms
after review; genuine frozen approval facts cannot be silently changed. Earlier
policy rows, approvals, photos and issued copies remain retained.

The native draft's creation submission ID and reserved number are preserved.
Recorded admission has its own immutable request key and fact digest. Same-form
retries return the same loan; another intent cannot post a second payout. Scoped
canonical-number duplicate and archive/import checks still apply, exempting only
the target draft itself. No counter is rewound or reserved number recycled.

The existing recorded policy/2 and recorded-anniversary/3 contract, schedules,
per-item principal and actual-date events establish the ordinary ACTIVE/CLOSED
loan. Original actor remains unknown and original precision remains DAY. Known
receipts and closure can be reconciled in the same submission. Routine entry does
not certify complete-book coverage; current monitoring is selected independently
and missing current valuations remain unknown until eligible evidence is supplied.

Permissions remain data.view/data.create/loan.disburse plus data.edit for an existing
draft. Entered receipts/closures retain their own repayment, accrual and release
permissions. Authorization and matching active Workspace are checked before
preview, posting and an idempotent return; no new action permission is introduced.

## Legacy-reference guard: migration 0058

`0058_completed_legacy_payout` narrows the existing SQL prohibition only for a
DISBURSAL with owned RECORDED_CONTRACT policy, recorded original-day source evidence,
recording actor and an explicitly absent prospective approval. A deferred constraint
requires its validated matching RECORDED disbursal snapshot before commit. The
existing snapshot guard still enforces scope, dates, terms, tranches and amount
conservation. A fabricated event without that snapshot cannot commit.

Legacy references retain unknown validity and inactive status. They do not permit
new lending. No Workspace table, RLS exemption or global license is added. The
migration is forward-only once these origins exist: stopping new admission must
retain compatible readers and the recorded-history writer/evidence shape. Do not
restore the earlier legacy prohibition over legitimate accepted completed payouts.

## Compatibility and remaining work

Exact-identity Loans recovery includes draft-source evidence, retained document/media
links, old policy rows, source identity and the new guard fingerprint. Approval-based
bounded history export continues to reject recorded origins rather than dropping
their provenance or inventing an approval. Wider independent portable recorded
profiles remain LD-07. Existing archive admission and strict native-history import
retain their own supported profiles; incomplete archive settlements are not
automatically promoted to ordinary closed loans.

This slice does not widen the supported monthly bullet/flexible agreement, permit
unknown item allocations, convert posted contracts, infer missing payments, or add
reduced-principal opening continuation. That continuation remains LD-04. Wider
source-rule mapping, operations/corrections, capture transition, staff acceptance
and deployment remain LD-05–08.

## Verification

Verification uses disposable `completed-payout-ld03-qa-20261005` and dedicated
`test_rokkad_ld03_20261005`, with `django_project.settings.test`. Migration 0058 is
exercised only there. No application/candidate/production database migration or
deployment is performed.

The final affected regression passes **303 tests in 202.897s**, including **24 new
LD-03 tests**. Coverage includes saved identity/creation key/counter, actual terms
without quotes, preserved genuine approval and prior policy, issued copies/photos,
multiple saved collateral items and rates, provisional coverage, known closure,
shared editor preview/confirm/retry, stale-source rollback, source/number duplicate,
permissions/Workspace denial, two concurrent admission cases, current valuation
monitoring and exact source/legacy recovery. Restricted-role checks reject approved
or malformed legacy events, unsupported policy/approval/source references and a
recorded event without its validated snapshot; valid recorded admission succeeds
and immutable snapshot mutation/foreign Workspace reads remain blocked.

Adjacent checks exercise ordinary draft/direct origination, retained-native earlier
payout, license continuation, shared calendar, repayment/release eligibility,
standing paper terms, multi-item activity, archive admission, document payloads,
risk assessment and history/3 compatibility. The first broad list passed its 302
functional cases but contained one nonexistent test-module label; that launcher
entry was removed before the successful final run. No unrelated baseline fix was
included.

Django system checks report no issues (one existing silenced check); migration
drift/history consistency against the dedicated test database reports no changes.
All 553 Loans Python files parse and scoped whitespace checks pass. The wider
repository suite is not claimed wholly green; the five independently reproduced
LD-01A baseline failures remain outside this slice.
