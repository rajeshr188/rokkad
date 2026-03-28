from django.urls import path

from . import views

urlpatterns = [
    # =========================================================================
    # WORKSPACE MANAGEMENT
    # =========================================================================
    # Workspace selection and dashboard
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
    # Workspace CRUD
    path("workspace/create/", views.workspace_create, name="workspace_create"),
    path("workspace/list/", views.workspace_list, name="workspace_list"),
    path(
        "workspace/<int:workspace_id>/", views.workspace_detail, name="workspace_detail"
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
    # Workspace settings and preferences
    path(
        "workspace/<int:workspace_id>/preferences/",
        views.CompanyPreferenceBuilder.as_view(),
        name="workspace_preferences",
    ),
    # =========================================================================
    # TEAM MANAGEMENT
    # =========================================================================
    # Team invitations
    path(
        "workspace/<int:workspace_id>/team/invite/",
        views.team_invite,
        name="team_invite",
    ),
    path("team/invitations/", views.team_invitations, name="team_invitations"),
    path(
        "team/invitations/accept/<str:key>/",
        views.AcceptInvite.as_view(),
        name="team_accept_invitation",
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
    # Team member management
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
    # =========================================================================
    # LEGACY URLs (Kept for backward compatibility)
    # =========================================================================
    # Old company URLs - redirect to new workspace URLs
    path(
        "company/create/", views.workspace_create, name="orgs_company_create"
    ),  # DEPRECATED
    path("company/list/", views.workspace_list, name="orgs_company_list"),  # DEPRECATED
    path(
        "company/<int:company_id>/", views.workspace_detail, name="orgs_company_detail"
    ),  # DEPRECATED
    path(
        "company/update/<int:company_id>/",
        views.workspace_update,
        name="orgs_company_update",
    ),  # DEPRECATED
    path(
        "company/delete/<int:company_id>/",
        views.workspace_delete,
        name="orgs_company_delete",
    ),  # DEPRECATED
    # Old invitation URLs
    path(
        "company/<int:company_id>/invite", views.team_invite, name="invite_to_company"
    ),  # DEPRECATED
    path(
        "invite/success/", views.invite_success, name="invite-success-url"
    ),  # DEPRECATED
    path(
        "invitations/accept-invite/<str:key>/",
        views.AcceptInvite.as_view(),
        name="accept-invite",
    ),  # DEPRECATED
    path(
        "company/invitations/",
        views.companyinvitations_list,
        name="orgs_company_invitations_list",
    ),  # DEPRECATED
    path(
        "invitation/<int:invitation_id>/",
        views.invitation_delete,
        name="orgs_invite_delete",
    ),  # DEPRECATED
    # Old membership URLs
    # Old membership URLs
    path(
        "membership/list/", views.membership_list, name="orgs_membership_list"
    ),  # DEPRECATED
    path(
        "company/<int:company_id>/membership/<int:membership_id>/update",
        views.team_change_role,
        name="orgs_membership_update",
    ),  # DEPRECATED
    path(
        "company/<int:company_id>/membership/<int:membership_id>/revoke",
        views.team_remove_member,
        name="orgs_membership_revoke",
    ),  # DEPRECATED
    # Other
    path("profile/", views.profile, name="profile"),
    path(
        "company-preferences/",
        views.CompanyPreferenceBuilder.as_view(),
        name="company-preferences",
    ),  # DEPRECATED - use workspace_preferences
]
