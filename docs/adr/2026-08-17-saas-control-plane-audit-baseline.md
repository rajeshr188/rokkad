---
status: accepted
owner: project
updated: 2026-08-17
tags: [adr, saas, control-plane, security, roadmap]
related:
  - ../architecture/saas-control-plane-architecture-audit.md
  - 2026-08-14-shared-schema-workspace-rls-tenancy.md
  - ../STATUS.md
---

# Accept The SaaS Control-Plane Audit As The Execution Baseline

## Status

Accepted.

## Context

The post-RLS control-plane audit reconstructs the current implementation,
identifies security and architecture gaps, and proposes an incremental roadmap.
Repeated broad redesign would delay closing known risks.

## Decision

The audit is the accepted control-plane baseline and roadmap.

Preserve the PostgreSQL RLS foundation. Execute the roadmap in small,
independently tested phases. Begin with Phase 0 security fixes. Do not combine
later Workspace resolution, ownership/RBAC, lifecycle, billing, onboarding,
URL, UI, or cleanup phases into Phase 0.

The exact Phase 0.5 contracts for Workspace authority, ownership,
authorization, and entitlements require their own decision lock before those
refactors begin.

Do not repeat the broad audit unless implementation uncovers material evidence
that contradicts it.

## Consequences

- The audit findings and phase order guide implementation.
- Every phase must remain reviewable, tested, and commit-worthy.
- Later-phase discoveries are recorded and deferred unless they block safety.
- The audit does not authorize a wholesale control-plane rewrite.
- Phase 0 stops after the identified endpoint security gaps are closed.
