---
status: completed
owner: project
updated: 2026-10-08
tags: [loans, production, deployment, retention]
related: [../plans/loan-origination-completion.md, loan-release-preparation-lo06.md]
---

# LO-07 production release

On 8 October the owner approved the recommended ongoing retention and explicitly
requested completion of the production switch with the LO-07 sequence. The owner
subsequently confirmed document/printing and Loan health screens were checked and
satisfactory. This does not post a transaction review, certify every loan's books,
or approve D01623's separate production correction.

## Exact target and candidate

- Host: existing Linode `172.235.9.64`; database `rokkad_production_20260924`.
- Application: `rokkad:loan-origination-5f10b597-server`, commit
  `5f10b597d6229d3a74b4c5fd6f1207595b80a143`, image ID
  `sha256:9846d3add8cfe7e16998e3befccfb1f3b10ff3563a7ae7b705932b2f4e850408`.
- [Exact-candidate CI](https://github.com/rajeshr188/rokkad/actions/runs/37713872975)
  passes, including 2,138 Loans tests; LO-06 verifies actual source/media recovery.
- 35 pending migrations: Loans 0033 through 0063, including branch/merge nodes;
  data_portability 0018 and 0019. Owner-only migration settings explicitly target
  production. Restricted roles run web and scheduled readers.
- Canonical `production-compose.yml` retains env-file references, settings,
  ports/network and non-static mounts. Only web image/static volume change.
  Candidate static volume: `rokkad_production_static_lo07_5f10b597`.
- Mail dispatch, feedback, recovery and watchdog command use the same candidate
  and guarded startup. Storage inventory follows the web container.

## Retention installed

The host-only [operator](../../scripts/retain_operational_backups.py) runs as
`ExecStartPost` of `rokkad-production-backup.service`, through
`/etc/systemd/system/rokkad-production-backup.service.d/30-retention.conf`.
Its installed SHA-256 is
`c6f482ac8c69d997bf01ad7cf38ce72a7cdaadb195b3233685bd8fa97a6c136d`.
The application candidate is unchanged by this host operator installation.

Keep the newest 24 successful hourly copies plus the latest copy for each of
the last 30 UTC dates, deduplicated. Verify checksums and retained catalogues
under the existing backup lock before removing completed operational dump pairs.
Recheck inspected file identities before the first deletion. Ignore partial files
and unrelated/checkpoint names; separate release folders are outside the scope.
Preserve the 5 GiB backup guard. The private audit records validated plans and
completed expiry; `retention-last.json` also flags space below 8 GiB.

Nine fictional boundary tests pass on Windows and Linux, including Linux symlink
protection. First service run at **08:30 IST** succeeds: 35 copies inspected,
31 retained, four expired (289,474,728 bytes). Free space is about 10.7 GiB.
Timer remains active. These checks do not establish external failure alerting
or an off-host copy; those remain separate operational follow-ups.

## Checkpoints and smoke preparation

A fresh read-only exported snapshot at **08:37 IST** covers 186 source tables.
Dump SHA-256:
`7e40bfb2858612254785f0cc1fdbacf1e4d5c3f02bdf5f32171b6d95fba0f55c`.
All 30,293 required media files (942,099,334 bytes) match frozen SHA-256/ETags;
the matching manifest reuses immutable protected LO-06 checkpoint bytes. No R2
uploads/deletes or off-host export occur. Referenced metadata is stable before/
after capture. The final write-pause checkpoint supersedes this readiness copy.

Prepared read-only smoke checks pass on the isolated candidate stage: selected
loan detail/collection reads, direct/paper editor, repayment/full-release GETs,
Loan health GETs, two issued PDF hashes and no-context/cross-Workspace isolation.
The first probe called a nonexistent document helper; using the existing
`loan_ticket` method corrects the operator probe without an application change.
No sessions, loans, receipts, releases, document issues or messages are created.

## Production sequence and compatible recovery

1. Pause the six previously active timers; let current readers finish, then stop
   web gracefully. The write pause begins **08:43:54 IST**.
2. Capture final read-only database snapshot and matching media bytes/manifest;
   validate catalogue/checksum and retain source row fingerprints privately.
3. Grant the existing restricted runtime role without rotating/relaxing it.
   Apply owner migrations. Compare all original business columns excluding only
   migration/content-type/permission metadata. Check restricted startup/schema
   and owner-startup refusal, plus actual production read-only business smoke.
4. Install prepared compatible timer/watchdog drop-ins and canonical compose;
   start candidate web, verify local and public HTTPS, and verify actual reader
   env/settings through guarded `--help` commands before resuming timers.
5. Resume exactly the previously active timers; verify post-release backup and
   retention. Record exact deployed image, checks and remaining acceptance limits.

Failures before migration can resume the unchanged old deployment after review.
Once migrations start, recover forward with a compatible candidate reader; do not
downgrade blindly or restore a pre-release checkpoint over later transactions.
All customer files, full dumps, raw logs/config and financial row fingerprints
remain in the approved mode-0700 server folder
`/home/rokkad/deploy/cutover-20260924/loan-continuation-20261006-b69df6ab`.
No database restore over production is part of this release.

D01623 remains an uncorrected DRAFT with zero recorded debt until its own reviewed
financial correction. Its confirmed agreement is retained; software deployment
does not invent a payout or fabricate completed corrected-paper acceptance.

## Completed rollout

The coordinated production release completes at **08:49:10 IST, 8 October**.
The final write-pause snapshot is **08:44:21 IST**, 88,598,984 bytes, SHA-256
`ce671467d6530cb225896af06c711650c3fd21a4e366216f93780b30f0f5d9c8`.
Its matching media manifest SHA-256 is
`a62018abc50069e504660c94d7a80157d264ad37a23d72daca665a6496d33290`.
All 30,293 file hashes are checked; protected existing checkpoint bytes supply
every referenced file, with no additional media download or R2 write.

All 35 owner migrations apply. **183 original business projections remain exact**.
Restricted startup, no pending migrations/schema drift, owner-startup refusal,
actual production business/document/monitoring reads and tenant isolation pass.
RA00500 remains active at collection 61,200; C07557 active at 8,170; 06716 closed
at zero; D01623 remains draft at zero. No financial action/document issue/message
is created by smoke checks. Normal previously configured jobs resume separately.

Canonical compose and four mail-reader drop-ins are installed. Candidate web
responds locally and through verified public HTTPS at `https://rokkad.com`.
Actual timer/watchdog command settings pass guarded help checks before all six
previously active timers resume. The site is available before the final backup
finishes; the completion timestamp includes post-release verification.

The post-release database backup and retention succeed at **08:49 IST**:
32 completed copies inspected, 31 retained, one expired. Free space is
**11,228,110,848 bytes** (about 10.5 GiB). Private `lo07-deployed.json` retains
exact rollout results; `lo07-final-health.json` records the subsequent live role,
migrations, cohort, timer, log-error and backup checks. Off-host recovery and
external backup alerts are separate follow-ups, not completed by this release.

At **08:53:40 IST**, the actual web image matches the pinned candidate, runs as
app with restricted database role `rokkad_prod_runtime` and no owner credentials,
and reports 202 tables with Loans 0063 / portability 0019. All **6,739 ordinary
active/closed loans** calculate: JCL 2,625, JSK 1,674, Lakshmi 2,440. All 39,215
unadmitted archive identities remain unchanged. This does not certify complete
books, green valuation or monitoring freshness. No automatic conversion occurs.
All six timers are active; mail feedback/recovery/health have completed normal
post-release runs successfully, with dispatch observed running its next turn.
Candidate web logs show zero error/traceback lines.

The fresh post-release dump is 88,862,726 bytes, SHA-256
`1e7c294e1eb33676d0cf7bf6b38a544d4b0b4bbcbd71acfe0b287120f6a9f469`;
checksum/catalogue checks pass. Final observed free space is 11,219,484,672 bytes
(about 10.4 GiB). Preserve the final checkpoint and compatible reader independently
of ordinary hourly expiry. See the recovery runbook for the off-host limitation.

At **08:56 IST**, dispatch's normal scheduled turn also finishes with success
and exit status zero. The 17 bounded nonsecret operator sources are preserved
in `lo07-operator-sources/`, with manifest SHA-256
`57f935859a55bff3aa29c89289bc23de5f54163cc19339f179c0b6f0b1e1333c`.
The finalized nine Linux retention tests pass again; the Windows external-symlink
case passes separately after tightening its fixture. No customer artifacts leave
the approved server scope.
