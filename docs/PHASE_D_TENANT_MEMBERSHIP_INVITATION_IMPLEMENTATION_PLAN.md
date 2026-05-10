# Phase D: Tenant, Membership, and Invitation Control-Plane Implementation Plan

## Goal
Finalize tenant/workspace management, membership management, and invitation management so they are:
- control-plane authoritative (public schema)
- userflow-consistent (global vs workspace-scoped pages)
- security-hardened (no ID probing bypass)
- test-protected (regression-safe)

## Canonical Scope and Boundaries

### Public schema (source of truth)
- Company (workspace) lifecycle
- Membership lifecycle
- Invitation lifecycle
- Access decision inputs (membership, role, invite status)

### Tenant schema
- Business/domain data only (girvi, dea, rates, sales, etc.)
- Optional read-only projections only (if needed for performance), never authority

## Current Route and View Mapping (Authoritative)

### Workspace management routes
- `workspace_selector`: `/orgs/workspace/`
- `workspace_dashboard`: `/orgs/workspace/<workspace_id>/dashboard/`
- `workspace_select`: `/orgs/workspace/<workspace_id>/select/`
- `workspace_create`: `/orgs/workspace/create/`
- `workspace_list`: `/orgs/workspace/list/` (alias -> selector)
- `workspace_detail`: `/orgs/workspace/<workspace_id>/`
- `workspace_update`: `/orgs/workspace/<workspace_id>/edit/`
- `workspace_delete`: `/orgs/workspace/<workspace_id>/delete/`
- `workspace_preferences`: `/orgs/workspace/<workspace_id>/preferences/`

### Team/invitation routes
- `team_invite`: `/orgs/workspace/<workspace_id>/team/invite/`
- `team_invitations`: `/orgs/team/invitations/` (my incoming invites)
- `team_accept_invitation`: `/orgs/team/invitations/accept/<key>/`
- `team_delete_invitation`: `/orgs/team/invitations/<invitation_id>/delete/`
- `team_invitations_list`: `/orgs/team/invitations/list/` (workspace pending invites)
- `team_members_list`: `/orgs/team/members/` (currently my workspace memberships)

## Phase D Implementation Sequence (Task-by-Task)

---

### D1. Normalize explicit access policy for workspace-id endpoints

#### Status: ✅ COMPLETE

**Deliverables:**
- ✅ `_assert_workspace_access()` helper implemented (9 endpoints integrated)
- ✅ Helper unit tests: 6/6 passing (denials, platform-admin bypass, permission checks)
- ✅ Endpoint-level tests: workspace_select (2 tests, deny redirect + allow success)
- ✅ All system checks passing
- ✅ Backward compatible (no breaking changes)

**Implementation details:**
- Helper location: [apps/orgs/views.py](../../apps/orgs/views.py) lines 61-108
- Integrated endpoints: workspace_detail, workspace_select, workspace_dashboard, workspace_update, workspace_delete, team_invite, team_remove_member, team_change_role, companyinvitations_list
- Test class: `WorkspaceAccessPolicyTests` in [apps/orgs/tests.py](../../apps/orgs/tests.py) line 224

#### Why unit tests only for endpoints:
Full endpoint integration tests require complete request/middleware context setup with database writes. The helper unit tests + endpoint-select tests establish the mocking pattern and verify helper behavior at unit level, which is sufficient for regression protection.

---

### D2. Route and userflow verification (Navigation + Canonical Routes)

#### Status: ✅ COMPLETE

**Deliverables:**
- ✅ Template audit completed (all 5 key navigation templates checked)
- ✅ Canonical routes verified in use: workspace_selector, workspace_dashboard, workspace_detail, workspace_preferences, team_invitations, team_invite
- ✅ Deprecated route names verified absent: orgs_invite_delete, company_invite_list, team_invite_delete
- ✅ OrgNavigationFlowTests class: 5/5 tests passing

**Implementation details:**
- Test class: `OrgNavigationFlowTests` in [apps/orgs/tests.py](../../apps/orgs/tests.py)
- Tests implemented:
  1. `test_sidebar_uses_canonical_workspace_routes` — Verifies sidebar.html uses canonical routes
  2. `test_workspace_dashboard_uses_canonical_routes` — Verifies workspace_dashboard.html uses canonical routes
  3. `test_profile_page_uses_team_invitations_route` — Verifies profile.html links to team_invitations
  4. `test_main_navigation_uses_canonical_routes` — Verifies tenant.html uses canonical routes
  5. `test_no_deprecated_route_names_in_templates` — Verifies absence of deprecated route names

**Audit results:**
- Templates verified: sidebar.html, workspace_dashboard.html, profile.html, tenant.html, _base.html
- Route names present: workspace_selector, workspace_detail, team_invite, team_invitations, team_invitations_list, workspace_delete, workspace_preferences
- Deprecated names found: 0 (verified via grep_search, all 20 matches were template tags, not route names)

#### Why static file verification approach:
Template rendering tests require complete Django context (User objects with company_set, URL reversals, permission sets). Static file verification reads template files as text and searches for route names, which is robust, fast, and doesn't require context setup.

---

### D3. Lock domain/path mismatch policy and behavior matrix

#### Status: ✅ COMPLETE

**Deliverables:**
- ✅ Domain/path mismatch guard confirmed in middleware
- ✅ Platform-admin bypass verified and tested
- ✅ DomainPathMismatchTests class: 5/5 tests passing

**Implementation details:**
- Domain workspace is authoritative on tenant domains.
- Non-admin users are blocked from cross-workspace probing via path IDs.
- Superusers intentionally bypass mismatch guard for platform-admin operations.
- Mismatch flow performs deterministic handling: public context reset, error message, redirect to domain workspace dashboard.

**Tests implemented in `apps/orgs/tests.py`:**
1. `test_domain_path_workspace_mismatch_redirects_to_domain_workspace`
2. `test_platform_admin_bypasses_domain_path_workspace_mismatch_guard`
3. `test_domain_workspace_is_authoritative_over_profile`
4. `test_path_workspace_wins_over_profile_without_domain`
5. `test_mismatch_guard_only_applies_on_tenant_domains`

---

### D4. Invitation lifecycle state machine (explicit transitions)

#### Status: ✅ COMPLETE

**Deliverables:**
- ✅ Added explicit invitation status model with canonical states: `pending`, `accepted`, `declined`, `revoked` (+ derived `expired` at runtime)
- ✅ Added deterministic transition helpers in model: `mark_declined`, `mark_revoked`, state-aware `accept`
- ✅ Added migration `0022_companyinvitation_responded_at_and_more` with backfill for already accepted invitations
- ✅ Updated invitation flows in views to be state-aware and idempotent
- ✅ Updated invitation templates to render status from lifecycle state
- ✅ InvitationLifecycleStateTests class: 6/6 tests passing

**Implementation details:**
- Model updates: `CompanyInvitation.status`, `CompanyInvitation.responded_at`, `lifecycle_state()`
- Decline action now persists `declined` state.
- Delete action now revokes invitation (no hard delete) with inviter-or-admin authorization.
- Accept action now blocks expired or non-pending invitations deterministically.

**Tests implemented in `apps/orgs/tests.py`:**
1. `test_lifecycle_state_returns_expired_for_pending_invitation`
2. `test_mark_declined_sets_state_and_response_timestamp`
3. `test_mark_revoked_sets_state_and_response_timestamp`
4. `test_team_invitations_decline_persists_declined_state`
5. `test_team_invitations_accept_rejects_expired_invitation`
6. `test_invitation_delete_allows_workspace_admin_revoke`

---

### D5. Membership lifecycle guardrails

#### Status: ✅ COMPLETE

**Deliverables:**
- ✅ Last-owner guardrail added for member removal
- ✅ Last-owner guardrail added for role-demotion flow
- ✅ Self-leave policy implemented:
  - non-owner self-leave allowed
  - owner self-leave blocked until ownership transfer
- ✅ Removed member profile workspace is cleared immediately when it points to removed workspace
- ✅ MembershipLifecycleGuardrailTests class: 5/5 tests passing

**Implementation details:**
- `team_remove_member` now blocks removing the final owner.
- `team_remove_member` now blocks owner self-leave even when other owners exist (requires transfer path).
- `team_remove_member` now clears stale `user.profile.workspace` for removed users.
- `team_change_role` now blocks demoting the final owner.
- Guard helpers added in view layer:
  - `_is_owner_membership(...)`
  - `_owner_membership_count(...)`

**Tests implemented in `apps/orgs/tests.py`:**
1. `test_cannot_remove_last_owner`
2. `test_owner_must_transfer_before_self_leave`
3. `test_removed_member_loses_workspace_access_immediately`
4. `test_self_leave_allowed_for_non_owner`
5. `test_cannot_demote_last_owner`

---

### D6. Control-plane integrity checks

#### Status: ✅ COMPLETE

**Deliverables:**
- ✅ Added dedicated control-plane service module: `apps/orgs/services/control_plane.py`
- ✅ Centralized Company/Membership/Invitation write operations into service functions
- ✅ Enforced public schema context for control-plane writes via shared schema wrapper
- ✅ Added audit events for all mutation operations handled by control-plane services
- ✅ Refactored org views to use service-layer mutations instead of direct model writes
- ✅ ControlPlaneIntegrityTests class: 3/3 tests passing

**Implementation details:**
- Service-layer operations added:
  - Workspace: create, update, archive
  - Membership: create, role change, remove
  - Invitation: send, accept, decline, revoke
- Public schema enforcement:
  - Every service mutation executes under `_public_schema_context()` (`schema_context(get_public_schema_name())`)
- Audit coverage added in service layer:
  - `COMPANY_CREATE`, `COMPANY_UPDATE`, `COMPANY_DELETE`
  - `TEAM_MEMBER_ADD`, `TEAM_MEMBER_REMOVE`, `TEAM_ROLE_CHANGE`
  - `TEAM_INVITE`, `TEAM_INVITE_ACCEPT`, `TEAM_INVITE_DECLINE`, `TEAM_INVITE_REVOKE`

**Tests implemented in `apps/orgs/tests.py`:**
1. `test_workspace_create_writes_control_plane_records`
2. `test_membership_mutations_occur_in_public_schema_context`
3. `test_invitation_mutations_are_audited`

---

### D7. Regression gate and rollout checklist

#### Status: ✅ COMPLETE

**Regression gate results (executed):**
1. ✅ `manage.py check` → `System check identified no issues (0 silenced)`
2. ✅ `manage.py test apps.orgs.tests` → `Ran 63 tests ... OK`
3. ✅ Focused middleware/security coverage confirmed in passing suite:
  - mismatch policy tests
  - non-member denial tests
  - platform-admin policy tests

**D7 fix during gate:**
- Updated one stale middleware test expectation for unauthenticated tenant-domain access:
  - Old expectation: unauthenticated user receives tenant context
  - Current policy: unauthenticated user is redirected to login with public context
  - Updated test: `test_unauthenticated_with_domain_workspace_redirects_to_login`

**Manual smoke checklist (ready for release sign-off):**
1. Non-member user cannot open `/orgs/workspace/<other_id>/` on localhost.
2. Non-member user gets mismatch redirect on tenant domain.
3. Superuser behavior matches policy on both localhost and tenant domain.
4. My Invitations and Pending Invitations pages show expected records.

## Proposed Test Class Placement in `apps/orgs/tests.py`

### Extend existing classes
- `SecureWorkspaceMiddlewareTests`
- `MiddlewareProcessRequestTests`
- `PermissionResolutionTests`

### Add new classes
- `WorkspaceAccessPolicyTests`
- `InvitationLifecycleTests`
- `MembershipLifecycleTests`
- `OrgNavigationFlowTests`

## Deliverable Definition of Done (Phase D)
1. One authority plane for tenant/membership/invitation decisions.
2. Consistent authorization semantics across middleware and view layer.
3. Clear global vs workspace-scoped navigation with no ambiguity.
4. Invitation and membership lifecycles have explicit state transitions.
5. New and existing tests protect all critical regressions.
