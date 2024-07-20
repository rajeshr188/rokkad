from django.urls import path

from . import views

urlpatterns = [
    # other urls...
    path("invite/", views.create_invite, name="invite_to_company"),
    path("invite/success/", views.invite_success, name="invite-success-url"),
    path(
        "invitations/accept-invite/<str:key>/",
        views.CustomAcceptInvite.as_view(),
        name="accept-invite",
    ),
    path("company/create/", views.company_create, name="orgs_company_create"),
    path("company/list/", views.company_list, name="orgs_company_list"),
    path("company/<int:company_id>/", views.company_detail, name="orgs_company_detail"),
    path(
        "company/update/<int:company_id>/",
        views.company_update,
        name="orgs_company_update",
    ),
    path(
        "company/delete/<int:company_id>/",
        views.company_delete,
        name="orgs_company_delete",
    ),
    path("membership/list/", views.membership_list, name="orgs_membership_list"),
    path("profile/", views.profile, name="profile"),
    path(
        "company/invitations/",
        views.companyinvitations_list,
        name="orgs_company_invitations_list",
    ),
    path(
        "company-preferences/",
        views.CompanyPreferenceBuilder.as_view(),
        name="company-preferences",
    ),
]
