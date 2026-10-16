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

Exact source/image identities, CI results, rehearsal and deployment outcomes are
recorded here as preparation completes. This initial entry is preparation only.
