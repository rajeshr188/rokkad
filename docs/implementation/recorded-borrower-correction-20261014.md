---
status: verified-locally
owner: project
updated: 2026-10-14
tags: [loans, paper-entry, corrections, validation]
related: [../adr/2026-10-14-recorded-borrower-correction.md, ../flows/unified-loan-recording.md]
---

# Active paper loan borrower correction

This records the initial bounded delivery. The approved
[origination consolidation](loan-origination-consolidation-20261014.md) supersedes
its paper-only applicability and servicing-export refusal: common correction now
supports eligible ordinary active loans and version 5 maps both Party identities.

The loan detail offers **Correct borrower** to Workspace administrators for active
paper loans. Its ordinary customer search, reference/reason fields, before/after
review and separate confirmation retain the loan identity and financial/custody
records. The audit trail displays old/new names and customer codes plus the paper
reference, recorder, time and reason.

The dedicated service uses the existing loan lock, action access and signed review
pattern; business changes remain outside the view. A typed immutable LoanChangeLog
entry carries exact Party IDs and snapshots with a request digest and source
fingerprint. Migration 0075 alters only enum choices and installs scoped INSERT,
append-only, Party-retention and retry guards; owner-only migration settings remain
mandatory. It branches from deployed monitoring 0073 so later delivery need not
force unpublished portability migrations. Empty 0076 joins the local 0074 branch.

Known renewal/funding/auction graphs, non-active/non-paper origins, missing or
foreign/inactive/blocked targets and unchanged borrower selection are refused.
Prior documents survive; newly generated contract/payment copies identify the
borrower correction. Borrower-bound transaction coverage requires another paper
check and old queued reminders cannot reuse their reviewed source fingerprint.
Current monitoring is invalidated by the existing PawnLoan save signal.

Loan-history and servicing exports/imports explicitly refuse unsupported borrower
remapping. Exact recovery retains both source identities and correction evidence.

## Verification

All **311 distinct selected cases** are verified across the broader and final
affected runs. The initial 289-case broader run passes 288 cases; its route sample
fixture lacked converters introduced by previously pending routes. The fixture
now supplies all converters and the complete route-adapter case passes.

The 40-case affected run passes 38 cases after the real concurrent-lock correction;
its remaining route sample and no-change-log document stub are fixed. The final
32-case confirmation passes all cases, including all 20 borrower correction cases,
document projections and complete route resolution. The eight exact-recovery cases
already pass in the affected run. Counts overlap and must not be added together.
Earlier focused fixtures were corrected for actual renewal proceeds, scoped
permission aliases, required monitoring policy and pending deferred constraints.
All observed errors are resolved.

Concurrency exposed a real PostgreSQL join/row-lock issue: locking a loan together
with its mutable borrower could omit a waiting row after the association changed.
The correction and recorded-document issuance now lock the loan alone, then read
the customer. Borrower correction locks Party rows in sorted order. Identical
concurrent submissions append once; competing signed reviews cannot both change
the borrower. The document endpoint also needed a correction-aware source
fingerprint to issue the new copy while retaining previously issued bytes.

Restricted-role writes verify successful correction, RLS hiding, immutable audit
UPDATE/DELETE refusal and foreign JSON Party-anchor refusal. Existing financial
events, snapshots, schedule versions, collateral and balances remain exact.
The tests verify old Party retention, empty guard reverse/reapply, existing-row
preservation and downgrade refusal with retained corrections. The local owner-only
merge migration, all-model consistency, system checks and import guards pass.

Four Chromium captures (form/review at 1440px and 390px) show the existing customer
picker and no horizontal overflow. Public CDN dependencies were cached in the
ignored local QA folder because sandboxed browser network reads are denied; the
render uses their existing declared versions, with no production asset change.
Initial unstyled captures were replaced and the styled captures inspected.

The exact local `test_rokkad_borrower_correction_20261014` database is removed after
verification. Fictional helper/log/screen artifacts remain under the ignored
`.tmp/borrower-correction-20261014` folder. No shared/development/production database
migration, real loan correction, commit or deployment has occurred.

## Release and remaining boundaries

Production delivery needs its own exact-source candidate/recovery sequence and
owner-only migration 0075, preserving unrelated pending work. Existing active
paper loans can be corrected after that release; deployment itself must not change
a real borrower. Known renewal/funding/auction graphs and cross-Workspace remapping
remain explicit reconciliation/profile work. Exact native recovery now includes
both former/current Party prerequisite fingerprints; older published exchange
profiles refuse this evidence instead of dropping the original borrower.
