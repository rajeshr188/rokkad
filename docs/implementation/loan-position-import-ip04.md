---
status: implemented-and-rehearsed
owner: loans
updated: 2026-10-09
tags: [loans, import, batch, rehearsal, provenance]
---

# IP-04: reviewed closed-position batch conversion

Follow the [accepted decision](../adr/2026-10-09-loan-position-import-without-earlier-history.md)
and [ordered plan](../plans/loan-position-import.md). The conversion service and
operator command are implemented and tested. Real-source admission is rehearsed
in a private production-derived database. Production records and schema remain
unchanged; this record does not claim the live conversion complete.

## The temporary JCL correction

The owner clarifies that the 190 JCL records already recognised as released but
missing release rows are a one-time recovery cohort. Future missing release rows
must not inherit that interpretation. Remove IP-03's schema-wide inference:
the adapter now requires an explicitly supplied exact source identity and
unchanged source-document hash for each member. Without that binding, the
no-release-row claim is held for separate review. The generic closed-position
contract still supports explicitly reviewed owner positions; it does not infer
returned custody from the Workspace or source schema.

Freeze the 190 identities from the earlier accepted inventory on the server,
checking every current immutable snapshot against that inventory. The cohort
digest is `ed45fc0a2ef6297babdb058d9f10782b559af0e8d48b1d4b1389f8f0738912aa`.
The operator loader requires exactly 190 JCL source keys and SHA-256 fingerprints.
This is a private recovery input, not a setting, product, standing policy or
staff-facing switch. Keep it with recovery evidence after conversion; do not
expand it or use it to admit future records. No release row/date is invented.

The fresh read-only census has unchanged source fingerprints:

| Workspace | Eligible closed positions | Held date conflicts |
| --- | ---: | ---: |
| JCL | 26,649, including the exact 190 | 15 |
| JSK | 3,836 | 4 |
| Lakshmi | 8,711 | 0 |
| Total | 39,196 | 19 |

The 19 contradictory date pairs remain retained and unconverted. Their dates are
not corrected or dropped to make them pass admission.

## Conversion and resumption

[closed_position_batch.py](../../apps/tenant_apps/loans/services/closed_position_batch.py)
orchestrates the existing IP-03 preparation/writer. A private signed manifest
binds the Workspace, actor, review day, exact proposed position, source evidence,
Party/series mappings and accepted snapshot digest. Review changes no loan or
counter. It rejects duplicate source identities and normalized loan numbers.

Commit uses one transaction per chunk of at most 100 records. Current owner,
action, business-write, Workspace and source/mapping checks run again. Number
collisions and future reserved ranges remain mandatory. Changed source families,
conflicting existing origins or revoked access stop the chunk; the whole current
chunk rolls back. Previously committed chunks remain valid.

Successful HistoricalLoanImport provenance is the durable progress record.
Identical retries return the existing loan and record no additional event or
number reservation. Progress output is emitted after the chunk commits. Re-run
from its start or from zero after interruption; a log offset alone is not proof
of admission. A daily review expires; refresh an unchanged earlier manifest into
new review files, preserving its original position date and accepted digests.
Changed facts or mappings cannot be approved by this refresh operation.

LockedNumberClaims builds a current number/source-alias index once per bounded
transaction, after the same Workspace and sequence locks used by admission.
It shares the ordinary claim/range rules, updates the in-memory index for each
new claim, and cannot be reused across transactions. This avoids repeatedly
loading all source graphs for every loan. Ordinary entry retains its existing
claim path and all guards. No runtime role is elevated and no guard is disabled.

The ordinary loan retains its original evidence FK and all source/photo access.
Only the CLOSED loan, sole zero position checkpoint, immutable import provenance
and audit evidence are added. No approval, disbursal, receipt, interest, release,
inventory movement or unknown lifetime cash total is manufactured.

## Operator sequence

Use the restricted runtime configuration for review/conversion, never the owner
database role. The command refuses an outer transaction so chunks really commit
independently. It produces private create-only manifest, token and exception files.

```text
python manage.py convert_legacy_closed_positions --workspace-id WORKSPACE --actor-id OWNER --manifest NEW_REVIEW.json --review-token-file NEW_REVIEW.token [--owner-return-cohort FROZEN_JCL_190.json]

python manage.py convert_legacy_closed_positions --workspace-id WORKSPACE --actor-id OWNER --manifest NEW_REVIEW.json --review-token-file NEW_REVIEW.token --apply --confirmed --batch-size 100 --start 0

python manage.py convert_legacy_closed_positions --workspace-id WORKSPACE --actor-id OWNER --refresh-manifest OLD_REVIEW.json --manifest REFRESHED_REVIEW.json --review-token-file REFRESHED_REVIEW.token
```

The frozen JCL file is needed only when preparing that one-time legacy cohort;
other Workspaces and later ordinary imports do not use it. Exact existing Party
identities and legacy LINODE register mappings are required; names do not merge
borrowers and missing setup is not silently created.

## Verification performed

170 checks pass in a fresh PostgreSQL database, including real concurrent replay,
chunk rollback, duplicate/collision refusal, changed snapshots, current authority,
review expiry/refresh, restricted-role immutability/RLS, native/paper compatibility,
ordinary browsing and media portability. Migration consistency reports no changes.

Build a bounded 28-file candidate from the current live image, preserving deployed
billing. Restore a catalogued server-only snapshot into
rokkad_ip04_rehearsal_20261009. Apply only Loans migration 0065 with separately
injected owner credentials. The production target/role startup guard correctly
rejects the clone's database name; a separate rehearsal-only settings copy binds
the isolated target. The actual production guard and settings are unchanged.
Restricted startup and migration consistency then pass.

The restricted runtime admits these real-source samples in the isolated copy:

| Workspace | Rehearsed admissions | Included owner-only cohort | Successful retries skipped |
| --- | ---: | ---: | ---: |
| JCL | 290 | All 190 | 50 |
| JSK | 50 | 0 | 50 |
| Lakshmi | 50 | 0 | 50 |
| Total | 390 | 190 | 150 |

Every new position is ordinary CLOSED, zero debt and returned custody with linked
retained evidence. All original loan, event, import-provenance, retained-source
and sequence row fingerprints match before/after. No disbursal/release is added.
Media mounts are read-only. This is a 390-record rehearsal, not a claim that all
39,196 have been admitted or all source media bytes were reverified in this slice.

Private manifests, checkpoint, settings copy, image/source hashes and rehearsal
results remain under the two loan-position-import folders in the existing
server cutover directory. Raw customer graphs and photos are not copied off-host.
Ignored local operator evidence is in .tmp/loan-position-import-20261009.

## Coordinated production execution still required

Deploy the compatible nullable-detail readers and owner-only additive migration
0065 with a fresh recovery checkpoint before any live admission. Preserve the
currently deployed billing/configuration. Recheck full reviewed manifests and
counts, then run bounded chunks and reconcile all 39,196 eligible sources against
ordinary origins, with the 19 exceptions retained. Keep a compatible reader on
rollback; never restore a checkpoint over later customer actions or delete
successfully admitted immutable evidence.

IP-05 supplies directory consolidation, default ordering and measured search
acceptance. Review that presentation with the converted cohort before the full
production switch: real current admission timestamps must not bury running loans
under newly admitted old closed records. Keep true entered-at times. Search
improvement is not inferred from conversion or claimed by this slice.
