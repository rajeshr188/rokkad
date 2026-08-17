from django.urls import path

from . import views

# Workspace manager routes are global authenticated surfaces. They manage the
# user's available workspaces and selected workspace, not tenant ERP data.
WORKSPACE_MANAGER_URLPATTERNS = [
    path("workspace/", views.workspace_selector, name="workspace_selector"),
    path(
        "workspace/<int:workspace_id>/dashboard/",
        views.workspace_dashboard,
        name="workspace_dashboard",
    ),
    path(
        "workspace/<int:workspace_id>/select/",
        views.workspace_select,
        name="workspace_select",
    ),
    path("workspace/create/", views.workspace_create, name="workspace_create"),
    path("workspace/list/", views.workspace_list, name="workspace_list"),
    path(
        "workspace/archived/",
        views.archived_workspaces,
        name="archived_workspaces",
    ),
    path(
        "workspace/<int:workspace_id>/", views.workspace_detail, name="workspace_detail"
    ),
    path(
        "workspace/<int:workspace_id>/setup/",
        views.workspace_setup,
        name="workspace_setup",
    ),
    path(
        "workspace/<int:workspace_id>/setup/state/",
        views.workspace_setup_state,
        name="workspace_setup_state",
    ),
    path(
        "workspace/<int:workspace_id>/edit/",
        views.workspace_update,
        name="workspace_update",
    ),
    path(
        "workspace/<int:workspace_id>/delete/",
        views.workspace_delete,
        name="workspace_delete",
    ),
    path(
        "workspace/<int:workspace_id>/restore/",
        views.workspace_restore,
        name="workspace_restore",
    ),
    path(
        "workspace/<int:workspace_id>/lifecycle/<str:target_state>/",
        views.workspace_lifecycle_transition,
        name="workspace_lifecycle_transition",
    ),
    path(
        "workspace/<int:workspace_id>/preferences/",
        views.CompanyPreferenceBuilder.as_view(),
        name="workspace_preferences",
    ),
]

# Incoming invitations belong to the authenticated user account. They are kept
# separate from workspace invitation administration even though compatibility
# paths currently live under /orgs/team/.
ACCOUNT_INVITATION_URLPATTERNS = [
    path("team/invitations/", views.team_invitations, name="team_invitations"),
    path(
        "team/invitations/accept/<str:key>/",
        views.team_accept_invitation,
        name="team_accept_invitation",
    ),
]

# Workspace invitation administration belongs to workspace settings. Current
# list/revoke/success paths remain unscoped for compatibility until canonical
# workspace-scoped aliases are introduced and tested.
WORKSPACE_INVITATION_URLPATTERNS = [
    path(
        "workspace/<int:workspace_id>/team/invite/",
        views.team_invite,
        name="team_invite",
    ),
    path(
        "team/invitations/<int:invitation_id>/delete/",
        views.invitation_delete,
        name="team_delete_invitation",
    ),
    path(
        "team/invitations/list/",
        views.companyinvitations_list,
        name="team_invitations_list",
    ),
    path("team/invite/success/", views.invite_success, name="team_invite_success"),
]

# Team membership routes are workspace settings/admin surfaces. The list route
# still uses selected-workspace fallback; mutating routes carry workspace_id.
TEAM_MEMBER_URLPATTERNS = [
    path(
        "workspace/<int:workspace_id>/team/member/<int:membership_id>/remove/",
        views.team_remove_member,
        name="team_remove_member",
    ),
    path(
        "workspace/<int:workspace_id>/team/member/<int:membership_id>/role/",
        views.team_change_role,
        name="team_change_role",
    ),
    path("team/members/", views.membership_list, name="team_members_list"),
    path(
        "workspace/<int:workspace_id>/leave/",
        views.workspace_leave,
        name="workspace_leave",
    ),
    path("memberships/", views.my_memberships, name="my_memberships"),
]

ACCOUNT_PROFILE_URLPATTERNS = [
    path("profile/", views.profile, name="profile"),
    path("account/settings/", views.account_settings, name="account_settings"),
]

urlpatterns = (
    WORKSPACE_MANAGER_URLPATTERNS
    + ACCOUNT_INVITATION_URLPATTERNS
    + WORKSPACE_INVITATION_URLPATTERNS
    + TEAM_MEMBER_URLPATTERNS
    + ACCOUNT_PROFILE_URLPATTERNS
)
