---
status: completed
owner: project
updated: 2026-09-21
tags: [migration, media, r2, evidence]
---

# Linode media preservation in private R2

This record covers file preservation for the reviewed three-Workspace migration.
It does not certify application attachments or final production readiness.
The source is still live; the frozen database/media cutover remains separate.

**Completed:** all 32,554 file copies and read-back hashes passed; destination keys
and sizes reconcile. Thirteen reports/manifests are also copied and hash-verified
under the R2 preservation prefix. The final state is
`MEDIA_PRESERVATION_VERIFIED_ATTACHMENTS_PENDING`, with zero application attachments.
Private `review.html`, `verification.json`, `evidence-copy-receipts.json` and
`evidence-manifest.json` are under `outputs/linode-media-copy-20260921/`.

## Scope and destination

The owner explicitly approved the private `rokkad-production-media` bucket and
the bucket-only Object Read & Write token `rokkad-media-migration-20260921`, with
a one-week expiry. The owner saved the S3 credentials privately in LocalAppData,
outside OneDrive. Authenticated HEAD/LIST confirmed access and an empty bucket.
The pre-existing repository `.env` points at a different Cloudflare account and
was not used or changed. Permanent application credentials are still required.

The plan binds **32,554 files**, **591,274,335 bytes** (about 564 MiB):

| Group | Files | Meaning |
| --- | ---: | --- |
| Branch originals | 31,405 | Every inventoried file in JCL, JSK and Lakshmi's media trees, including files absent from the discovery photo-reference list. |
| Unresolved shared candidates | 1,149 | Older shared-folder files whose paths match missing JCL references; ownership is unproved and they are not attached. |

The copy-plan SHA-256 is
`996167ba5aee97bf7033f236a49eedd6c0c61bf63029384c475ac00cafa26eef`.
Objects use prefix `media/legacy/6ca968d626474dbb8e3924f0c1a12ed6/`, followed by
`branch/<schema>/<content-sha256>/<original-path>` or
`unresolved-shared/<source-folder>/<content-sha256>/<original-path>`.
These are preservation keys, not mutable application FileField names.

## Transfer and verification boundary

Private operator helpers and receipts are under
`outputs/linode-media-copy-20260921/`. The local isolated SDK is boto3 1.43.98;
it does not change application requirements or the production Python environment.
The helper signs object-specific conditional PUT and GET URLs for 15 minutes and
sends them over SSH stdin to a standard-library Python worker. No long-lived R2
credential, signed URL or media file is saved on Linode, and no media bytes pass
through the owner's computer. Receipt files contain paths, hashes and outcomes.

Each source read rejects symlinks/path escape and checks type, size, byte hash and
file stability against inventory. Conditional `If-None-Match: *` refuses overwrites.
Every object is read back on Linode and SHA-256 verified. A 15-file sample passed;
retrying all 15 returned precondition failures for PUT and verified the identical
existing bytes. Nine local source-path, size and destination rejection checks passed.

Initial transfer concurrency was four workers. After 1,000 verified objects, the
exact task-owned remote helper was stopped and the copy resumed from recorded
receipts with 32 small-file workers. No application process was stopped; the
largest inventoried file is 329,608 bytes. Partial uncheckpointed copies remain
safe to retry through conditional creation and read-back verification.

Final preservation checks passed: every plan key/size matches the destination
listing, all copy receipts verify, and evidence manifests are separately saved
and hash-verified in R2. An unsigned GET of a known collateral photo from Linode
returned HTTP 400 with `InvalidArgument: Authorization`; no image bytes were
returned. This explicit authentication rejection is the observed result, not an
invented 403. An earlier local urllib TLS failure was not counted as access denial.
The authenticated bucket Settings page shows no custom domains, the public
development URL disabled, Standard/APAC storage and no object-expiry rule.
The only lifecycle rule aborts incomplete multipart uploads after seven days.
There are no bucket lock rules: do not claim provider-enforced immutable storage.

## Association preparation and exceptions

| Discovery reference class | Verified branch file | Missing branch file |
| --- | ---: | ---: |
| Customer photograph | 1,148 | 5 |
| Active collateral photograph | 5,988 | 102 |
| Closed-history photograph | 21,088 | 3,507 |
| Total | 28,224 | 3,614 |

The 1,149 separately preserved shared candidates cover 23 active-photo references,
1,121 closed-photo references and five customer photos; none is an approved match.
Another 2,465 references have no exact path in the checked branch/shared folders.
Separately, **203 of the 6,293 active collateral items have no source photo
reference at all**. Missing-reference and missing-file cases must remain distinct.
Loan balances and custody facts are not changed by media copying or these findings.

Offline re-extraction from the same hashed SQL archive retained all 1,153 customer
photo rows, including default flags and raw-row hashes. They belong to 1,147 source
customers: six have multiple photos, two have no marked default, and none has
multiple defaults. Retain every image; do not invent a default selection or original
capture date. Named active-loan exceptions are available in the private report.

## Remaining work

Create an authorized, retry-safe attachment path for exact imported Party,
collateral and historical-evidence identities. Use separate application copies
so photo replacement/document cleanup cannot delete the preserved originals.
Keep existing Workspace routes and RLS authorization; test denied anonymous,
cross-Workspace and revoked-user access and permitted rendering/downloads.

Active photos need explicit legacy provenance, not a false new capture claim.
Closed-history photos need immutable authorized attachment retention without
creating operational loans or editing accepted archive documents. Keep missing
originals as visible exceptions; newly taken photos are new evidence. Add/test
actual Django R2 storage dependencies, isolate rehearsal/production credentials,
and do not deploy using the expiring migration token.

Final cutover still needs fresh source preparation, a scheduled write freeze,
and complete database/media reconciliation. See the
[media plan](../plans/linode-media-to-r2.md) and
[preservation decision](../adr/2026-09-21-legacy-media-preservation-and-application-copies.md).
