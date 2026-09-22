---
status: proposed
owner: loans
updated: 2026-09-22
tags: [adr, loans, templates, printing, experiment]
related:
  - 2026-08-06-loans-versioned-configurable-documents.md
  - 2026-08-09-loans-logical-layout-and-print-profile-separation.md
  - ../plans/ticket-template-designer.md
---

# Simplify template authoring while preserving document issuance

The owner wants clients to create their own ticket designs. Production's template
and positioned-frame approach already serves JCL plain-paper and JSK preprinted
stationery. The successor has stronger versioning and issuance boundaries but
exposes setup complexity and lacks several production authoring capabilities.

## Proposed decision

Evaluate a single template/frame editor over the existing Loans layout blocks,
assets, print profiles, publication, assignments and issue services. Reuse the
production authoring concepts and reviewed design data, not its Girvi-coupled
models or renderer. Do not create another source of loan financial facts.

Present paper/copy choices with the design in one user journey. Retain separate
internal layout and print-profile contracts and immutable published versions;
client simplicity does not require mutable historical documents. Preserve RLS,
authorization, approved financial evidence and exact-byte artifact reprints.

The bounded extension needs optional backgrounds/data-only printing, value-only
fields, production-equivalent customer/media bindings and sufficiently precise
geometry. Review visible business requirements separately from internal audit
evidence. The [implementation contract](../implementation/ticket-template-frame-mapping.md)
now selects layout v4, stock-aware profile v2 and ticket payload v2. V4 optional
backgrounds, field labels, precision geometry and text spacing are implemented on
the feature branch, together with profile v2 stock mode and separate design/print
previews. Payload-v2 contact/photo evidence and the nullable immutable issue source
snapshot are implemented; static-stock coverage, unified authoring/activation and
actual artwork acceptance remain pending. Prior schema interpretation and exact
stored artifacts survive.

Party identity/contact/photo data is captured at first issue; approved economics
and collateral/photo evidence retain their existing snapshot authority. A nullable
immutable source snapshot extends the existing issue, not a second history model.
Reprints resolve the stored artifact before fetching mutable data/media. Keep one
official print PDF; stationery guides appear only in labelled design previews.

Unified activation uses the existing Workspace/Series profile scopes and validates
the intended pair atomically. License-only profile scope is not added. Internal
audit identities need not clutter v4 paper output; reviewed static stock/artwork
declarations must match authoritative values while dynamic business facts remain
required. Source quantity/license/value differences and physical calibration are
explicit acceptance gates, not silent compatibility assumptions.

## Status and compatibility

The owner subsequently accepted the per-copy signature-area choice and explicit
optional printed-interest requirement, implemented for v4 in
[this decision](2026-09-22-ticket-signature-area-choices.md). JCL's Original and
Duplicate now have a validated paired preview using their reviewed artwork;
physical printing, reverse sides and integrated client activation remain pending.

The owner accepted separating printed business information from internal audit
evidence on 2026-09-22. Implemented for v4: audit IDs/fingerprints and verification
text are optional on paper; complete source evidence remains required in the
payload/issue, accessible through the existing admin Evidence page. New starters
omit internal identifiers. Business identity, approved terms, collateral coverage
and signature space remain required on each front. Existing printed designs and
artifacts are not rewritten. Reviewed fixed-stock declarations remain a distinct
pending part of this experiment; arbitrary text/backgrounds cannot waive coverage.

The owner approved branch isolation and a design-first experiment, not a merged
replacement. Existing schema/background/binding and publication rules remain in
force for prior versions. The opt-in v4 foundation permits absent backgrounds;
it now enforces business coverage separately from internal verification. Compatibility checks
pass for legacy rendering and stored reprints; physical and owner acceptance
remain required before adoption.

The plan defines acceptance examples, exclusions and isolated runtime rules.
Keep `rls-mvp` available at checkpoint `8b0e1ba3`; use the feature worktree and a
separate database/media location for experimentation. Reverting Git alone is not
a database rollback. Physical printer and owner authoring acceptance are merge
gates, not assumptions from unit tests.

## Alternatives

- Port the old mutable models/renderer wholesale: loses the successor's issuance
  boundaries and couples printing back to retired domain models.
- Add the old engine alongside the current one: doubles maintenance and makes
  historical output and configuration harder to reason about.
- Keep current authoring unchanged: does not satisfy self-service customization
  or JSK's working data-only stationery workflow.

The feature status/plan records partial implementation and remaining acceptance.
