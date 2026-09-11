---
status: active
owner: project
updated: 2026-09-09
tags: [implementation, dependencies, architecture]
---

# Dependency policy

This policy describes the supported product, not the retired accounting/ERP design.
The [constitution](../constitution.md) and [control-plane contracts](../architecture/control-plane-contracts.md)
are authoritative. Historical policy is preserved in the
[snapshot](../archive/context/2026-09-09/implementation/dependency-policy.md).

| Owner | Responsibility and boundary |
| --- | --- |
| Party | Borrower/counterparty identity, relationships and private profile/KYC media |
| Loans | Lending lifecycle, balances, collateral/custody and immutable transaction/document evidence |
| Rates | Workspace reference rates; Loans freezes values used in completed calculations |
| Notify v2 | Delivery of authorized notice intent and delivery evidence; never the source of loan state |
| orgs/accounts/onboarding | Workspace and personal identity, membership, ownership, local grants and setup orchestration |
| subscriptions | Commercial terms, effective billing, entitlements, verified payment/refund/review evidence |
| tenancy | Explicit Workspace context, ownership registry and forced PostgreSQL RLS |

Use existing services/commands for writes and selectors/facades for cross-app reads.
Compose workflows at their existing integration boundary. Keep business calculations
out of templates and lifecycle mutation out of views. Ordinary model relations and
queries are not an excuse to bypass the owning service's permission, lifecycle,
immutability or audit checks. Do not add generic abstraction layers without need.

Business apps must not import subscription models, provider adapters or billing
state to create their own access policy. Use the existing control-plane access and
entitlement integration. Membership, authorization, lifecycle, billing and RLS are
separate checks. Notification delivery failure must not undo loan completion.

DEA/accounting, Girvi, Contact, Product and legacy Notify are retired dependencies.
Do not reintroduce their imports, posting engines, schema-tenancy helpers or UI
promises. Historical migrations, deliberate compatibility redirects/410 responses
and Party `contact.*` permission aliases are not dead code merely because their
names are old. Review callers before removal.

## Enforcement and package changes

Current checks include [control-plane import/context tests](../../django_project/test_control_plane_contract_registry.py)
and [app conformance checks](../../django_project/test_phase9_app_conformance.py), plus
boundary-specific service/RLS tests. Run affected tests from the
[testing guide](testing-and-migrations.md). `python scripts/check_app_boundaries.py` replaces the retired DEA guard. It scans
Git-tracked Python source in application/infrastructure roots, including tests but
excluding historical migrations; deleted files and docs archives are not scanned.
It rejects retired modules (including the former DEA facade), resolves relative
imports, and checks literal dynamic imports. Business apps cannot import the listed
billing/provider internals. Computed module names are not statically proven safe.
New untracked files enter this check when tracked/available in CI; inspect them
before staging. `python -m unittest scripts.test_app_boundaries` tests the guard.
GitHub CI runs both checks; there is no virtualenv-wide recursive scan.

Before removing packages/templates, inspect imports, settings/app registration,
template tags/inheritance, dynamic names, commands and tests. See the [R13 reachability inventory](dependency-template-cleanup.md) for the
bounded removals and retained dependencies. Verify a clean install and `pip check`; neither alone is a
security audit. Redis is optional; see [cache configuration](cache-configuration.md).
No blanket dependency upgrades are part of documentation cleanup.
