---
status: accepted
owner: project
updated: 2026-09-12
tags: [loans, portability, evidence, migration]
---

# Preserve unknown legacy validity and unverified valuations

The absolute conversion prohibition below is superseded by the narrowly audited
[September 22 verification workflow](2026-09-22-verified-legacy-license-continuation.md).
Unknown source evidence and every imported loan's original revision remain intact.

The jcl owner confirmed that licence validity was never recorded and that the
stored valuation is old. Active opening balances, custody, three-month maturity
fallback and three grace days have separately been reviewed for C00121. Requiring
invented legal dates or promoting the old amount into a current appraisal would
misrepresent the source.

## Decision

Reuse the existing Workspace-owned licence and immutable revision tables. An
explicit `is_legacy_reference` licence is inactive, has both validity dates null,
and is represented by a `LEGACY_REFERENCE` revision. Its number field retains a
source grouping label, not a verified legal number. Ordinary licences/revisions
still require both dates. Database constraints enforce those shapes; triggers
prevent conversion between reference/verified identity, mismatched revision kinds
and disbursal under a legacy reference. Existing forced RLS and revision
immutability remain in force. No new tenant table or generic bypass is added.

The owner-only `create_legacy_license_reference` service requires a bounded
source label and evidence reference and records the normal setup audit. Amend,
renew and activate reject a legacy reference. Verified setup is created separately.
Series can retain grouping and allocate release receipt numbers; loan-number
allocation remains blocked. Expiry registers show unknown validity and expiry
notices are unavailable, rather than computing dates from null values.

Only the opening command accepts optional nonempty `setup.legacy_license_evidence`.
It must map to the inactive legacy-reference revision, with the source label still
matching. Complete-history import retains verified-licence requirements. The jcl
bridge verifies the label against freshly extracted source rows.

Opening review v2 supports an explicit unverified valuation object with exact keys
`status: UNVERIFIED`, `source_amount`, `source_date`, `evidence_reference`. Unknown
amount/date are null. Non-null values remain bounded and dated claims cannot
postdate cutover. This alternative creates no CollateralAppraisal or current-value
cache. Existing reviewed amount/date appraisals remain supported unchanged. A null
valuation object still means an unfinished review and fails validation. v1 and
strict complete history do not acquire this alternative.

The jcl dump has no dated item appraisal. Its bridge rejects a supplied source date
and permits assigning its old loan-level amount to an item only for a single-item
loan and only unchanged. Multi-item totals remain in the source graph rather than
being apportioned without evidence. The owner review and imported loan detail label
these as unverified source values. Current collateral value and LTV stay unavailable
until actual dated appraisal/monitoring evidence is available.

A reviewed opening with unverified values may settle all debt and return every
outstanding item without an appraisal: retained exposure is zero and no unknown
amount is substituted into the settlement. Custody, balances, permissions, original
collection rules, concession and reversal checks still apply. Native loans and
partial release retain their valuation requirements. The ordinary release-number
allocator permits only release receipts under an active legacy series; it never
permits new loan numbers for that reference.

Exports retain the original setup flag and unverified source values in immutable
opening evidence. Restore creates no initial appraisal for them, but restores a
later first appraisal (version 1) when present. Semantic reconciliation, source
identity, dated servicing and retry guarantees remain unchanged.

## Delivery and pilot

Migration `loans.0012_legacy_opening_evidence_gaps` alters existing tables and adds
the database guards. Ordinary web/worker/import processes remain on the restricted
runtime role. Source attestations are migration evidence, not verification of
licence compliance or current collateral worth. Production cutover is not approved
by this change.

The isolated C00121 pilot is staged with source-verified evidence and a rolled-back
preview. Its principal obligation uses the owner-selected original maturity; its
recognized interest is payable as of the confirmed cutover, without claiming older
itemized interest due dates. The ancillary policy uses existing application defaults
with latest-appraisal valuation; the named opening rule still owns collection.
Final review covers that exact prepared input before financial commit.

See the [operator flow](../flows/legacy-opening-import.md),
[v2 review contract](../contracts/loan-opening-review-v2.md) and
[first-import plan](../plans/first-legacy-import.md).
