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
copy scope, and backgrounds. Versioned workspace print profiles will own A5/A4
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
will make resolved profiles drive future physical packaging after parity.

## Integrity Gate

Run inside each tenant schema before and after a document-layout rollout:

```powershell
python manage.py tenant_command check_loan_document_integrity --schema=<schema> --fail-on-findings
```

The command verifies canonical layout/profile hashes, layout/document scope,
profile revision and assignment scope, profile evidence on new issues, asset
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

For LPD7.2 compatibility output, record the issue's print-profile name,
version, canonical hash, and `LEGACY_LAYOUT` scope. After LPD7.3, test the same
logical layout through every assigned
profile and verify that changing the active profile does not alter a historical
issue reprint.

## Recovery

If a configured render fails, do not silently hide it. Owner/Admin may request
the existing PDF URL with `?renderer=fixed`; this action is audited. Diagnose
and repair by cloning the published revision, correcting the draft, previewing
and test-printing it, publishing it, then changing the assignment. Never mutate
the prior published revision or issued artifact.
