---
status: active
owner: project
updated: 2026-09-08
tags: [roadmap, planning]
related: [STATUS.md, plans/active.md, plans/backlog.md, plans/completed.md]
---

# Roadmap

## Current foundation

Party, Loans, Notify v2, and Rates are the supported business apps. Shared-schema
PostgreSQL forced RLS, Workspace permissions/lifecycle, billing/entitlements,
invitations, Loans Workspace routing, and immutable Workspace slugs are complete.
The Phase 11 checkpoint is `c8de539`, pushed on `rls-mvp`.

Girvi, Contact, legacy Notify, DEA/accounting, and the old inventory/sales/purchase
tracks are retired. Their historical plans are not current implementation work.

## Priority 1: MVP operator acceptance

- Complete and retain a real-transaction HTTP acceptance gate from Workspace
  creation through trial, lending setup, Party creation, loan disbursal,
  repayment, full release, and immutable PDF reprints under a restricted role.
- Fix reproducible journey blockers while preserving service-owned financial
  calculations, custody evidence, idempotency, and Workspace isolation.
- Complete browser/device and physical-printer checks with an operator. Automated
  HTTP tests establish server behavior, not visual or hardware acceptance.
- Follow the [acceptance checklist and findings](implementation/mvp-operator-acceptance.md).

## Priority 2: Remaining operator navigation and setup

- Party action URLs now preserve Workspace identity. Audit Rates/Notify deep
  links next.
- Improve setup guidance using actual lending prerequisites and clearly separate
  general checklist completion from loan readiness.
- Use observed operator friction to scope the deferred Loans UI redesign.

## Priority 3: Controlled operational pilots

- Exercise real email/WhatsApp delivery and callback evidence with configured
  providers and explicit operator authorization.
- Expand acceptance scenarios to later-date interest, reversals, renewals,
  auctions, and storage/verification journeys using existing domain services.
- Reconcile remaining historical documentation as each live area is reviewed.

See [active](plans/active.md), [backlog](plans/backlog.md), and [completed](plans/completed.md).

See [README](../README.md) for the project entry point.
