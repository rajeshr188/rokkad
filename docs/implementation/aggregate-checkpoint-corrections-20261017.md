---
status: locally-verified
owner: loans
updated: 2026-10-17
tags: [loans, corrections, legacy, verification]
related: [../plans/jsk-wh-original-rate-correction-20261017.md, ../contracts/loan-servicing-bundle-v8.md]
---

# Retained aggregate checkpoint correction support

The owner's confirmed JSK WH paper agreements require an original-rate
correction, preserving the already paid first month. The existing shared
agreement service now accepts retained opening-review/2 through its ordinary
checkpoint correction path. No Workspace-specific screen, loan type or financial
calculator is introduced. The owner's later expanded scope also enables the
existing native correction path for unserviced policy-1 simple/full-month
agreements, preserving their legacy calendar/calculator and explicit proceeds.
Serviced legacy agreements remain blocked for connected reconciliation.

## Calculation and write boundaries

- The existing aggregate calculator supplies original-anniversary, original-
  principal, cumulative HALF_EVEN whole-rupee amounts. Never multiply an already
  rounded 2% balance by 1.1/2.
- The pure `prepare_unpaid_collection_rate_review` helper prepares a complete
  review only when recognized additional interest remains entirely unpaid and
  one retained aggregate-interest obligation supplies its due date. Separate
  principal-only obligations remain unchanged. Partial payments/waivers, future
  charges or multiple interest allocations require an explicit checkpoint review.
  The helper neither establishes business evidence nor authorizes application.
- The existing signed preview, locked graph/dependency checks, current authority,
  confirmation and request-key retry remain mandatory. The original opening and
  accepted import stay immutable. The appended correction supplies the balance
  difference and a new remaining-obligation schedule.
- The existing typed correction form handles aggregate carry fields without
  presenting monthly-period bases or advance schedules absent from that contract.
  Monitoring settings remain independent; corrected debt invalidates assessments
  for ordinary refresh.
- A new guarded migration admits profile 2 without loosening source-chain,
  identity, date or immutable-evidence checks. Servicing bundle 8 identifies the
  additional correction semantics; old bundle profiles reject the new graph.

## Scoped production evidence

At 00:01:15 UTC on 17 October, an explicitly approved read-only check confirms the
same 685 nonzero-interest imported loans as the earlier snapshot, with no changed
source hashes. All retain first-month-paid evidence, unchanged principal,
recognized interest equal to unpaid interest and only their original opening
event. No connected funding, renewal, auction or out-of-vault collateral appears.
All have separate principal and aggregate-interest obligations, with the full
opening interest represented in the latter.

The read-only proposal at 00:06:49 UTC successfully prepares all 685 and preserves
their principal, fees, original dates, calculation rule and paid first month.
Individual monetary values remain in the server process; scoped local reports
contain loan references, hashes/flags and aggregate impact only, under the
approved `.tmp/jsk-wh-correction-review-20261017/` location. Exact monetary totals
and customer loan references are not copied into tracked documentation.
The proposal membership/hash is
`f45e39a90b247a047d3ddf518ee88a04653d79bc3c2f12042c1975ffc9dc8135`.

This calculation does not execute the write-producing service preview, issue a
confirmation token, lock a future apply graph or apply a correction. A later
apply must recheck source hashes and dependencies, regenerate the same checkpoint
proposal and use the ordinary authorized service. The earlier 685-loan proposal
is superseded by the owner's all-active scope: the read-only check finds 826,
all unserviced and without connected dependencies. All 824 import proposals pass,
including the 139 zero-opening-interest imports. For WH02145 and WH02146 the
owner explicitly confirms 1.1% at disbursal after the proceeds question; retain
saved document charges while correcting the original advance/net proceeds.
No new cash is recorded. Both native records have original licence revisions.

## Verification and remaining release work

The final 49-case selection passes in 108.240 seconds, covering ordinary,
aggregate and legacy native corrections, both portable/exact recovery paths,
legacy calendar/upfront preservation, stale/competing reviews, source immutability,
rollback, authorization, RLS, downgrade and monitoring behavior. Earlier selections
passed 100 correction/servicing cases and 213 portability cases; those overlap and
are not summed. Seven repository/boundary tests, pin/format/static guards,
document links and preservation checks pass; no model drift is detected.

Testing caught a new PL/pgSQL alias colliding with the existing trigger record
variable. The alias is corrected and the unpublished migration is rolled back
and reapplied only on the empty disposable test database before the final rerun.
No historical/deployed migration file is edited.

The final read-only all-active proposal at 00:28:25 UTC prepares 824 imports and
two native agreements with identical membership/source hashes. Its metadata-only
proposal digest is
`f08d6b4ba0d828fcfa21a434bb05dc43541ebb55d90fb1b38d7e9ad43d6bcf24`.
Native proposal inputs explicitly retain the owner's confirmed first-month
deduction at 1.1% and the existing document charges; no new cash is proposed.

The disposable database is
`test_rokkad_aggregate_correction_20261017`; adversarial DML uses a non-superuser,
non-bypass role. No production database writes or deployment have occurred.
The owner now requests the actual scoped all-active correction. Exact-source CI,
compatible release/recovery and isolated production-data rehearsal precede apply.
