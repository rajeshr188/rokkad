---
status: complete-local
owner: project
updated: 2026-10-05
tags: [loans, servicing, read-models, ld-01]
related: [../plans/unified-loan-domain-correction.md, ../adr/2026-10-05-unified-loan-admission-and-continuation.md]
---

# LD-01 read-only servicing contract and position

## Change and boundary

Checkpoint `89f7321e` on `work/loan-servicing-contract-ld01` preserves completed
shared entry and the architecture review. Billing/platform/storage changes remain
outside both the checkpoint and this slice. LD-01 changes only a new selector,
three read consumers, tests and documentation; no migration or posting change.

`selectors/servicing_contract.resolve_servicing_contract` reads the existing
financial origin, saved policy and recorded/opening evidence. It exposes supported
profile, original/cutover dates, rounding/calendar conventions and separate opening
recognized/unpaid interest. Older native event folds without itemized snapshots
retain unknown policy values instead of acquiring invented terms.

`get_servicing_position` delegates to the existing canonical balance fold,
recorded collection balance or opening payment balance. It distinguishes recorded
debt from collection with unposted interest. Optional transaction coverage uses the
existing completeness selector; it does not attest to a book or change current
coverage requirements. Maturity/amounts come from the existing balance result;
item allocation and obligations remain in their existing validated selectors and
preview. No duplicate calculator, allocation engine or full future checkpoint
schema was introduced.

Repayment preview, reminder balance and repayment form balance context reuse this
position. Unsupported recorded profiles fail explicitly in both consumers; the
previous repayment-preview native fallback is removed. Mixed origins, foreign
Workspace objects, pre-original/pre-cutover dates and unsupported opening profiles
are rejected. Existing dedicated opening servicing still requires strictly after
cutover and supported chronology/schedule. Closed opening reminders retain the
recorded fold without adding new interest.

All financial writers, actor permissions, signed review/idempotency, paper-purpose
eligibility and native approval/quotes remain unchanged. This slice does not admit
reduced-principal checkpoints, new source allocation rules or new action purposes.

## Interest differences preserved

| Existing contract | Boundary | Rounding |
|---|---|---|
| Recorded anniversary 1 | Charge starts on original monthly anniversary; a payment on that day changes the following period | Loan-level charge each anniversary, HALF_UP to paise |
| Recorded anniversary 2 | Same timing; actual item principal/rates | Each item's anniversary charge HALF_UP to paise, then sum |
| Opening collection 2 and supported later payments | Charge count increases the day after the original monthly anniversary; reviewed baseline is already recognized | Raw aggregate cumulative charge, adjusted for supported reductions, HALF_EVEN to whole rupees |
| Native periodic contract | Frozen native period/partial-month rules; current repayment uses posted debt | HALF_UP at saved quantum through existing period/item calculations; older scalar fallback preserved |

Example: original date 5 April, principal 10,000, 2% monthly, first month covered,
no other payments. Paper additional interest is 200 on 5 May; the opening rule is
zero on 5 May and 200 on 6 May. This compares cumulative charges after upfront
coverage, not remaining unpaid interest after arbitrary receipts/cutover recognition.

For rounding, two raw item charges of 10.005 become 10.01 each, totaling 20.02
under itemized paper rules. Summing first would produce 20.01 at paise precision.
Under opening whole-rupee HALF_EVEN, cumulative 100.50 becomes 100, but cumulative
201.00 becomes 201. Rounding each monthly 100.50 first would incorrectly yield 200
over two months. These are current accepted calculation versions; LD-01 does not
choose a new universal business convention.

## Verification environment and progress

Isolated container `loan-servicing-ld01-qa-20261005` uses the current local candidate
image `rokkad:entry-refined-20261003-a80e473e`, with only the five LD-01 source/test
files copied to its verified `/code` directory. Tests use
`django_project.settings.test` and dedicated database `test_rokkad_ld01_20261005`.
Neither candidate database/media nor production is modified. Test setup uses owner
credentials; adversarial reads explicitly assume a NOSUPERUSER/NOBYPASSRLS role.

The initial 13 contract tests passed. Three additional tests cover provenance
independence, restricted-role isolation and a closed label without financial
origin. The affected regression run initially
hit filesystem permission errors because the new QA container's `/code/media`
directory was not writable. This is an isolated test setup issue; only its empty
media/static directories were made writable. A subsequent 238-case suite passed
in 95.126s. After the final missing-origin guard, the complete final **239-case
affected suite passed in 94.193s**, including all **16 new contract tests**.
Django checks reported no issues (one preexisting silenced check).

Private logs and the QA runner are retained in `.tmp/ld01`. New Python files
compile, documentation links resolve and scoped Git whitespace checks pass.
Outside the two LD-01 edits to previously dirty application files and the checkpoint's
one trailing-space cleanup, all 91 other protected application files retain their
reviewed hashes. QA contains exactly the copied LD-01 source/test bytes.

Coverage includes native posted debt, recorded profiles 1/2, anniversary and rounding
ties, optional/provisional coverage, no-write reads, cutover, closed reminders,
partial-payment/reversal, unknown profiles, source provenance, query bounds and
Workspace isolation. The provenance equivalence fixture is explicitly
admission-independent, not a claim of end-to-end import for new unsupported rules.

## Rollback and remaining work

Restore the previous three read consumers to roll back this slice; it creates no
new financial evidence or schema. Keep accepted source contracts and issued files.
LD-02 remains next: common operation purpose/eligibility with existing validated
repayment/full-release writers. Broader admission, source rules, checkpoint profiles,
coverage transitions and export changes remain pending in the plan.
