---
status: complete
owner: operations
updated: 2026-10-10
tags: [backups, storage, cleanup]
---

# BS-02 scoped application-image cleanup

The owner authorizes proceeding after the [storage review](backup-storage-review-20261010.md).
Execute only the 25 candidates in the reviewed private manifest, after fresh
reference and backup checks. Unrelated local billing changes remain excluded.
No runtime deployment, business-record mutation or retention change occurs.

## Recheck and execution

Approved private manifest SHA-256:
`7b82e8a4e003ea9e61335cec10171ef59d2afd2ef5175a693c0845b495dfdc20`.

Fresh checks inspect all running/stopped container image references, 106 retained
release/rehearsal metadata files, 33,552 current script/config files and 20 service
configuration files. All 25 candidates remain eligible; all 89 previously protected
images remain present. Exact image identities, creation dates, size and tags match.

Verify the live image and HTTPS, all six timers, the latest dump SHA-256, fresh
backup timestamp and archive catalogue. Catalogue verification runs without a
database connection or network and exports no customer rows.

Remove only the reviewed tags after identity and container-reference rechecks,
without force. All 25 images are removed; none are refused or skipped. Preserve
all protected image identities and all existing container-to-image bindings.
No generic Docker, volume or build-cache prune is run. No database, rehearsal,
media, backup, checkpoint or filesystem-reserve deletion is included.

## Measured result

| Measurement | Result |
| --- | ---: |
| Available before removal | 7.574 GiB |
| Net available-space recovery | 2.553 GiB |
| Available at post-cleanup capacity check | 10.127 GiB |
| Protected images preserved | 89 |
| Removed reviewed images | 25 |
| Current retained full dumps | 34 |
| Full-retention upper bound at latest dump size | 53 copies; 8.113 GiB |
| Projected available space at full retention | 4.817 GiB |
| Remaining deficit to 5 GiB cutoff | 0.183 GiB, before growth |

Capacity measurement is taken at 03:30:58 IST on 10 October. Containerd storage
is now 36.934 GiB. Docker lists 92 remaining images and reports 4.425 GB of
potentially reclaimable build cache; this is a broad estimate, not a reviewed
cleanup manifest. No cache removal is performed or included in this scope.

Shared layers and cache mean recovery differs from the 3.14 GiB image-unique
estimate. The measured net figure includes any concurrent ordinary server usage;
it is not a promise of Docker-exclusive bytes. Build-cache removal is not needed
to claim this bounded cleanup complete and is not included.

Final live-image, HTTPS, six-timer and backup checksum/catalogue checks pass.
Approved 24-hourly/30-UTC-daily local retention remains active. Protected recovery
images, all live containers and recovery copies are retained.

The capacity projection holds other usage and the current dump size fixed;
future database growth is excluded. Current backups pass above the cutoff, but
full local-retention capacity and growth headroom remain unresolved. The earlier
2.73 GiB shortfall is a pre-cleanup projection, superseded by this measurement.

## Next

Proceed with BS-03/04 in the [ordered plan](../plans/backup-storage-and-evidence-efficiency.md):
dedicated private encrypted off-server database recovery, verified remote bytes
and actual isolated restore. Select any reduced local-copy policy only after
that acceptance. Current media credentials/bucket do not automatically authorize
database-backup upload. Alternatively, add enough disk capacity for the cutoff
and growth headroom. Existing immutable posted source snapshots remain intact.

Private recheck, per-image execution journal, capacity and health aggregates remain
under `/home/rokkad/deploy/cutover-20260924/loan-position-release-20261010/`.
No raw customer evidence is exported. This is an operational cleanup; no app code
or accounting boundary changes, ADR or financial regression-test rerun is needed.
