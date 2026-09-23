---
status: accepted
owner: project
updated: 2026-09-23
tags: [migration, media, portability, rls, deployment]
---

# Bind production media admission to one reviewed destination

The [attachment workflow](2026-09-22-legacy-media-attachment-evidence.md) initially
allowed rehearsal databases only. Production needs the same attachment services,
immutable receipts and conditional copies, with an explicit destination contract.

Extend `linode_media` with a non-secret `linode-media-target/1` manifest and its
reviewed file SHA-256. Bind the configured database name, TCP host/port and runtime
user, the connected server address/port and current database/user, the exact HTTPS
R2 endpoint/bucket/production application prefix, source installation UUID/archive
checksum, and each source schema's destination Workspace ID and slug.

Non-rehearsal execution requires `prod_r2`. Rehearsal keeps its existing plan
format and cannot accept a production manifest or plan. Both paths retain the
restricted-role check, Workspace authorization, source resolution, content
verification and immutable receipts. No new table or alternate storage pipeline
is introduced.

Production plans have a `linode-media-plan/2` header containing the manifest file
checksum, including when there are no attachment rows. Apply requires that exact
header, checks the entire plan and its destination/source bindings before copying,
and rejects duplicate source identities. A changed manifest requires a new plan.
Hashes detect changes against the operator's reviewed files; they are not digital
signatures and do not establish who approved them.

Default storage must match the manifest and use private ACL settings, signed URLs,
verified TLS, no public custom domain and no overwrite. These are configuration
checks, not proof of remote bucket policy or network reliability. The destination
host still needs authenticated upload/read/print checks with durable credentials.

Completed media admission does not mark a deployment production-ready. Provisioning,
fresh source reconciliation, backup recovery, timed hosted rehearsal and the final
all-branch freeze remain governed by the [cutover runbook](../implementation/linode-production-cutover.md).
Never generate a real target manifest by substituting the old server or practice
Workspace IDs while the separate destination server remains uncreated.
