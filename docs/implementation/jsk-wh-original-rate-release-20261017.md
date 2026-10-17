---
status: deployed
owner: loans
updated: 2026-10-17
tags: [loans, corrections, release, recovery]
related: [aggregate-checkpoint-corrections-20261017.md, ../plans/jsk-wh-original-rate-correction-20261017.md]
---

# Original-rate correction release: 17 October 2026

The owner superseded the initial 685-only proposal and authorized correcting all
active JSK WH loans carrying the inherited wrong 2% rate. The verified selection
contains 824 retained aggregate imports and two unserviced native policy-1 loans.
The owner confirms original 1.1% monthly terms, first-month interest paid upfront,
and original proceeds at 1.1% for both native loans with their saved document fees.

Application `b0d572940dd2ed3f33f8e860d6a1a3ba6202e1b2`, image
`sha256:00d351bd154c1f68d27d6c5d72302a6b2beb4352e830d8708979d7c62053de98`,
is deployed. Loans 0092 and portability 0031 admit the versioned evidence shapes;
servicing bundle 8 preserves aggregate and unserviced native legacy corrections.
Risk remains V13. The release also includes the independently reviewed dependency
and tooling update, including Django 6.1.2, covered by the same exact-source CI.

All seven [CI jobs](https://github.com/rajeshr188/rokkad/actions/runs/38986792573)
pass. Final local correction selection passes 49 cases; earlier overlapping
100 servicing and 213 portability selections are not added to that count.
The clean image passes dependency integrity and exact encrypted application
recovery, without putting the recovery private key on the server.

An isolated server-only production copy restores 222 tables and 1,160,810 rows.
Business-table fingerprints remain unchanged by the compatibility migrations.
All 826 corrections succeed through ordinary signed, locked services in one
transaction. The full retry returns 826 existing corrections and changes no
business rows. Seventy-two invariant groups preserve original append-only
evidence, unselected loans and selected identities, principal and physical facts.
All 826 risk assessments become current using the normal public worker service;
monitoring policy and missing-valuation semantics remain independent.

The rehearsal initially refuses a nullable-join batch lock before any writes;
the administrative runner locks only loan rows, and the unchanged copy is
verified before retry. This changes no application source or domain gate.

Production promotion pauses web, monitoring and six scheduled timers, drains
runtime connections, seals an encrypted stopped-writer checkpoint and verifies
remote recovery before owner-only migration. Four scheduled application readers,
web and monitoring move together. The live apply creates 824 opening corrections,
two native reversals and two corrected disbursals, retaining original evidence.
No new payout, refund, receipt or message is recorded. The principal, borrower,
loan number and collateral facts are preserved. Original erroneous source rows
remain available alongside the owner's clarification and correction history.

The read-only postcondition confirms all 826 selected agreements/items at 1.1%
and zero active WH loans at the wrong 2%. Risk catch-up verifies all 826 current
without changing valuation policy. Runtime file parity, restricted credentials,
owner-startup refusal, twelve counter screens across three Workspaces, six timers,
public HTTPS and preserved environment/resources/media/configuration pass.
Existing encrypted R2 pre/post backup recovery and retention checks pass.

The disposable rehearsal database and both hash-verified plaintext dumps are
removed after recovery/acceptance passes. Transient environments are absent;
encrypted recovery points and source/acceptance evidence remain retained.

See the [de-identified deployment proof](jsk-wh-original-rate-release-20261017.deployment.json).
Private cohort records, individual amounts, database dumps and secrets are not
committed. Release scripts and detailed private evidence remain scoped to the
ignored task directory and the production release directory.
