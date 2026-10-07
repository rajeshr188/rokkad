---
status: implemented
owner: project
updated: 2026-10-07
tags: [loans, origination, correction, recovery]
related: [../plans/loan-origination-completion.md, ../adr/2026-10-07-shared-loan-entry-and-explicit-origination-correction.md]
---

# LO-01 actual-paper origination correction

## Implemented behavior

An eligible reopened draft offers **Correct recorded origination**. Administration,
create, edit and payout authority are checked again at the financial command.
Staff review actual item principals/rates, tenure, advance interest, document charge,
proceeds, source reference and an explicit correction reason. The review names the
retained payout/reversal pairs. Confirmation records completed business; it does
not pay the customer again or invent an original digital approval.

The ordinary recorded-history writer retains loan, number and item identities and
creates one supported current recorded origin/schedule. Old native approvals,
payouts, reversals, snapshots, schedules, photos and issued documents survive.
Preview rolls back; signed stale review and concurrent/repeated submissions cannot
produce two origins. Same-day neutral attempts remain in balance folds, while
validated IDs are excluded from later-activity checks. Recorded receipt correction
and monitoring continue against the actual agreement. Printed recorded copies
identify the correction and distinguish original date from recording time.

This first profile supports only fully reversed same-day native attempts with no
incompatible financial/custody/funding dependencies. Actual original identity/date
and physical collateral must already be correct. A later-date reversal or changed
jewellery evidence requires broader reconciliation. Ordinary draft admission and
retained-native review retain their existing prerequisites and do not fall back.

Exact Workspace recovery includes the complete graph/files. Bounded per-loan
servicing export refuses the new profile explicitly; embedded retained native IDs
cannot be copied into another Workspace without a remapping contract.

## Verification

All **17 correction tests** pass, including receipt insertion/restatement, review
rollback/staleness, purpose binding, duplicate/concurrent retries, authority,
restricted-role posting/isolation/immutability, exact graph/file recovery,
monitoring and recorded-document projection. The separately repeated opening
recovery case also passes (**18 tests**, 32.690 seconds).

The initial adjacent run executed 258 checks: 256 passed, one incorrectly named
test module did not import, and one opening-recovery fixture encountered a
PostgreSQL lock deadlock. The invocation is corrected; the new transactional
fixture takes the established recovery locks before creating rows, and the failed
recovery case passes on repeat. The final presentation/retained-native/correction/
servicing-dependency run passes **75 checks** (69.637 seconds), including all 17
correction checks against the final source. Documentation links, import boundaries
and whitespace pass.

At **11:06:13 IST, 7 October**, a restricted-runtime diagnostic corrected D01623
only in the previously approved private staging database. Production was checked
read-only immediately beforehand: it still contained only the 2 October payout
#19388 and reversal #19390, with DRAFT state and original date 24 September.

Staging retains loan **19330**, collateral **19393**, approvals, photos, old events,
two disbursal snapshots and two schedules. One unreversed recorded origin now
establishes 2,100 principal, 84 advance, 10 charge and 2,006 proceeds. Preview left
the draft unchanged and confirmation retry added no duplicate. Recorded debt is
2,100; interest stays zero through 24 October and increases by 84 on 25 October.
The recorded-anniversary/3 contract drives ordinary servicing/exposure reads.

The diagnostic used read-only source overlays on the pinned ef3c82a5 staging
image, with source hashes recorded in the approved private server folder. It is
**not a clean final-candidate build or production acceptance**. Stage book
completeness was not attested. Actual media was not recovered in this diagnostic.
The original stage cold backup remains available; staging now intentionally
contains the demonstrated correction. No production correction, migration or
deployment occurred. Final clean-candidate CI/recovery remains LO-06 work.

## Early LO-00 operational discovery

Read-only metadata at **10:54:17 IST, 7 October 2026** found **1,792,262,144 bytes**
free (about 1.67 GiB), 3,023,034 free inodes, staging database 702,118,935 bytes,
PostgreSQL WAL 654,311,424 bytes and no PostgreSQL temporary files. Production
database size was 770,407,447 bytes. These are dated capacity measurements, not
evidence that a full image/checkpoint/media recovery will fit.

Production uses private R2 prefix `media/application/production/linode-rls`.
Nonempty file references cover Party identity documents/photos, collateral photos,
historical attachments, document assets and issued PDFs. References can share
objects; field counts are not a distinct-object or byte inventory. The current
credentials received `AccessDenied` for bucket versioning metadata; versioning is
unverified. No customer media was downloaded and no credential was printed.

Before heavy release rehearsal, measure distinct required object bytes and restore
headroom, verify object checksums and representative issued files, and establish
the permitted recovery snapshot/version mechanism. Capacity needs a concrete
remedy after size measurement; do not globally prune images or unrelated backups.
Final media recovery, source/staff acceptance and the clean release candidate
remain LO-05/LO-06 work.
