---
status: completed
owner: project
updated: 2026-10-15
tags: [loans, origination, release, monitoring]
related: [loan-origination-consolidation-20261014.md, recorded-borrower-correction-20261014.md]
---

# Origination consolidation production release

The owner's 15 October proceed instruction authorises the scoped software release,
production-copy rehearsal and compatible-reader rollout. Actual customer corrections,
register reservation and financial transactions remain separate business actions.

The candidate is a 94-file derivative of the deployed dashboard-sections image,
`rokkad:dashboard-sections-20261012-fb9c494297df`. Its exact baseline image ID is
`sha256:fe76e58ee9d07609059a8a59b47db09ce5a3f188b109a31cfd995533a0317c6b`.
The release image is `rokkad:origination-20261015-e8ca3ef84835`, ID
`sha256:2d00adda26f5f28af17d0e376320c87e4d45e6e0aa3125585713425363ab4f53`.
The source manifest records every deployed-base and candidate file hash; the parent
checkout alone does not represent the release. Unrelated WhatsApp, onboarding and
bronze work is excluded. Deployed risk arithmetic and collateral valuation readers
are retained. Static assets and their volume are unchanged.

Shared correction evidence requires compatible servicing/portability readers.
The candidate includes the reviewed PC-02 through PC-06 prerequisites rather than
publishing the whole dirty checkout. Sixteen owner migrations are pending: Loans
0069–0071 and 0074–0077; portability 0020–0027; Rates 0005. Loans 0072/0073 are
already deployed. All web, monitoring and scheduled reader processes must use the
compatible image before new corrections can be written.

Release review found that the native risk-notice uniqueness rule still treated
every corrected customer as the original notice intent. Migration 0077 scopes the
existing unique intent to the immutable borrower correction identity; absent or
legacy identities retain the original uniqueness. Readiness uses the same latest
identity. Old queued notices remain blocked by the delivery identity guard, and
the corrected Party needs its own consent. Same-contact correction, a separate
replacement notice, duplicate refusal and populated downgrade refusal are covered
by a real restricted-role regression. No notification is sent by these tests.

The 195-case compatibility selection completes in partitioned runs: 192 functional
Windows cases, two separately verified PostgreSQL concurrency cases and the exact
26,649-file synthetic volume case in a network-disabled Linux candidate container.
The Windows volume run was stopped because per-file reads were slow; its assertions
were retained unchanged in Linux. A final 76-case correction/servicing/readiness
suite passes. Initial raw-notice fixture omissions and an invalid test-module label
are corrected; all actual selected cases pass. System/model checks pass, 1,371 local
baseline files match production source hashes and all 94 runtime files match the
frozen release manifest. The owner-created local test database and the verified
isolated rehearsal database are removed; backups and proofs remain preserved.

The isolated on-host production-copy rehearsal passes all sixteen migrations in
20.187 seconds. Its 202-table backup contains 1,066,774 rows. All 199 original
business projections remain exact after migration; source financial rows remain
exact after the bounded worker. Restricted startup, model consistency, existing
closed/native views, risk-evidence preflight and new GET-only preparation pass.
JCL, JSK and Lakshmi each expose register preparation and three sampled eligible
customer-correction forms. Exact encrypted off-server image download, local
decryption and verified reload pass; the key never goes to the server.

All customer dumps, raw diagnostics/config and row fingerprints stay within the
existing private mode-0700 deployment folder on the host. Local ignored artifacts
contain source, fictional test evidence and safe release metadata. Neither rehearsal
nor deployment restores a backup over production.

The prepared switch pauses the six previously active timers and both application
processes, captures a fresh write-pause checkpoint, provisions existing restricted
runtime grants and applies owner-only migrations. It compares all original business
columns before enabling compatible web, monitoring and four scheduled readers,
then checks read-only business views, owner-startup refusal, unchanged configuration,
public HTTPS and post-release backups. Once migrations start, recover forward with
the verified compatible image; do not restore an old database over later activity.

## Production completion

Compatible web and monitoring start at **04:22:45 IST, 15 October**. All four
scheduled readers are verified and the six previously active timers resume by
**04:25:18 IST**. All sixteen owner migrations apply, all 199 original business
projections remain exact, owner startup is refused and actual read-only loan and
preparation screens pass. The fresh write-pause checkpoint SHA-256 is
`aaf2d225f9e3803049c7b45ffbf2a75ef7e75d51c0b09e5b349fdc87f53ae07d`.

The operator's initial environment comparison stops on list ordering after the
new pair is online. Both original sorted environment hashes and commands match;
configuration values never change. Forward completion verifies unchanged compose,
mounts/static, protected config and bounded worker resources, then completes
reader checks and resumes timers. No database rollback or old-reader downgrade
occurs. The operator now compares environment values independent of order.

Final health verifies all 94 source files in each running reader, restricted role,
no pending migrations, public HTTPS and six active timers. Both new readers have
zero error/traceback lines across their full lifetimes. The post-release backup,
encrypted remote download verification and ordinary retention pass at **04:26:42
IST**. Its snapshot SHA-256 is
`d8c25bf54d712dad58cc2ab4b7522daf47df21b4525ef9465429da6a796d70d6`.
No borrower, register, financial transaction or notice intent is created by the
release operator.

Capacity remains an operational follow-up: 8,239,222,784 bytes (about 7.67 GiB)
are free, below the existing 8 GiB warning and above the 5 GiB backup guard.
Retention preserves 32 uncovered/protected older checkpoints; this release does
not delete them to silence that warning. The disposable rehearsal database is
removed, with its verified backup and source proof retained privately.
