from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django_tenants.utils import (get_public_schema_name, remove_www,
                                  schema_context)
from dynamic_preferences.views import PreferenceFormView
from invitations.views import AcceptInvite
from render_block import render_block_to_string

from .decorators import company_member_required, role_required, roles_required
from .forms import (CompanyForm, CompanyInvitationForm, MembershipForm,
                    company_preference_form_builder)
from .models import Company, CompanyInvitation, Domain, Membership, Role

# Create your views here.

User = get_user_model()


def has_permission(user, tenant, permission_codename):
    try:
        # Get the user's role in the tenant
        membership = Membership.objects.get(user=user, tenant=tenant)
        role = membership.role
    except Membership.DoesNotExist:
        # The user does not have a role in the tenant
        return False

    # Check if the role has the permission
    return role.permissions.filter(codename=permission_codename).exists()


def has_role(user, tenant, role_name):
    try:
        # Get the user's role in the tenant
        membership = Membership.objects.get(user=user, tenant=tenant)
        role = membership.role
    except Membership.DoesNotExist:
        # The user does not have a role in the tenant
        return False

    # Check if the role has the permission
    return role.name == role_name


# def my_view(request, tenant_id):
#     tenant = get_object_or_404(Tenant, id=tenant_id)

#     if not has_permission(request.user, tenant, 'my_permission'):
#         return HttpResponseForbidden()

# Existing code...


@login_required
def company_create(request):
    if request.method == "POST":
        form = CompanyForm(request.POST)
        # TODO: set schema to public schema and then create the company
        if form.is_valid():
            with schema_context(get_public_schema_name()):
                company = form.save(commit=False)
                company.schema_name = company.name.lower().replace(" ", "_")
                company.creator = request.user
                company.owner = request.user
                company.save()
                domain = remove_www(request.get_host().split(":")[0]).lower()
                company_domain = f"{company.schema_name}.{domain}"
                Domain.objects.create(
                    tenant=company, domain=company_domain, is_primary=True
                )
                Membership.objects.create(
                    user=request.user, company=company, role=Role.objects.get(name="Owner")
                )
                request.user.set_workspace(company)
            return redirect("orgs_company_list")
    else:
        form = CompanyForm()
    return render(request, "company/company_form.html", {"form": form})


@login_required
def company_list(request):
    companies = request.user.owned_companies.exclude(name="public").annotate(
        num_members=Count("memberships")
    )
    form = CompanyForm()
    return render(
        request, "company/company_list.html", {"companies": companies, "form": form}
    )


@login_required
@company_member_required
def company_detail(request, company_id):
    company = Company.objects.get(id=company_id)
    return render(request, "company/company_detail.html", {"company": company})


@roles_required(["Owner", "Admin"])
def company_update(request, company_id):
    company = Company.objects.get(id=company_id)
    if request.method == "POST":
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            form.save()
            return redirect("orgs_company_list")
    else:
        form = CompanyForm(instance=company)
    return render(
        request, "company/company_form.html", {"form": form, "company": company}
    )


@roles_required(["Owner", "Admin"])
def company_delete(request, company_id):
    company = get_object_or_404(Company, id=company_id)

    if request.method == "GET":
        return render(
            request, "company/company_delete_confirm.html", {"company": company}
        )

    elif request.method == "POST":
        if request.user != company.owner:
            return redirect("error_page")  # Redirect to an error page

        # Switch to the public schema before deleting the company
        with schema_context(get_public_schema_name()):
            company.delete()

            # Reset the user's workspace to the public schema
            request.user.workspace = get_public_schema_name()
            request.user.save()
        return redirect("orgs_company_list")


@login_required
@company_member_required
def companyinvitations_list(request):
    invitations = CompanyInvitation.objects.filter(email=request.user.email)
    return render(
        request, "company/company_invitations_list.html", {"invitations": invitations}
    )


# @role_required('Owner')
def create_invite(request):
    if request.method == "POST":
        form = CompanyInvitationForm(
            request.POST, inviter=request.user, request=request
        )
        if form.is_valid():
            form.save()
            return redirect("invite-success-url")
    else:
        form = CompanyInvitationForm(inviter=request.user)
    return render(
        request,
        "company/invitation_form.html",
        {"form": form, "url": reverse("invite_to_company")},
    )


@login_required
def invite_success(request):
    return render(request, "company/invite_success.html")


class CustomAcceptInvite(AcceptInvite):
    def get(self, *args, **kwargs):
        invite = self.get_object()
        email = invite.email
        user = User.objects.filter(email=email).first()

        if user:
            # If the user is already registered, create a Membership instance
            print(f"role: {invite.role}")
            Membership.objects.create(
                user=user, company=invite.company, role=invite.role
            )

        return super().get(*args, **kwargs)


class CompanyPreferenceBuilder(PreferenceFormView):
    template_name = "company/company_preferences.html"
    section = "company"
    subsection = "general"
    title = "Company Preferences"
    success_url = reverse_lazy("company_preferences")

    def get_form_class(self):
        # return CompanyPreferenceForm(instance=self.request.user.workspace)
        return company_preference_form_builder(instance=self.request.user.workspace)

    def render_to_response(self, context, **response_kwargs):
        # Check if the request is made via HTMX
        if self.request.headers.get("HX-Request", False):
            # Render only the specific block content for HTMX requests
            content = render_block_to_string(
                "company/company_preferences.html", "content", context, self.request
            )
            return HttpResponse(content)
        else:
            # Proceed with the normal flow for non-HTMX requests
            return super().render_to_response(context, **response_kwargs)


@login_required
@role_required("Owner")
def membership_revoke(request, membership_id):
    # company = get_object_or_404(Company, id=company_id)
    membership = get_object_or_404(Membership, user=user_id, company=company)

    membership.delete()
    return redirect("orgs_company_list")  # Redirect to the list of companies


@login_required
@roles_required(["Owner", "Admin"])
def membership_update(request, company_id, membership_id):
    company = get_object_or_404(Company, id=company_id)
    membership = get_object_or_404(Membership, id=membership_id, company=company)

    if request.method == "POST":
        form = MembershipForm(request.POST, instance=membership)
        if form.is_valid():
            form.save()
            return redirect("orgs_company_detail", company_id=company_id)
    else:
        form = MembershipForm(instance=membership)
    return render(request, "company/edit_membership.html", {"form": form})


@login_required
def membership_list(request):
    memberships = request.user.memberships.all()
    return render(request, "company/membership_list.html", {"memberships": memberships})


@login_required
def profile(request):
    return render(request, "company/profile.html")


@login_required
def invitation_delete(request, invitation_id):
    invitation = get_object_or_404(CompanyInvitation, id=invitation_id)

    # Check if the user has the permission to delete the invitation
    if request.user != invitation.inviter:
        return redirect("error_page")  # Redirect to an error page

    invitation.delete()

    # return redirect(
    #     "orgs_companyinvitations_list"
    # )  # Redirect to the list of invitations
    return HttpResponse("Invitation deleted successfully")
