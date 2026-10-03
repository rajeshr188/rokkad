---
status: accepted
owner: project
updated: 2026-10-02
tags: [khata, servicing, recovery, audit, rls]
---

# Khata operator forms and native recovery

The owner requested the next implementation slice after shared summaries and
documents. Existing Loans-owned khata services already define financial and
custody rules. Connect ordinary Django forms to those services, with separate
khata URLs and no changes to pawn posting or numbering.

Cash movements, opening approval, terms approval/activation, exchanges, handovers,
settlement and bounded corrections use a server-generated preview followed by a
CSRF-protected confirmation. Signed reviews bind instructions, request UUID,
workspace, actor, account, action and business day; they expire after 30 minutes.
Confirmation uses the original service review hash, so changed source evidence,
prices, photos or policies cannot silently change the reviewed operation. Services
recheck current authorization and business-write availability, and preserve their
idempotent retry behavior. Photo uploads are a direct validated POST. Source dates
remain today-only. Proposals and opening drafts are reviewed but do not activate
terms or imply cash received. Only the existing bounded corrections are exposed.

The owner-authorized usability extension combines receipt and optional photograph
in one direct validated save with an explicit actual-receipt checkbox. It preserves
separate immutable DEPOSIT/PHOTO sources, binds photo bytes into retry identity,
rolls back receipt rows on photo failure and cleans only newly written private
files. No temporary upload staging or financial-policy change is introduced.
Exchange search is read-only; confirmation keeps the signed-review contract.
See the [checkpoint](../implementation/khata-collateral-usability.md).

Expose series setup to authorized setup administrators, and WARN/BLOCK policies
to the workspace owner. Independent series remain a first-class choice. The
service menu uses a disclosure, with permission-aware links and readable item/
source choices. Private photo reads verify bytes and remain workspace-scoped.

Use a fixed, versioned `khata-native-recovery/1` ZIP for native disaster recovery.
Capture all thirteen khata tables, full original source JSON, exact decimal/date/
UUID values, series counters, policy/terms revisions, periods and exact segments,
allocations, custody selections, original photographs and issued PDF bytes.
Retain external prerequisite identity fingerprints and canonical reconciliation
at the export date. Capture under a workspace and table write lock. Do not reuse
pawn history formats or create an old-paper import path.

Recovery is deliberately exact-identity and offline: an empty khata destination
in a matching restored database, with original workspace/borrower/staff/licence/
rate identities already present. It is not a workspace clone, merge, import,
replacement of existing evidence or complete workspace backup. Require a trusted,
independently retained archive SHA-256. Edited or third-party archives are outside
this contract. The table-owner process has the same trust boundary as database
disaster recovery, rather than an application financial-admission endpoint.

Only the table owner can temporarily disable khata user triggers within the
restore transaction to preserve historical immutable rows and final projections.
Forced RLS, foreign keys, checks and uniqueness remain enabled. No runtime-role
bypass, session setting or new privileged callable function is introduced. All
triggers must be enabled at entry; they are enabled before commit and PostgreSQL
rolls back their state on failure. Validate typed ownership/parent references,
media/payload hashes, and restored P/U/interest schedule/held/eligible custody.
No ordinary-loan rows or numbering counters are changed. Advance khata database
PK sequences monotonically after exact insertion.

Default restore is an actual rolled-back preview, including reconciliation,
without media writes. Commit requires the original workspace slug confirmation
and owner-only settings. Refuse existing destination evidence and conflicting
media; clean up only newly created files if a restore fails. A separately reviewed
pilot and complete database/private-media backups remain production gates.

See the [operator and recovery flow](../flows/khata-servicing-and-recovery.md).
