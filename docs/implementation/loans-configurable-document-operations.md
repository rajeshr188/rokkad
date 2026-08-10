---
status: active
owner: loans
updated: 2026-08-09
tags: [loans, documents, operations, printing]
related: [../plans/loans-configurable-documents-plan.md, ../adr/2026-08-06-loans-versioned-configurable-documents.md, ../adr/2026-08-09-loans-logical-layout-and-print-profile-separation.md]
---

# Loans Configurable Document Operations

## Logical Layout And Print Profile Boundary

The accepted target architecture separates regulated document design from
physical printing:

```text
payload -> published logical layout -> logical surfaces
        -> published print profile -> physical PDF -> immutable issue
```

Layouts own content, signatures, Original/Duplicate identity, Terms/D3 content,
copy scope, and backgrounds. Versioned workspace print profiles own A5/A4
packaging, included copies, simplex/duplex ordering, orientation, scaling, and
printer guidance. Every issue must record both immutable revision hashes and
retain exact artifact bytes.

LPD7.1 provides validated versioned profile persistence and deterministic
`Series -> Workspace -> built-in` resolution. LPD7.2 maps every embedded
loan-ticket sheet/copy composition to an equivalent compatibility profile and
records that profile's name, version, canonical hash, and `LEGACY_LAYOUT`
source on every new configurable ticket issue. Existing `copy_mode` and
`sheet` settings still drive rendering, so this evidence describes the output
actually produced rather than claiming an assigned profile was used. LPD7.3
now makes resolved profiles drive new configurable loan-ticket issues. The
renderer first produces logical copy surfaces, validates the selected pair,
then performs A5 sequencing or A4 side-by-side imposition. Existing issued
artifacts are returned before current defaults are resolved.

## Owner/Admin Workspace

Open **Loans setup > Print profiles** to manage physical packaging. Create a
draft, choose A5 sequential or A4 side-by-side composition and printer
guidance, preview it against a published loan-ticket layout and approved loan,
then publish and assign it at workspace or Series scope. Editing is restricted
to drafts; change a published profile by cloning it. Retirement disables its
active assignments but preserves issue evidence.

Assignment validates the actual effective logical layout for each affected
Series before changing state. For example, a duplex profile requiring Terms or
D3 cannot be assigned where that surface is absent. Workspace assignment
checks all Series except those already protected by a Series-specific profile.

Open **Loans setup > Issued documents** to inspect the immutable issue ledger.
Each detail records source, verification identity, layout revision/hash, print
profile revision/hash/scope, payload hash, and PDF hash. **Download exact
artifact** returns the stored bytes; it does not regenerate from current
defaults.

Owner/Admin compatibility recovery is explicit:

```text
<loan-ticket-pdf-url>?print_profile=legacy
```

This uses the published layout's embedded composition, records
`LEGACY_LAYOUT` evidence on a newly created issue, and emits a workspace audit
event. It never activates automatically after a profile failure. The separate
`?renderer=fixed` recovery remains available under its existing rules.

## Integrity Gate

Run inside each tenant schema before and after a document-layout rollout:

```powershell
python manage.py tenant_command check_loan_document_integrity --schema=<schema> --fail-on-findings
```

The command verifies canonical layout/profile hashes, layout/document scope,
profile revision and assignment scope, every Series' effective layout/profile
compatibility, profile evidence on new issues, asset
workspace and byte hashes, issued artifact hashes, revision scope, and
regeneration lineage. For the parity pilot it also rejects every active
loan-ticket assignment that would emit only Original or only Duplicate. A
configured ticket must use `A5_BOTH_SIMPLEX`, `A5_BOTH_DUPLEX`,
`A4_SIDE_BY_SIDE`, `A4_SIDE_BY_SIDE_DUPLEX`, or an Original/Duplicate copy
mode. No assignment is valid because the fixed fallback emits both copies.
Any finding blocks rollout. The same findings are visible to Owner/Admin under
Loans setup > Document layouts > Integrity diagnostics.

## Layout Pack Boundary

Exports contain only schema-v1 JSON plus validated asset bytes and hashes. They
contain no tenant IDs, users, assignments, issues, source data, Python, HTML,
or executable templates. Import rejects unsafe ZIP paths, excess files/size,
unknown manifest properties, invalid layout bindings, and asset hash drift.
Every import creates a new unassigned draft; it must be previewed, test-printed,
published, and assigned locally.

## Printer Pilot Matrix

Complete this with a real operator before production closeout:

| Check | A4 simplex | A4 duplex | A5 | Result |
| --- | --- | --- | --- | --- |
| Loan ticket original/duplicate | Pending | Pending | Pending | Pending |
| Long borrower/regional text | Pending | Pending | Pending | Pending |
| 25+ collateral rows | Pending | Pending | Pending | Pending |
| Logo and image background | Pending | Pending | Pending | Pending |
| PDF letterhead background | Pending | Pending | Pending | Pending |
| QR scans to exact verification ID | Pending | Pending | Pending | Pending |
| Margins/signature boxes are printable | Pending | Pending | Pending | Pending |
| Earlier official issue reprints byte-identically after default change | Pending | Pending | Pending | Pending |

Record printer make/model, driver, paper stock, duplex setting, operator, date,
and any scaling option used. Do not mark LPD6 operationally complete from an
on-screen PDF review alone.

For compatibility output, record the issue's print-profile name, version,
canonical hash, and `LEGACY_LAYOUT` scope. For resolved output, record the
`SERIES`, `WORKSPACE`, or `BUILT_IN` scope. Test the same logical layout through
every assigned profile and verify that changing the active profile does not
alter a historical issue reprint.

## Recovery

If a configured render fails, do not silently hide it. Owner/Admin may request
the existing PDF URL with `?renderer=fixed`; this action is audited. Diagnose
and repair by cloning the published revision, correcting the draft, previewing
and test-printing it, publishing it, then changing the assignment. Never mutate
the prior published revision or issued artifact.
