---
status: active
owner: project
updated: 2026-10-03
tags: [docs, navigation, architecture]
---

# Rokkad documentation

Rokkad is shared-schema pawn-lending SaaS built around Party, Loans, Rates and
Notify v2. Workspace-owned business data is isolated by PostgreSQL forced RLS.
Start with current guidance below. Retired accounting/ERP material is historical,
not an instruction to reintroduce it.

## Current work and decisions

- [Status](STATUS.md): checkpoint, validation and remaining acceptance.
- [Agent memory](AGENT_MEMORY.md): stable decisions and owner constraints.
- [Active delivery](plans/active.md) and [hardening plan](plans/project-hardening.md).
- [Unified loan recording](flows/unified-loan-recording.md): accepted real-time/paper-entry design and [tracked delivery](plans/unified-loan-recording.md); independent paper entry, servicing, supported corrections, native recovery and recorded-origin auction implemented locally; real-book/release acceptance pending.
- [Release Khata and paper-first recording together](flows/khata-and-paper-first-release.md): scoped commit, merged migration dependencies, separate staff acceptance and joint rollout/recovery.
- [Roadmap](ROADMAP.md) and [Future work](plans/future-work.md): shelved ideas and resume conditions.
- [Khata requirements](plans/khata-agreements.md): confirmed rules and remaining scenario/release gates.
- [Khata foundation](implementation/khata-foundation.md): local backend implementation, tests and remaining servicing work.
- [Khata opening](implementation/khata-opening.md): local custody, approval, photos, valuation and staged-withdrawal backend.
- [Khata interest collection](implementation/khata-interest-collection.md): frozen monthly charges, annual/monthly dues and oldest-due receipts.
- [Khata agreement changes](implementation/khata-agreement-changes.md): approved limit/rate activation, exact interest splits and financial reductions.
- [Khata custody and settlement](implementation/khata-custody-settlement.md): grouped exchanges, hard-LTV reduction returns, closing interest and pending physical handovers.
- [Khata corrections](implementation/khata-corrections.md): bounded receipt compensation, unhanded exchange cancellation and dependency/authorization safeguards.
- [Khata integration](implementation/khata-integration.md): borrower/dashboard/portal summaries, read-only account screens and preserved private documents.
- [Khata operator and recovery](implementation/khata-operator-and-recovery.md): complete supported command forms, private photos and native recovery evidence.
- [Khata servicing and recovery flow](flows/khata-servicing-and-recovery.md): operator reviews and exact-identity offline restore.
- [Khata labels and pilot flow](flows/khata-labels-and-pilot-review.md): individual/combined physical labels, saved reprints and authenticated custody scans.
- [Khata release review](implementation/khata-release-review-20261002.md): local delivery evidence, supported scope and remaining named-pilot gates.
- [Khata test candidate](implementation/khata-test-candidate-20261002.md): frozen source preparation and disposable full database/media recovery rehearsal.
- [Khata image/local pilot](implementation/khata-image-pilot-20261002.md): verified Linux image, 372 regressions, persistent localhost review and remaining hosted/hardware gates.
- [Khata test-pilot acceptance](flows/khata-test-pilot-acceptance.md): owner-selected new test workspace, operator scenarios and 100 x 60 mm paper/QR checks.
- [Khata balances and documents](flows/khata-balances-and-documents.md): register filters, balance semantics, custody and exact reprints.
- [Khata technical design](architecture/khata-technical-design.md): proposed schema, numbering, workflows, permissions and verification cases.
- [Project architecture review](architecture/2026-09-09-project-review.md): original findings and follow-ups.
- [Constitution](constitution.md), [control-plane contracts](architecture/control-plane-contracts.md)
  and [ADRs](adr/): domain invariants and accepted architecture.
- [Dependency policy](implementation/dependency-policy.md): supported ownership/import boundaries.

## Business and operator flows

- [Khata account workflow](flows/khata-account-workflow.md): complete staff journey, worked examples, collateral identification and developer source contracts.
- [Paper-first operator guide](flows/paper-first-operator-and-release.md): independent numbered loans, actual dated receipts/renewal/closure, book review and recovery.
- [Khata collateral usability](implementation/khata-collateral-usability.md): combined receiving/photos, paginated private browsing and searchable exchange groups.
- [The complete loan journey](flows/loan-journey.md): developer reference, shared PNG and in-app staff handbook.
- [Set up your business](flows/business-setup.md) and [first-loan setup](flows/first-loan-setup.md).
- [Understand dashboard customer, portfolio and lending-activity metrics](flows/business-dashboard.md).
- [Enter, correct and withdraw metal prices](flows/metal-rate-entry.md).
- [Reassess collateral and review freshness](flows/collateral-reassessment.md).
- [Review loan health, amend monitoring limits and enable refresh](flows/loan-health-monitoring.md).
- [Choose simple or extended loan workflow](flows/loan-workflow-choice.md).
- [Browse collateral and releases](flows/collateral-and-release-browsing.md).
- [Release multiple loans](flows/multiple-loan-release.md).
- [Document layouts, exact overlays and print profiles](flows/loans-document-layout-operator-guide.md).
- [Pawn-loan financial read models](domain/pawn-loan-financial-read-models.md)
  and [regulatory/economic setup](domain/loans-regulatory-setup-and-policy.md).
- [Party](domain/party.md), [Notifications](domain/notifications.md),
  and [subscription checkout/recovery/reviews](flows/subscription-checkout.md).

## Development and operations

- [Containers, CI and runtime startup](implementation/container-and-ci.md).
- [Testing and migrations](implementation/testing-and-migrations.md).
- [Workspace operator commands](implementation/loans-operator-commands.md).
- [Action permissions](implementation/action-permission-review.md).
- [Private media](implementation/private-media-access.md).
- [Cache configuration and optional Redis](implementation/cache-configuration.md).
- [Document integrity and physical acceptance](implementation/loans-configurable-document-operations.md).

## History and interpretation

[Context snapshots](archive/context/README.md) preserve the previous long status,
memory, roadmap and obsolete current guides. [Archive](archive/README.md) contains
older app plans, migration investigations and retired Girvi/DEA/Contact material.
[Completed work](plans/completed.md) and [legacy backlog](plans/backlog.md) are
historical reference, not automatic current priorities. Old docs may still refer to
files or apps that no longer exist. Prefer the current contracts and active plan.

Keep this index curated. Run `python scripts/check_current_docs.py` after changing
current entry links; the CI check intentionally does not validate every archived
historical claim or external URL.
