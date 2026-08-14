---
status: complete
owner: project
updated: 2026-08-14
tags: [saas, phase-0, characterization, inventory, django-tenants]
related: [../architecture/SAAS_TARGET_ARCHITECTURE.md, saas-foundation-architecture-audit.md, ../STATUS.md]
---

# SaaS Foundation Phase 0 Baseline

## Scope

Phase 0A/0B adds characterization and read-only inventory only. It does not change runtime authorization, tenant resolution, models, migrations, schemas, or data.

Artifacts:

- `apps/orgs/test_saas_foundation_phase0.py`
- `apps/orgs/management/commands/check_saas_foundation.py`

Run the inventory with:

```powershell
python manage.py check_saas_foundation --json
python manage.py check_saas_foundation --fail-on-findings
```

The command explicitly enters the public schema and performs no writes.

## Characterized current behavior

The Phase 0 tests intentionally capture these current conditions before Phase 1 changes them:

- `ALLOW_COMPANY_HARD_DELETE` is true and Company admin exposes a hard-delete bulk action.
- allauth email verification is optional.
- `SecureWorkspaceMiddleware` selects `UserProfile.workspace` when neither domain nor path resolves a tenant.
- membership validation occurs before `connection.set_tenant()`.
- domain/path mismatch handling occurs before the tenant switch.
- subscription access is evaluated in both workspace middleware and subscription middleware.

These are baseline assertions, not endorsements. The accepted email decision is narrower than the original audit: general signup remains optional-verification, while invitation acceptance requires proof of the matching invited email. Later tenant-resolution and subscription phases address the remaining boundary risks.

## Public-schema inventory result

Inventory executed on 2026-08-14:

| Check | Result |
|---|---:|
| Non-public Companies | 6 |
| Archived Companies | 0 |
| Owner missing Membership | 0 |
| Owner without Owner Role | 0 |
| Memberships | 8 |
| Memberships with null Role | 0 |
| `CompanyOwnership` rows | 0 |
| Multiple active ownership groups | 0 |
| Active ownership disagreement | 0 |
| `CompanyInvitation` rows | 0 |
| `PendingInvitation` rows | 0 |
| Orphan pending bridge rows | 0 |
| Case-variant pending invitation groups | 0 |
| Guardian user object permissions | 0 |
| Guardian group object permissions | 0 |
| Integrity finding count | 0 |

The current data does not block eventual removal of `CompanyOwnership`, `PendingInvitation`, or Guardian. Code references and invite-before-signup behavior must still be migrated before deletion.

## RBAC finding

All four current Role rows have zero database permissions:

| Role | Permission rows |
|---|---:|
| Owner | 0 |
| Admin | 0 |
| Member | 0 |
| Customer | 0 |

Therefore `RolePermissions` hard-coded sets remain the effective RBAC authority. They must not be deleted until a permission matrix is accepted, Django Permission rows are seeded, and parity tests pass. The live role catalog also contains `Customer`, while the target architecture expected Viewer and optionally Accountant. Phase 3 must reconcile actual role requirements rather than blindly renaming or seeding roles.

## Source-reference inventory

Broad Python occurrence counts, including tests but excluding migrations, confirm that the competing paths are still active concepts:

| Concept | Occurrences |
|---|---:|
| `CompanyOwnership` | 7 |
| Guardian | 17 |
| `RolePermissions` | 6 |
| `PendingInvitation` | 15 |
| profile workspace fallback | 56 |
| `SubscriptionAccessService` | 14 |

These counts are navigation aids, not proof that every occurrence is runtime use. Each deletion phase still requires call-site classification.

## Test results

Focused Phase 0 gate:

```text
8 tests passed
```

Broader SaaS regression gate:

```text
53 tests run; 49 passed; 4 failed
```

The failures pre-date and are outside the new Phase 0 files:

1. `accounting` is present in `TENANT_ERP_URLPATTERNS` but absent from `SecureWorkspaceMiddleware.WORKSPACE_REQUIRED_URLS`. Two authorization intent tests expose this boundary mismatch. Treat this as a Phase 1 tenant-isolation fix requiring a real middleware access test, not merely an expected-set edit.
2. The direct-invitation signal intent test expects `Membership.objects.get_or_create`, while current code delegates to `control_plane.create_membership()`. The runtime direction is better; update the stale intent assertion only after verifying the service behavior test covers capacity and idempotency.
3. The org URL-order intent test omits the current archived-workspaces and workspace-restore routes. Update the expected compatibility list after confirming those routes are accepted public control-plane behavior.

The existing test database also reports unmigrated DEA model changes. They belong to the pre-existing working tree and are not addressed by this SaaS Phase 0 slice.

## Phase 0 conclusion

There are no current public-row reconciliation blockers. Hard-delete safety was explicitly skipped because current operations require bulk-admin exposure. The next accepted slice is matching verified-email enforcement at invitation acceptance, followed by authoritative tenant resolution. The `/accounting/` middleware gap should be included in the tenant-resolution safety phase because it is a concrete current boundary mismatch.
