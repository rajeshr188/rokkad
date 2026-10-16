---
status: preparing
owner: project
updated: 2026-10-16
tags: [loans, counter, monitoring, deployment]
related: [everyday-counter-improvements-20261016.md, loans-architecture-hardening-20261016.md, represented-position-coverage-20261016.md, ../plans/future-work.md]
---

# Counter and monitoring production release

The owner requests recording the repository review as FW-024, followed by commit,
push and production deployment. Repository cleanup itself remains deferred.
The candidate combines the previously committed monitoring lifecycle and
represented-position changes with the locally accepted everyday-counter work.
The separate JSK WH note is retained as documentation; no retrospective interest
correction is selected by this release.

Read-only preflight confirms both live readers still use
`sha256:53f6dd38d64bff0ebf3cadcf26402ff2f78a4d220305200b056f64ddc379d6ac`
and V11. All six timers and public login are healthy, with 10.549 GiB free.
Comparing 1,539 candidate runtime paths identifies 99 differing files, including
contract references. No newer live image needs merging at this checkpoint.

The coordinated schema boundary consists of Loans 0089, both independent 0090
guards and their 0091 merge, plus data_portability 0030. Compatible web, monitoring
and four scheduled readers must move together to V13 and package profile 4.
Rehearse against an isolated production copy and preserve original business-table
projections. Preserve unsupported valuation and unavailable earlier history.

Existing authorized encrypted operational backups run before and after release.
Retain a stopped-writer encrypted recovery checkpoint before migrations and verify
the candidate application image through the previously authorized local encrypted
recovery process. Private keys stay off-server. No production source/customer data
is copied into Git or the outgoing source-only archive. After migration starts,
recover forward with compatible readers; do not silently return to an old writer
or restore over later customer activity.

## Exact committed candidate and local checks

Application commit `a68dbcb0d3612724577e9371cc325e19fff46453` is pushed to
`work/loan-servicing-contract-ld01`, including FW-024 and the independent JSK note.
The [source-only manifest](counter-release-20261016.manifest.json) binds 99 files
in a 1,116,160-byte archive and 1,539 checked runtime paths. Its canonical private
manifest identity is `f23a87410931ddda4e521fcfb8ee3745a4b7d9e8c379b4483669db197c6ce035`.
Candidate `rokkad:counter-production-20261016-a68dbcb0d361` has image ID
`sha256:cb6eeea89992cdd4aaf20934e9debda773c8deef8383d5ce1161ab1c28856bdf`.
The separate build changes no running service.

The full affected selection now passes **162 cases in 223.459 seconds**, including
the corrected overdue preview/access expectations. Twelve JavaScript cases pass;
1,440 committed Python files parse and 1,252 import-boundary checks pass. Earlier
desktop/phone acceptance remains recorded in the linked counter implementation.
Selections overlap and are not summed. The exact-commit
[six-group CI run](https://github.com/rajeshr188/rokkad/actions/runs/38918647235)
is dispatched explicitly because the working branch does not match push filters.

Encrypted local application recovery passes: a 228,245,604-byte ciphertext is
downloaded, decrypted with the existing local identity and reloaded on the same
server as the exact candidate image. No database/customer/config records are in
this transfer; no private key is uploaded and transient plaintext is removed.
The candidate application image is not uploaded to R2 by this recovery check.

## Server rehearsal and recovery

The isolated production copy restores **222 tables / 1,130,005 rows**, with exact
snapshot fingerprints. The five planned migrations apply, and all **219 original
business-table projections** remain equal (framework migration/content-type/
permission tables are excluded). Baseline/candidate readers match **14 financial
samples across four retained contract profiles** and pass 23 screen checks.
The new counter check passes directory/detail/Dashboard readers across all three
Workspaces, collection parity and daily component reconciliation.

The first candidate-reader attempt uses the old static manifest and correctly
fails on the newly added entry script. Collect assets into the candidate's separate
volume, verify its JavaScript/manifest and unchanged predecessor assets, then
resume all candidate reader/feature checks on the same upgraded isolated copy.
This corrects preparation order; source, image and migrations remain unchanged.
The initial failed helper is retained as evidence rather than counted as passing.

The bounded V13 worker selects ten loans per Workspace, **30 total / zero errors**.
Afterward **216 original non-derived business-table projections** still match;
only the three derivative risk tables may change. This is not a capacity test or
a claim that every portfolio assessment is current or collateral evidence complete.

Candidate static volume is `rokkad-counter-static-20261016-f23a87410931`. Prepared
compose and scheduled-reader changes validate without installation. Restricted
startup/model checks, protected configuration, current timers and existing access
remain intact. The existing encrypted pre-backup passes actual remote download
verification and unchanged retention. Local encrypted image recovery also passes.

## Full-suite gate failure and correction

The exact-commit CI run passes five groups but Loans executes 2,695 cases in
1,707.358 seconds with 18 assertion failures and ten errors. Production is not
switched. The initial image above is superseded by the corrected candidate once
its checks pass; successful real-data sampling does not waive a failing full suite.

The broader selection exposes an undefined latest-event variable in checkpoint
correction, a terminal-position reader attempting absent grace terms, and a
revision lookup that adds per-loan queries to the existing monthly batch. Fix
those application defects while retaining the 12/13-query and zero-query preview
assertions. Existing failing correction/terminal tests provide direct regression
coverage. Update older assertions for optional book assurance and reviewed policy
confirmation, an outdated locked-query mock, and compare valuation evidence under
one frozen aware cutoff. Financial source/permission and missing-history guards
remain in force. The affected full classes are rerun before another release.

This checkpoint still has no production switch.

The affected-class follow-up executes 226 cases: 225 pass, with one remaining
opening-correction history lookup exceeding the unchanged batch bound. Reuse its
already prefetched event history, retaining correction-chain validation. The final
65-case selection passes in 104.470 seconds, covering the complete monthly-query,
agreement-correction and counter-workflow modules, including that remaining failure.
Selections overlap; no selected failure remains unresolved. Build a new candidate
and run exact-source CI again before release.
