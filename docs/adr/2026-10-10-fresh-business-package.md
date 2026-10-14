---
status: accepted
owner: project
updated: 2026-10-10
tags: [adr, portability, pc-05]
---

# Fresh business restoration composes domain services atomically

The owner selects PC-05 in the [completion plan](../plans/data-portability-completion-20261010.md).
`rokkad-business-package/1` accompanies PC-04's private exchange with an explicit
22-model setup contract, customer register codes/files/metadata, content-addressed
media, and exact financial-to-setup bindings. Configuration is a fixed reviewed
inventory, not arbitrary Django deserialization or native database recovery.
Existing financial profiles and their reconciliation remain authoritative.
Business logo/theme/workflow travel through an explicit Org-owned settings service;
destination naming/routing/ownership and account preferences are excluded.

The standalone exporter captures setup, customers, media references and supported
financial files in the same repeatable-read transaction, then publishes its private
directory after commit. Missing media or unsupported applicable graphs hold the
export. Independent checksums establish integrity, not authenticity. Output is
private plaintext; operators protect its parent directory and transfer channel.
No customer encryption/key-management protocol is claimed by this increment.

Fresh restoration needs empty business tables, no subscription/access decision,
and no staff membership beyond the destination owner. This keeps ordinary HTTP
business activity in existing recovery-only mode. It does not change billing or
lifecycle rules. Default seeded setup is business data: provision an empty target
for this operator path rather than overwrite or silently discard those defaults.
Control-plane ownership and destination permissions remain independently checked.

Preview performs the same domain restoration in a rollback transaction and
cleans temporary file writes. One-hour approval binds actor, destination, package
digest and semantic reconciliation. Confirmed restore repeats current checks and
commits the complete supported package in one transaction. Readers never see a
half-restored business. A new immutable, directly Workspace-owned receipt retains
the source manifests/setup privately and the results, under forced RLS. Retry
returns that receipt rather than reapplying history. This is an operator-assisted
atomic path, not a new background job engine or an automatic 26,649-loan migration.

Setup restores fresh local identities and preserves immutable business dates,
contract fields, version order, numbering reservations and effective scopes.
Source users and setup author IDs are excluded. Original business setup claims
remain in the private receipt; the recording actor is local. SQL
evidence/ownership guards stay enabled. Document definitions/assets are validated
through existing validators before insertion. Source licences remain disabled;
the destination owner must review ordinary setup before lending activation.
Financial source-book completeness does not become destination book approval.

Canonical Party import remains the ordinary guarded lifecycle. A private package
option preserves the reviewed source business code through the Party creation
service, rather than consuming unnecessary temporary customer numbers. Other
imports retain their existing numbering behavior. Source document verification
is a retained claim, not a newly performed destination verification.

Whole-package transactions trade simplicity for duration and disk/MVCC costs.
Operators rehearse and schedule large transfers with adequate headroom. PC-04's
resumable individual-file exchange remains available separately. PC-06 retains
wider funding/storage/correction/zero-allocation coverage and continuation
acceptance. Legacy licence verification/attestation and quotes whose frozen source
definition differs from the current RateSource require a reviewed remapping adapter;
this version holds them rather than weakening their evidence guards.
