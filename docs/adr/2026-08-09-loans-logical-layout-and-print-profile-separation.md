---
status: accepted
owner: loans
updated: 2026-08-09
tags: [adr, loans, documents, printing, profiles]
related:
  - 2026-08-06-loans-versioned-configurable-documents.md
  - ../plans/loans-configurable-documents-plan.md
  - ../flows/loans-document-layout-operator-guide.md
  - ../implementation/loans-configurable-document-operations.md
amends: [2026-08-06-loans-versioned-configurable-documents.md]
---

# ADR: Separate Logical Loan Layouts From Physical Print Profiles

Date: 2026-08-09
Status: Accepted

## Context

Loans currently stores logical document design and physical sheet composition
inside the same published layout revision. For loan tickets, the layout may
contain Original, Terms, Duplicate, and D3 surfaces while also selecting an A5
sequence or A4 landscape side-by-side preset. This preserves deterministic
output but makes layout creation unnecessarily dependent on printer and paper
configuration.

The existing document architecture already treats logical overlay rendering as
separate from physical imposition. Official issues retain exact PDF bytes and a
hash, so historical reprints do not need to resolve current defaults again.

## Decision

1. Published layouts own the logical business document:
   - registered fields, tables, wording, geometry, formatting, and signatures;
   - Original and Duplicate copy identity;
   - Original Terms and Duplicate D3 back-surface content;
   - Both/Original/Duplicate block scope;
   - logical-surface backgrounds and mandatory evidence validation.
2. Versioned workspace-owned print profiles own physical output packaging:
   - which logical copies are included in one print job;
   - A5 sequential or A4 landscape side-by-side imposition;
   - simplex or duplex page ordering;
   - paper size, output orientation, and scaling policy;
   - operator-facing printer/flip-edge guidance.
3. The rendering pipeline is `immutable DocumentPayload -> published logical
   layout -> validated logical surfaces -> resolved versioned print profile ->
   physical PDF artifact -> immutable LoanDocumentIssue`.
4. Print profiles resolve independently from layouts. The initial precedence is
   `Series -> Workspace -> built-in profile`. License-level or printer-station
   scope requires later evidence and is not part of the first implementation.
5. A print profile is immutable after publication. Corrections use a new
   version and assignment, following the same draft/publish discipline as
   layouts.
6. Every official issue snapshots the resolved profile identity, version, and
   canonical hash in addition to the layout/payload/asset/PDF evidence. The
   exact issued PDF bytes remain the legal reproduction mechanism.
7. Changing a workspace or Series print-profile assignment affects only future
   official issues. Reprints return the stored original bytes. Authorized
   regeneration creates a linked new issue and records the newly resolved
   profile.
8. Layout validation continues to prove that every logical Original or
   Duplicate front selected by an eligible profile contains all mandatory
   fields, tables, and verification evidence. A print profile cannot remove
   required legal content or manufacture a logical surface absent from the
   published layout.
9. Printer-driver behavior is not encoded as executable instructions in the
   PDF. Profiles may record tested guidance such as paper stock and flip edge,
   but physical acceptance remains required.
10. Existing schema-v1/v2 published layouts and official issues remain valid.
    Until the new profile models and renderer stage ship, current embedded
    `copy_mode` and `sheet` settings remain authoritative. Migration must create
    equivalent profiles and prove byte/page-order parity before removing those
    properties from new layout authoring.

## Target Model

Names are provisional until the schema slice:

- `LoanDocumentPrintProfile`: stable workspace-owned identity and lifecycle.
- `LoanDocumentPrintProfileRevision`: immutable versioned physical settings and
  canonical hash.
- `LoanDocumentPrintProfileAssignment`: workspace or Series selection.
- `LoanDocumentIssue`: additive profile revision/hash evidence.

The first built-in profiles should cover:

- A5 Original;
- A5 Duplicate;
- A5 Original and Duplicate simplex;
- A5 Original/Terms and Duplicate/D3 duplex;
- A4 landscape Original/Duplicate side-by-side;
- A4 landscape side-by-side duplex with Terms/D3 backs.

## Compatibility And Migration

1. Characterize every existing copy/sheet preset with page-count, page-size,
   surface-order, and extracted-text tests.
2. Add profile persistence and issue metadata without changing layout behavior.
3. Materialize an equivalent immutable profile for each distinct embedded
   legacy composition and assign it at the narrowest matching scope.
4. Render old and new pipelines against the same payload/layout/assets and
   require equivalent page size, order, copy labels, mandatory content, and
   backgrounds. Exact bytes are not required across renderer versions, but the
   newly issued artifact remains hash-pinned.
5. Change new layout authoring to edit logical surfaces only. Keep legacy
   published revisions readable and renderable indefinitely.
6. Remove embedded composition from a future layout schema version only after
   migration, compatibility rendering, integrity diagnostics, and physical
   printer acceptance pass.

## Consequences

- Layout authors no longer need to choose printer imposition while arranging
  regulated content.
- One logical design can serve several paper/printer configurations without
  cloning its legal content.
- Print-profile changes become auditable and reproducible rather than mutable
  workspace preferences.
- The issue path gains another resolved immutable dependency and must fail
  closed if profile scope or hash validation fails.
- The UI needs separate Owner/Admin areas for Document layouts and Print
  profiles, with previews showing both resolved revisions.

## Rejected Alternatives

- Bare mutable workspace preferences: rejected because they provide no version,
  hash, assignment history, or issue provenance.
- Moving Original/Duplicate semantics entirely into printer preferences:
  rejected because copy identity, back-page forms, signatures, and mandatory
  evidence are business-document requirements.
- Re-rendering historical issues from current profiles: rejected because later
  settings or renderer changes could alter legal output.
- Deleting embedded composition immediately: rejected because existing
  published layouts and official issues must remain interpretable.

## Implementation Gate

Do not change runtime rendering from this ADR alone. Implementation is complete
only when profile models/services/UI, compatibility migration, issue
provenance, integrity diagnostics, focused renderer tests, and the physical
printer matrix all pass.
