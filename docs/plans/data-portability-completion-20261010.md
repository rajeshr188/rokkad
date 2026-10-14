---
status: active
owner: project
updated: 2026-10-10
tags: [plans, portability, fw-007, fw-012]
---

# Complete the existing portability workflows

The [14 October borrower correction](../implementation/recorded-borrower-correction-20261014.md)
adds a later exchange boundary: histories with BORROWER_CORRECTED evidence retain
both former/current Party identities. Published loan-history and servicing-bundle
profiles refuse them until a separately versioned two-Party remapping contract is
selected and verified. Exact Workspace recovery already retains both prerequisites.
Do not drop the correction or map both IDs to the current borrower to bypass this.

The owner accepts the [10 October review](../architecture/data-portability-review-20261010.md)
and selects incremental implementation in its recommended order. Existing domain
services, published profile meanings, financial guards and forced RLS remain the
foundation. This authorizes development; production release remains a separate
verified sequence.

| Slice | Scope | Acceptance | State |
| --- | --- | --- | --- |
| PC-01 | Current staff capability catalog | Formats, limits, coverage, permissions and restore availability displayed honestly; full Workspace transfer not claimed | Verified locally; not deployed |
| PC-02 | Unified supported loan-file restore | Upload/profile detection → explicit mappings → non-posting reconciliation → exact confirmation → ordinary loan links; opening/history/servicing/closed wires retain their meanings | Verified locally; not deployed |
| PC-03 | Essential-position source adapters | Reviewed reduced-principal active checkpoints and closed-register templates; no invented earlier transactions or reuse of the JCL exception | Verified locally within documented bounds; not deployed |
| PC-04 | Representative-volume exchange | Bounded, consistent, resumable Party/financial/media chunks; real JCL/Lakshmi size, connected identity and numbering checks | Verified locally within documented operator bounds; not deployed |
| PC-05 | Fresh-Workspace business package | Applicable customers/configuration/loans/media restored in dependency order; empty compatible destination; clear exclusions and reconciliation before operations | Verified locally within documented operator/profile bounds; not deployed |
| PC-06 | Remaining graph coverage and continuation | Required funding/storage/correction support and reviewed zero initial retained-item allocation; export/restore/re-export equality and future servicing, monitoring, document and numbering acceptance | Verified locally within documented graph/operator bounds; not deployed |

PC-01/02 reuse existing history staging and the Loans opening, servicing and
closed-position restore commands. Wider files use one small Workspace-owned file
review batch because the original history batch binds one JSON document to one
origin. Package bytes use private application file storage rather than database
JSON/base64. Original source hash/path/inventory remain immutable; completed
receipts remain retained. Cancellation clears staged values and removes the
upload after database commit. Existing media inventory covers the new file field.

Every slice needs appropriate malformed-source, confirmation/replay, permissions,
restricted-role isolation and financial boundary checks. PC-02 does not expand a
published financial profile, permit SQL/native recovery uploads, increase source
parser limits, create historical cash transactions, or implement complete Workspace
transfer. Larger/newer source contracts belong to later slices.

See the [browser restore decision](../adr/2026-10-10-browser-loan-file-restoration.md).
The [implementation record](../implementation/browser-loan-file-restoration-pc02.md)
records 128 passing regression checks against the committed baseline plus this
slice, migration consistency and required rollout steps. PC-03's
[essential-position adapter record](../implementation/essential-position-registers-pc03.md)
tracks its additional templates, explicit boundaries and verification.
PC-04's [volume exchange record](../implementation/bounded-volume-exchange-pc04.md)
tracks operator snapshot/export, checksummed chunks, existing receipt-based
resumption and exact accepted borrower references. PC-05's
[fresh package record](../implementation/fresh-business-package-pc05.md) tracks
the atomic operator path, private review/receipt, empty unactivated destination,
explicit setup/media coverage and initial held graph limitations. PC-06's
[wider graph record](../implementation/portable-graphs-pc06.md) adds explicit funding,
storage/correction, retained zero-item and source-only licence/quote adapters.
Isolated continuation and regression acceptance covers 323 passing cases across
the broader run and corrected fresh-workspace fixture rerun. Source authority and quote
evidence are retained honestly; original version-1 coverage is unchanged.
Ordinary new item allocations remain positive. Reviewed zero remaining allocation
requires the exact accepted opening checkpoint rather than omitted jewellery or
invented cash. Broader real-Workspace release remains separate.
