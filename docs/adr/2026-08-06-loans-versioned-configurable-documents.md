---
status: accepted
owner: loans
updated: 2026-08-06
tags: [adr, loans, documents, pdf, templates]
related: [../plans/loans-configurable-documents-plan.md, ../apps/loans/architecture-and-girvi-parity.md, 2026-07-15-loans-rewrite-domain-and-cutover-architecture.md]
---

# ADR: Loans Versioned Configurable Documents

Date: 2026-08-06
Status: Accepted

## Context

Girvi supports business-customizable loan tickets through mutable templates,
positioned frame rows, uploaded PDF backgrounds, and a renderer coupled to
Girvi models. Loans has simpler fixed PDFs built from immutable approval and
event evidence. Loans needs Girvi's operator capabilities without introducing
a second source of financial facts or making historical reprints mutable.

## Decision

1. Every Loans renderer consumes a versioned, immutable `DocumentPayload` made
   only of scalar details, tabular rows, source identities, fingerprints, and a
   verification ID. Projection builders are the only document layer that may
   read loan aggregates and event evidence.
2. The current fixed renderer remains supported permanently and consumes the
   same payload contract as future configurable renderers.
3. Configurable layouts belong to Loans. Girvi's `LoanTemplate`,
   `TemplateFrame`, views, and model-aware renderer will not be imported.
4. Layout bindings use an application-owned allow-list and constrained,
   versioned layout schema. Arbitrary Python, Django/Jinja expressions, model
   paths, HTML, and JavaScript are prohibited.
5. Draft layout revisions may change. Published revisions are immutable and
   changes require clone-and-publish. Resolution precedence is series, license,
   workspace, then the fixed system layout.
6. Official first print creates immutable issue evidence tying the source
   fingerprint, payload schema/hash, renderer/layout version, PDF hash, actor,
   and issue time together. Later default changes cannot alter that official
   issue.
7. Artifact retention is required for official issued documents. The exact PDF
   bytes are stored in tenant-isolated storage and verified by hash when read.
   Payload/revision data remains sufficient for diagnostics, but deterministic
   rebuilding is not the legal reproduction mechanism.
8. Preview and test prints are watermarked and never create official issue
   evidence. Regeneration under a newer layout creates a linked new issue; it
   does not replace the earlier one.
9. Layout, revision, assignment, and issue models will be tenant-owned with
   explicit workspace validation. Their future migrations use
   `migrate_schemas`.

## Consequences

- Fixed and configurable output cannot drift in their underlying business
  facts.
- Published layouts and official issued bytes provide reproducible historical
  documents even after defaults change.
- Storage growth is accepted for stronger regulatory evidence and will require
  retention, integrity, and orphan diagnostics.
- The first implementation can extract projections without schema or visible
  behavior changes.
- Each document kind must define its own required field registry; generic
  customization cannot remove mandatory source or verification information.

## Rejected Alternatives

- Copy Girvi's frame models and renderer: rejected because it couples layout to
  mutable models and repeats its complexity.
- Arbitrary HTML/Jinja templates: rejected because the execution and data
  access surface is too broad for tenant-authored regulatory documents.
- Store only the current default: rejected because historical reprints would
  change.
- Rebuild official bytes on every request: rejected because library/font or
  renderer changes can alter output even when source facts are unchanged.

## Review Triggers

Review before enabling cross-workspace layout sharing, executable template
languages, external signing, artifact deletion/retention policies, or automatic
Girvi template migration.
