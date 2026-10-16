---
status: deployed
owner: loans
updated: 2026-10-16
tags: [monitoring, defaults, production, amendments]
related: [../adr/2026-10-16-calculated-monitoring-default.md, jcl-monitoring-coverage-review-20261016.md]
---

# Calculated monitoring default and amendment flow

The owner requests calculated metal monitoring as the default across Workspaces
and reports an overlap error while attempting an amendment. Current production
inspection verifies JCL's 2,377 active migrated-opening loans saved latest appraisal
and 340 disbursed active loans saved lower-of. The opening-register adapter selects
latest appraisal explicitly; this is not proof of original physical valuation.

The correctly linked amendment form validates in all three business Workspaces.
The ordinary setup GET opens a new, unlinked policy form, which cannot overlap an
existing scope. Local code now opens the latest Workspace policy as an amendment
by default, retains explicit new-scope creation and gives an actionable overlap
message. It does not remove model/service/database guards or infer a predecessor
when an old unlinked POST arrives.

## Authorized production amendments

A restricted read-only inspection confirms requesting actor 1 has existing setup
authority in all three businesses. A full rolled-back preview succeeds before
commit. The existing runtime service appends today's explicit calculated-value
Workspace defaults: JCL v1 to v2, JSK v1 to v2, Lakshmi v2 to v3. These are the only
active Workspaces with configured monitoring policies; no licence overrides exist.
Test/empty Workspaces receive no fabricated setup.

The original policy rows, every other policy field and the complete source-row
fingerprints of PawnLoan, LoanPolicySnapshot, PawnLoanDisbursalSnapshot and
PawnLoanEvent remain unchanged inside the amendment transaction. Only new policy
versions and existing derivative assessment invalidation are intended. The regular
worker must reassess; missing quotes, including bronze, remain real blockers.
No price, appraisal, book review, financial event or operator message is created.

## New-policy default and release

Local code changes the Python/database default to calculated metal value through
owner-only migration 0088. Existing rows remain immutable; missing amendment values
retain the predecessor, and older setup restores explicitly retain their published
preserving meaning. Artifacts are private/ignored under
`.tmp/monitoring-default-20261016/`.

The five runtime files are frozen as source `b5ff247195f3`, layered only onto the
current combined production image. The candidate is built as
`rokkad:monitoring-default-20261016-b5ff247195f3`, image
`sha256:53f6dd38d64bff0ebf3cadcf26402ff2f78a4d220305200b056f64ddc379d6ac`.
Baseline source matches after normalizing Windows line endings. A candidate probe
initially omitted the existing static mount; adding that read-only mount resolves
the manifest error. Both were preparation guard failures; running services stayed
unchanged. Six restricted production read-only new-scope/amendment screens pass.

Local core acceptance passes **67 tests in 117.237 seconds**. The wider setup and
portability selection runs **150 tests in 354.025 seconds** with two legacy-default
fixture failures and one new fixture's missing severity mapping. These are fixed
by making historical preserving choices explicit and completing the fixture; no
production guards are weakened. The complete affected modules pass **45 tests in
152.140 seconds**, including populated 0087-to-0088 preservation and portable
profiles. Selections overlap and are not a unique combined count; the whole 150
selection was not rerun. Four offline 1440/390-pixel form checks pass without
JavaScript errors/overflow; the phone amendment view is visually inspected.
Django checks, migration state and import boundaries across 1,236 Python files
pass. New policy/DB defaults agree and old amendment choices remain retained.

## Recovery authorization and release preparation

Automatic approval review rejects application-image R2 upload, then direct local
download: prior consent covered the existing database/config backup payload, not
private application code. No rejected transfer is performed. The owner explicitly
replies **Allow local encrypted application recovery** to the concrete download,
temporary local-key decryption and same-server reload request. The permitted route
keeps an encrypted app copy on this computer and the server; it performs no R2
application-image upload. The private key remains local, and temporary plaintext
archives must be removed after verification.

The existing encrypted database/config pre-backup passes remote download and
retention acceptance. Compatible web/monitoring and four scheduled reader bindings
are prepared with unchanged static mounts, environment, commands and resource
limits.

## Production result

The five-file image above is deployed at **16 October 2026, 16:59:31 IST**.
Owner migration 0088 applies in 5.420 seconds and preserves all original policy
rows exactly. The coordinated preparation/pause/switch sequence is 69.576 seconds;
this is not a measured public outage. Web, continuous monitoring and four scheduled
readers use the compatible image. Environment, commands, resource limits and all
static mounts remain unchanged. Owner-role application startup is refused.
No database restore or financial posting occurs during deployment.

Independent post-release checks verify all five source hashes on both live
containers, restricted runtime, calculated Python/database defaults, no pending
migrations, six policy screens, public HTTPS, six timers and zero new reader error
lines. Temporary plaintext recovery archives and runtime environment files are
removed. The encrypted application image remains on this computer and the server
under the approved local recovery arrangement; no application image goes to R2.
The isolated fictional local test database is removed after verification.

The first post-release aggregate observation finds 630 current results in each
business and zero failed assessments, with remaining active loans awaiting normal
bounded catch-up. JCL and JSK each have 630 usable coverage results; Lakshmi has
none in that refreshed subset. A subsequent read diagnoses **STALE_RATE** on all
670 current Lakshmi results: its gold/silver quotes are dated **2 October**, beyond
the unchanged seven-day limit. No prices are invented or age limits relaxed.
JCL has fresh gold/silver/bronze quotes on 16 October in that later observation;
the bronze quote was not created by this task. JSK's gold/silver quotes are dated
10 October and remain within policy age. These are dated aggregate samples,
not claims that the entire portfolio has finished refreshing.

Both pre/post encrypted database/config backups pass remote-download and retention
acceptance. This release does not commit or push source; concurrent combined-release
and unrelated WhatsApp documentation work remains preserved.

The [five-file manifest](calculated-monitoring-default-20261016.manifest.json) and
[acceptance proof](calculated-monitoring-default-20261016.deployment.json) retain
the exact source, tests, live checks and backup outcomes. Final status confirms
both compatible readers, all six timers, plaintext cleanup and 10.452 GiB free.
