---
status: accepted
owner: project
updated: 2026-09-13
tags: [loans, portability, authorization]
---

# Contain generic Loans model imports

The owner authorized the first security slice following the
[Loans portability audit](../architecture/loans-portability-audit.md). The legacy
generic importer exposed Loans models through generated ModelResources, outside
the domain command and reviewed admission paths.

Exclude every model in the Loans app from the generic import form. Reject forged
Loans selections before source parsing and reject Loans at the import resource
factory as well. This includes setup, funding, financial and evidence models;
future Loans models inherit the restriction. Do not change the RLS registry or
the generic export inventory to achieve write containment.

Generic import requires matching explicit request/database Workspace context, an
ACTIVE Workspace, and current `data.view`, `data.import` and
`workspace.settings.manage` grants through WorkspaceAccess. The settings grant
preserves administrative intent without depending on role names. Existing platform
override policy still applies through WorkspaceAccess, but cannot bypass Workspace
context, lifecycle or the Loans-model prohibition. Existing exports and metadata
reads retain their prior authorization in this bounded slice; broader generic
tool and export policy review remains separate.

Supported Party staging, complete-history Loans import and opening import retain
their own authorization, validation and transaction boundaries. Non-Loans generic
imports retain their existing mechanics under the new entry authorization. This
is not an endorsement of unrestricted model import as the final portability design.

Validation exposed a pre-existing limitation in non-Loans generic creation:
django-import-export attempts to reset the model's shared sequence after inserting
rows, which the restricted role rejects. Tests retain that denial and prove the
insert transaction rolls back, while ordinary permitted updates still work.
Do not grant runtime sequence-reset privileges to make generic creation succeed.
Replacing that generic behavior with supported domain import services remains
separate work; the staged Party pipeline does not use this ModelResource path.

No schema, native lifecycle, financial calculation or constraint changes. No
financial migration/cutover is authorized. Historical evidence acceptance and
validation-category work remain subsequent separately reviewed slices.
