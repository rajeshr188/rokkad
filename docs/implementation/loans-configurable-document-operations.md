---
status: active
owner: loans
updated: 2026-08-06
tags: [loans, documents, operations, printing]
related: [../plans/loans-configurable-documents-plan.md, ../adr/2026-08-06-loans-versioned-configurable-documents.md]
---

# Loans Configurable Document Operations

## Integrity Gate

Run inside each tenant schema before and after a document-layout rollout:

```powershell
python manage.py tenant_command check_loan_document_integrity --schema=<schema> --fail-on-findings
```

The command verifies canonical layout hashes, layout/document scope, asset
workspace and byte hashes, issued artifact hashes, revision scope, and
regeneration lineage. Any finding blocks rollout. The same findings are visible
to Owner/Admin under Loans setup > Document layouts > Integrity diagnostics.

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

## Recovery

If a configured render fails, do not silently hide it. Owner/Admin may request
the existing PDF URL with `?renderer=fixed`; this action is audited. Diagnose
and repair by cloning the published revision, correcting the draft, previewing
and test-printing it, publishing it, then changing the assignment. Never mutate
the prior published revision or issued artifact.
