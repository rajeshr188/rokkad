---

status: active
owner: project
updated: 2026-09-12
tags: [loans, portability, mvp, migration]
---

# Route to the first legacy import

## Current dump supersedes the old batch (2026-09-12)

The owner supplied `C:\Users\rajes\backup_20260912_224652.sql`, a custom-format
archive. Read-only extraction and comparison are complete under the same legacy
namespace. Use `outputs/jcl-current-comparison-20260912/review.html` and its linked
full source review for current decisions. There are 2,463 unreleased loans, all
retained by the collateral rule, with stored principal 45,351,608. This is source
principal, not approved debt. Eleven have payment rows requiring reconciliation;
the remaining 2,452 still need reviewed opening balances, fees, paid coverage and
custody. The active set references 1,093 customers; 613 share names in 189 groups.

Only 194 of the earlier 2,446 proposed loans remain unreleased. Another 2,249 are
released and 3 absent. The five unfinished earlier Party batches are now CANCELLED;
their original private files/reports remain preserved. C00121 is released in the
new source on 2025-01-21, while Workspace 9 retains its earlier active test opening.
Do not import the obsolete candidates or rewrite that pilot. A fresh isolated
rehearsal Workspace 10 (`test-jcl-current-20260912`) was authorized and created.
Workspace 9 remains unchanged.

Current preparation is complete in Workspace 10. Review
`outputs/jcl-current-preparation-20260912/review.html`: 1,093 native Parties, 755
contacts and 1,104 addresses imported through ordinary services, with exact source
bindings. All 613 same-name source customer records remain separate after explicit
batch review. Two addresses for one customer had conflicting default flags; both
are retained with no chosen destination default and preserved source provenance.

All 2,463 source-active loans have destination setup proposals and original readable
numbers. Two legacy licence references, seven series, the approved test monitoring
thresholds, retired legacy product and INR 15,500/g pure-gold test quote are saved.
Counters reserve C07433, RA00533, A10000, H09991 and LEGACY6-10000; R/B are
exhausted at 10001. Existing source ranges include released/excluded/disappeared records.
No financial loan, event or appraisal has been imported into Workspace 10.

The owner specifically kept the 11 payment-bearing unreleased loans on hold until
checked. For the remaining 2,452, proposed principal totals 45271218;
the September 12 interest illustration is 4891222. These
assume unchanged principal, first month paid upfront and no later collections or
concessions. The next owner review must establish balances/fees, coverage and
collateral custody; null evidence must not be replaced by inferred approval.
After that, compose bounded financial staging/commit from the existing services,
validate exact inputs and execute approved current appraisals. Complete gold
estimates exist for 1659 loans; other metal values remain
unknown. Recheck quote freshness on execution.

Verified licence/active-product setup for new lending and limited-evidence released
history remain pending. R09911's future date (2026-12-16) is a released/excluded
source exception; it does not block the current active candidates. September 12
remains a diagnostic comparison date until explicitly accepted for this rehearsal.
The general reviewed-name decision is documented in its
[ADR](../adr/2026-09-12-reviewed-party-name-collisions.md).

## Active-batch preparation (2026-09-12)

Historical checkpoint below: superseded by the current dump above.

Owner-authorized preparation is saved in private
`outputs/jcl-active-preparation-20260912/review.html`. Workspace 9 now has both
legacy licence references and all six source-series mappings. Five Party review
batches hold 1,236 customer masters, 622 contacts and 1,203 addresses; one of the
1,237 required customer identities already maps to Party 8. No new Party or loan
was committed. The full-source R/o conversion hold is outside this batch.

The packages cover all 2,446 new active candidates with checked destination setup,
readable numbers, original terms, separate proposed balances and appraisal inputs.
They intentionally retain null balances, custody/coverage attestations and final
approval where unconfirmed; they are not ready for financial staging or upload.
Principal proposal: 21,651,825. April 9 unpaid-interest illustration: 11,359,106.
Fees remain unknown. Monitoring policy 4 is the agreed test policy; 1,751 loans
have complete gold estimates and 695 require further valuation. Recheck current
quotes when executing appraisals; no appraisal is saved merely by preparation.

Actual Party staging exposed a necessary identity-resolution gap: 769 new customer
rows conflict on repeated names despite distinct source IDs; 467 pass individual
checks. Equal-name groups were kept together across bounded files. Do not merge or
rename people, or assume changing a chunk boundary resolves identity ambiguity.
Next resolve these through a reviewed source-ID-preserving path, then commit
customers and revalidate their dependent contacts/addresses. Cohort balances,
fees, first-month coverage, custody and obligations must be reviewed before the
source-bound financial preview/commit. Bulk opening/appraisal execution remains
to compose the existing services; this preparation does not bypass the existing
20-unfinished-Loans-batch limit by staging thousands of individual openings.

Numbering is prepared separately from lending readiness:

| Series | Next reserved number | Availability |
| --- | --- | --- |
| C | C00123 | Counter prepared; legacy licence blocks new lending |
| R | R08066 | Counter prepared; legacy licence blocks new lending |
| A | A10000 | Last slot at the configured 10000 ceiling; legacy licence blocks new lending |
| B | B10001 | Exhausted at 10000 |
| H | H09991 | Series remains inactive |
| LEGACY6 (blank source label) | LEGACY6-10000 | Series remains inactive; original bare loan numbers unchanged |

Ranges include released, held and skipped loans. C retains its existing 999999
test ceiling; new series use the ordinary 10000 default, not source `max_limit`.
Release receipts have separate test-prefixed counters. The audited Loans
`reserve_sequence_through` command advances an existing sequence under its row
lock and cannot rewind or issue a number. Import preserves source numbers.
The September 22 [license verification workflow](../flows/legacy-license-continuation.md)
now supports continuing the same license and series after current document and
final frozen numbering review. It appends verification evidence without changing
old loans. Ordinary activation still rejects unverified references; this rehearsal
has not verified or activated them. A grouping that is not the legal license number
still requires separate verified setup with coordinated non-overlapping numbering.

## Full-tenant preview (2026-09-12)

The complete jcl review is prepared in the private
`outputs/jcl-migration-preview-20260912/migration-review.html` artifact. It accounts
for 19,240 source loans and 5,431 customers without staging or importing rows.
After the authorised collateral exclusions, 2,448 active candidates remain
(including C00121 and held R07743) alongside 4,620 released historical records.
The released-history command is still absent. Cohort balances/custody, current
valuations for non-gold items, one relationship mapping and destination setup
must be resolved before a tenant-wide financial rehearsal.

April 9 is a comparison date only. The latest jcl source loan/payment/release is
October 10, 2024. The owner confirmed this is a test dump and will supply a fresh
dump with the latest activity later. Continue rehearsal preparation with this
source; re-extract and reconcile the later dump before live cutover. Rehearsal
estimates must not become confirmed production balances. This clarification
supersedes the generated preview's pending source-freshness question. Preserve all
skipped source evidence and readable loan numbers. The preview's candidate/converted
flags are not financial approval, and C00121's source identity must remain an
existing binding.


## Current pilot acceptance (2026-09-12)

C00121 has its readable source number through an audited correction preserving
accepted evidence. Its normal page shows original maturity/grace and a dated
full-release quote. The September 12 quote is 7,300. A rolled-back release with a
50 concession, receipt rendering, custody return and reversal passed. The stored
loan remains ACTIVE with one opening event. The owner accepted recognisability and approved the test monitoring settings,
now saved as policy 4/version 1 in Workspace 9. A current owner-authorized RATE_BASED appraisal now records 34,875, using
test gold quote 5 at 15,500 INR/g pure gold; valuation/LTV are available. The
underlying original source valuation remains unverified historical evidence.

The next source preparation should explicitly put the readable source number in
`setup.local_loan_number`. Check collisions and future series ranges before
approval. The dump adapter supplies ordinary opening inputs; no jcl-specific
rules belong in generic numbering or monitoring services.

Older preparation checkpoints below describe staging. Their statements that no
loan exists are superseded by this acceptance checkpoint. Complete the operational
pilot before tenant-wide conversion; the April 9 checkpoint is rehearsal-only.


The first source is the owner's legacy PostgreSQL dump, tenant `jcl`. Simple Excel
registers follow. C00121 is imported in isolated Workspace 9 (loan ID 16).
The remaining cohort is preparation only; no production cutover is approved.

## Completed foundations

- Bounded, read-only dump extraction with source identities, hashes, source checks
  and a reversible whole-loan collateral exclusion proposal.
- Existing Party staging, identity mapping and atomic commit infrastructure.
- Strict complete-history Loans import/export for sufficiently complete sources.
- Owner-informed anniversary calculation, first-month coverage and net-weight
  preparation; deterministic aggregate rounding for the rehearsal.
- Single-loan full release now supports an explicit administrator-approved interest
  concession, recording cash and loss separately with immutable reason/actor,
  reversal, replay and isolation coverage. This services existing native Loans;
  it does not create migration opening support by itself.
- Migration opening evidence, balance and item-principal read foundation. A single
  immutable opening freezes reviewed cutover amounts and mappings; earlier balance
  queries and mixed origins fail explicitly. Reports separate imported debt from
  lending/collections. This has synthetic test coverage only; ordinary generic
  posting remains blocked for opening loans.
- Explicit v2 collection checkpoint and exposure projection preserve inclusive
  anniversaries, first-month coverage and cumulative aggregate rounding across
  cutover. Remaining reviewed obligations can be persisted with owner authorization,
  original due dates, retry conflict checks and atomic rollback. Delinquency uses
  reviewed grace. These are tested domain building blocks; source candidates are
  not automatically populated or approved.
- Full release now posts the migration collection catch-up, settles cash plus
  explicit concession, terminates the reviewed schedule and returns collateral
  atomically. Coupled reversal restores all of those effects. Existing form/detail,
  numbered receipts, original-date read models, retries and rollback are tested.
  This enables the supported full-release path, not partial repayments, native
  periodic accrual, renewal or auction servicing of opening loans.

## Required work before an active pilot import

The isolated destination is Workspace **9**, `TEST - jcl migration rehearsal`.
The owner has confirmed C00121's April 9 rehearsal balances (principal 5,000,
unpaid interest 1,700, fees zero), first-month paid coverage with no later payments
or concessions, custody, three-day grace and a migration maturity of 2025-01-10.
Do not ask for those confirmations again. Licence validity was never recorded;
the dumped valuation is old and has no confirmed date/current value.

Those evidence gaps are now supported: an inactive legacy-reference licence stores
null dates, and explicit UNVERIFIED valuation evidence creates no appraisal or LTV.
The source borrower, reference, series and retired compatible product are prepared.
Normal-database migrations portability 0013 and Loans 0010/0011/0012 are applied.
The source was freshly verified and C00121 is READY in prepared legacy openings.
The real owner review page returns HTTP 200. The private
`outputs/legacy-pilot-jcl-20260912/pilot-review.md` contains the exact route.
No financial loan is imported yet; next is review of that complete preview and
explicit financial confirmation, followed by reconciliation in the isolated test
Workspace. The April 9 date remains rehearsal-only, not production cutover.
See the [evidence-gap decision](../adr/2026-09-12-legacy-opening-unknown-evidence.md).

The per-loan opening commit is now implemented with owner authorization, a full
rolled-back preview, exact-input confirmation, source identity shared with complete
history, immutable provenance and atomic rollback. Synthetic imported loans have
passed release/reversal and retry checks. No real `jcl` loan has been committed;
the one-loan source staging and browser approval bridge is now implemented.
It re-extracts the selected dump snapshot, verifies the exact retained loan and
source facts, retains source evidence and requires signed owner confirmation.
Actual reviewed inputs and a real rehearsal remain; see the
[operator flow](../flows/legacy-opening-import.md).

Legacy collateral mapping is implemented: review v2 and the destination model
can retain unrecorded gross weight with known net/purity; Bronze is distinct.
Native origination remains strict. The refreshed offline report at
`.tmp/legacy-collateral-jcl-20260912/` maps 1,775 Gold, 688 Silver and seven Bronze
items across 2,448 active candidates, with all 2,470 gross weights unknown.
All candidates still require financial/destination review; R07743 stays held.
Of those loans, 298 store tenure 3 and 2,150 store tenure 0. The inspected legacy
Girvi code declares a default tenure but does not calculate a contractual maturity;
neither value by itself proves a historically agreed due date. The subsequent
owner instruction now supplies an explicit migration rule for missing maturity:
three calendar months from the original business loan date, with end-of-month
clamping. Preserve any recorded maturity terms and retain the migration rule in
terms evidence. Do not restart tenure at import or extend an already recorded date.

| Work | Concrete completion condition |
| --- | --- |
| Active opening and servicing | A Loans-owned immutable migration opening records approved cutover principal/interest/fees, per-item principal, original dates, rule and paid coverage without fabricated historical disbursal/receipts. Repayment, ongoing interest, full release, correction, reporting and export work from that opening; unsupported actions fail explicitly. |
| Legacy evidence gaps | Unknown gross weight and explicit Bronze are supported. Resolve missing original due terms and establish custody/valuation and opening balance evidence. R07743 remains held until corrected with evidence or omitted from an approved pilot selection. Missing values are not replaced with arbitrary defaults. |
| Destination and adapter | Select the destination Workspace; translate source customers through Party identities and review licence/series/product mappings. Preserve source loan numbers/reference provenance, resolve numbering collisions and translate the approved source selection into canonical opening commands. Existing customers/setups are reused when explicitly matched. |
| Tested commit and rehearsal | Validate the exact candidate set, balances and mappings before writes. Commit with authorization, forced RLS, per-loan atomicity and source-fingerprint idempotency; verify retries cannot duplicate debt. Rehearse a small approved selection in a test Workspace and compare counts, principal, interest, collateral and post-import servicing. |
| Production handover | Obtain a fresh dump after an agreed cutover, reconcile source activity through that point, verify the final selected/held counts and totals, and execute the reviewed batch with a recovery procedure. The April snapshot and April 9 comparison date are rehearsal inputs only. |

Opening export and bounded cross-Workspace restoration are now implemented.
The restore command rebuilds and reconciles the opening plus supported later
servicing before atomic commit; source-local IDs and actor claims stay in immutable
provenance. Identical retry cannot duplicate debt or reset newer servicing. See the
[restore decision](../adr/2026-09-12-opening-restore-reconciliation.md).

The next MVP step is to **resolve the prepared one-loan review and rehearse it**.
The isolated destination is selected. Review the source snapshot and rehearsal
date; complete the mapped borrower, licence,
series/product, original due terms, reviewed balances, custody and valuation.
Keep unsupported due terms, payments, reduced principal or disputed amounts held unless
supported by reviewed evidence. R07743 remains held. A successful synthetic restore
does not supply those missing facts or authorize a production cutover. The
owner should not have to construct JSONL, recreate old receipts or re-answer the
fractional-rounding question. Present a proposed mapping/balance review from source
data when an actual business decision is needed. Keep unresolved individual loans
held rather than silently repairing them or requiring every exceptional loan to
enter the first pilot.

## Released records and the full initial migration

The retained released cohort needs a separate limited-evidence closed-record path:
preserve customer, source number, dates, collateral facts and the owner's closure
attestation without making it an active balance or inventing complete payment
history. That path remains unimplemented. It is required to finish the full initial
dump migration, but it need not prevent an earlier active-loan pilot. Exclusion
proposals are reviewed explicitly for each cohort; an active-loan opening can never
be used to represent a released loan.

## Scope kept out of the first pilot

Simple Excel conversion, Party history filters, general archives, cross-Workspace
preset copying, renewal/auction import and accounting restoration are not first-
pilot requirements. Broad payment-concession configuration is unnecessary. The
implemented concession applies to an individual full release; ordinary partial
repayments, batch release and renewal retain their existing behavior. Above-due
collections are not automatically treated as extra interest or negative losses.

Concession histories cannot be exported as strict `loan-history/1`; that profile
cannot represent loss and now returns an explicit error. The migration opening
and its subsequent events can now be downloaded as
[opening evidence](../contracts/loan-opening-export-v1.md). The dedicated operator restore now rebuilds and reconciles that evidence. It keeps
native complete-history imports separate and does not merge exports into an
existing ordinary opening.

See the [opening contract](../contracts/loan-opening-position-mvp.md),
[collection decision](../adr/2026-09-12-legacy-collection-estimates-and-concessions.md)
and [delivery plan](data-portability.md).
