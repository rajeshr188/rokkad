---
status: active
owner: loans
updated: 2026-08-10
tags: [loans, usability, pagination, filtering, urls, camera]
related:
  - loans-rewrite-roadmap.md
  - loans-configurable-documents-plan.md
  - ../adr/2026-07-15-loans-rewrite-domain-and-cutover-architecture.md
---

# Loans Usability And URL Consistency

## Outcome

Make the mature Loans domain comfortable for daily counter use without
weakening immutable evidence, tenant isolation, or temporary Girvi coexistence.

## UP1: Capture-First Collateral Photographs

Status: implemented 2026-08-10.

- Mobile photo inputs request the environment-facing camera while retaining the
  normal photograph chooser.
- Draft/edit, post-draft append, and release-and-renew additional collateral
  expose an in-page camera/webcam capture action.
- Browser capture produces a JPEG `File` and submits through the existing form;
  server-side JPEG/PNG content, size, tenant, lifecycle, hash, and immutability
  rules remain authoritative.
- Denied/unsupported camera access falls back to the normal file chooser.
- `getUserMedia` requires HTTPS or localhost and explicit browser permission.

## UP2: Bounded Tables And Contextual Filters

Status: in progress; UP2.1 and UP2.2 implemented 2026-08-10.

Use `django-filter`, already installed, plus Django `Paginator`. Preserve active
filter query parameters in page links and apply tenant scope before filters.

Priority order:

1. PawnLoan list: implemented. Text search covers loan number, borrower, party
   code, license number, and Series code; state, tenant-bound license/Series,
   and inclusive loan-date filters compose with it. Results are capped at 25
   rows and filter state survives pagination.
2. Issued documents: implemented. Source/issue/profile search, document kind,
   issue kind, profile source (including historical evidence without recorded
   LPD7 provenance), and inclusive issued-date filters compose across 50-row
   pages. The former silent newest-200 cutoff is removed.
3. Storage inventory and physical verification: hierarchy/state/session/date;
   50 rows.
4. Notices and operational diagnostics: kind/status/date; 50 rows.
5. License, profile, and layout administration only when realistic workspace
   volume justifies it.

Do not paginate small evidence tables embedded inside one loan detail. Those
are a single aggregate history and need a separate usability decision if they
become large.

## UP3: Canonical Workspace Loans URLs

Status: architecture slice pending; add an ADR before implementation.

Current route planes conflict:

- `/w/<workspace>/loans/` conditionally enters Loans or Girvi;
- several sibling workspace-slug detail/report aliases still call Girvi
  directly;
- new Loans operations live under `/loans/internal/`;
- Loans administration lives under `/loans/setup/`.

Target route policy:

- daily operations: `/w/<workspace>/loans/...`;
- administration: `/w/<workspace>/settings/loans/...`;
- stable scanned collateral/storage identifiers may retain dedicated tenant
  routes, but generated QR targets must use one documented canonical form;
- `/loans/internal/...` and `/loans/setup/...` remain temporary compatibility
  aliases, using safe redirects for GET and preserving POST semantics until
  every form/action is migrated;
- workspace-slug aliases must resolve Loans versus Girvi consistently from the
  same feature/cutover policy rather than mixing identifiers between domains.

The URL migration must inventory every reverse call, form action, PDF link, QR
target, test, and bookmarked GET route. Do not globally redirect POST actions
or assume a Girvi primary key identifies a PawnLoan.

## Acceptance

- A counter operator can photograph each item directly from mobile or webcam.
- Primary tables stay bounded and preserve filter state while paging.
- Every normal Loans navigation path remains within the canonical workspace
  route family.
- Compatibility routes have explicit removal criteria and no ambiguous
  Girvi/PawnLoan identifier dispatch.
