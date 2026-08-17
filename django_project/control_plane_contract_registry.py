"""Exact executable evidence for accepted control-plane invariants."""

T = "apps.orgs.tests."
P2 = "apps.orgs.test_phase2_ownership_access."
P5 = "apps.orgs.test_phase5_invitations."
LIFE = "apps.orgs.test_workspace_lifecycle."
BILL = "apps.subscriptions.test_phase4_billing."
RLS = "apps.tenant_apps.loans.tests.test_rls."

CONTRACT_TEST_LABELS = {
    "CP-WORKSPACE-001": (T + "MiddlewareProcessRequestTests.test_unauthenticated_without_workspace_gets_public_context",),
    "CP-WORKSPACE-002": (T + "SecureWorkspaceMiddlewareTests.test_select_workspace_candidate_uses_path_but_never_profile",),
    "CP-WORKSPACE-003": (T + "DomainPathMismatchTests.test_domain_path_workspace_mismatch_is_forbidden",),
    "CP-WORKSPACE-004": (T + "WorkspaceAccessPolicyTests.test_workspace_access_denies_non_member",),
    "CP-WORKSPACE-005": (
        T + "SecureWorkspaceMiddlewareTests.test_select_workspace_candidate_uses_path_but_never_profile",
        T + "WorkspaceAccessPolicyTests.test_workspace_select_get_cannot_mutate_profile_preference",
    ),
    "CP-RLS-001": ("apps.tenancy.tests.WorkspaceContextDatabaseTests.test_sets_transaction_local_database_and_python_context",),
    "CP-RLS-002": ("apps.tenancy.tests.WorkspaceContextDatabaseTests.test_sets_transaction_local_database_and_python_context",),
    "CP-RLS-003": ("apps.tenancy.tests.WorkspaceContextDatabaseTests.test_rejects_conflicting_nested_context",),
    "CP-MEMBERSHIP-001": (P2 + "Phase2OwnershipAccessTests.test_workspace_access_is_request_independent_and_fail_closed",),
    "CP-MEMBERSHIP-002": (
        P5 + "CanonicalInvitationAcceptanceTests.test_acceptance_creates_membership_and_terminal_invitation_state",
        P5 + "CanonicalInvitationAcceptanceTests.test_expired_invitation_is_rejected_without_membership",
    ),
    "CP-OWNERSHIP-001": (P2 + "Phase2OwnershipAccessTests.test_owner_user_deletion_is_protected",),
    "CP-OWNERSHIP-002": (P2 + "Phase2OwnershipAccessTests.test_transfer_updates_owner_and_both_mirrored_roles_atomically",),
    "CP-OWNERSHIP-003": (P2 + "Phase2OwnershipConcurrencyTests.test_competing_transfers_serialize_and_only_one_commits",),
    "CP-AUTH-001": (P2 + "Phase2OwnershipAccessTests.test_workspace_access_is_request_independent_and_fail_closed",),
    "CP-AUTH-002": (
        T + "WorkspaceAccessPolicyTests.test_workspace_access_allows_member_with_required_permission",
        T + "WorkspaceAccessPolicyTests.test_workspace_access_denies_missing_required_permission",
    ),
    "CP-AUTH-003": (
        T + "WorkspaceAccessPolicyTests.test_workspace_access_allows_platform_admin_without_membership",
        T + "DomainPathMismatchTests.test_platform_admin_cannot_bypass_domain_path_workspace_mismatch_guard",
    ),
    "CP-LIFECYCLE-001": (
        LIFE + "WorkspaceLifecycleServiceTests.test_owner_can_archive_and_reactivate_same_workspace",
        BILL + "Phase4BillingTests.test_expired_trial_is_derived_without_mutating_stored_status",
    ),
    "CP-LIFECYCLE-002": (LIFE + "WorkspaceLifecycleServiceTests.test_owner_can_archive_and_reactivate_same_workspace",),
    "CP-BILLING-001": (BILL + "BillingMiddlewareAcceptanceTests.test_business_app_is_blocked_when_workspace_has_no_subscription",),
    "CP-BILLING-002": (BILL + "Phase4BillingTests.test_webhook_replay_is_acknowledged_without_reprocessing",),
    "CP-ENTITLEMENT-001": (BILL + "Phase4BillingTests.test_entitlements_are_namespaced_typed_and_missing_fails_closed",),
    "CP-ENTITLEMENT-002": (
        BILL + "Phase4BillingTests.test_entitlements_are_namespaced_typed_and_missing_fails_closed",
        BILL + "BillingMiddlewareAcceptanceTests.test_billing_evaluation_error_fails_closed",
    ),
    "CP-ENTITLEMENT-003": ("django_project.test_phase1_subscription_boundary.Phase1SubscriptionBoundaryTests.test_business_restriction_runs_after_workspace_is_established",),
    "CP-DATAPLANE-001": (
        RLS + "LoansRLSIsolationTests.test_root_and_child_rows_are_hidden_without_context",
        RLS + "LoansRLSIsolationTests.test_bulk_child_insert_cannot_spoof_another_workspace",
    ),
    "CP-JOB-001": (
        "apps.orgs.test_workspace_seed_commands.WorkspaceSeedCommandContextTests.test_workspace_defaults_opens_its_explicit_context",
        "apps.orgs.test_workspace_seed_commands.WorkspaceSeedCommandContextTests.test_all_workspaces_passes_each_explicit_id_to_scoped_command",
        "apps.tenant_apps.loans.tests.test_reassess_pawn_loans_command.ReassessPawnLoansCommandTests.test_reports_successful_bounded_batch",
    ),
}

CONTRACT_COVERAGE_GAPS = {
    "CP-AUTH-003": "Platform override evidence does not assert an audit event.",
    "CP-LIFECYCLE-002": "Lifecycle evidence does not assert retained business-row ownership.",
    "CP-DATAPLANE-001": "Loans evidence is not an all-Workspace-model metadata gate.",
}
