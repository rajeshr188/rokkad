"""
Onboarding Views - Step-by-step guided user onboarding
"""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django_tenants.utils import get_public_schema_name, remove_www, schema_context

from apps.orgs.audit import AuditLog
from apps.orgs.models import CompanyInvitation, Domain, Membership, Role

from .forms import (
    CompanySetupForm,
    ProfileSetupForm,
    TeamInviteForm,
    TourPreferencesForm,
)
from .models import OnboardingChoice, OnboardingProgress

logger = logging.getLogger(__name__)


def get_or_create_progress(user):
    """Get or create onboarding progress for user"""
    progress, created = OnboardingProgress.objects.get_or_create(user=user)
    return progress


@login_required
def onboarding_start(request):
    """
    Onboarding entry point - routes user to correct step
    """
    progress = get_or_create_progress(request.user)

    # If already complete, redirect to dashboard
    if progress.is_complete:
        return redirect("workspace_list")

    # Redirect to current step
    return redirect(progress.next_step_url)


@login_required
def onboarding_profile(request):
    """
    Step 1: Profile Setup
    """
    progress = get_or_create_progress(request.user)

    # Skip if already completed
    if progress.profile_completed:
        return redirect(progress.next_step_url)

    if request.method == "POST":
        form = ProfileSetupForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()

            # Mark step complete
            progress.mark_step_complete(1)

            # Log completion
            AuditLog.log(
                "ONBOARDING_PROFILE_COMPLETE",
                user=request.user,
                description="Completed profile setup",
                request=request,
                success=True,
            )

            messages.success(request, "Profile updated successfully!")
            return redirect(progress.next_step_url)
    else:
        form = ProfileSetupForm(instance=request.user)

    context = {
        "form": form,
        "progress": progress,
        "step_number": 1,
        "step_title": "Profile Setup",
        "step_description": "Tell us a bit about yourself",
    }
    return render(request, "onboarding/step_profile.html", context)


@login_required
def onboarding_company(request):
    """
    Step 2: Company Setup
    """
    progress = get_or_create_progress(request.user)

    # Ensure previous step is complete
    if not progress.profile_completed:
        return redirect("onboarding_profile")

    # Skip if already completed
    if progress.company_created:
        return redirect(progress.next_step_url)

    if request.method == "POST":
        form = CompanySetupForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                with schema_context(get_public_schema_name()):
                    # Create company
                    company = form.save(commit=False)
                    company.schema_name = company.name.lower().replace(" ", "_")
                    company.creator = request.user
                    company.owner = request.user
                    company.save()

                    # Create domain
                    domain = remove_www(request.get_host().split(":")[0]).lower()
                    company_domain = f"{company.schema_name}.{domain}"
                    Domain.objects.create(
                        tenant=company, domain=company_domain, is_primary=True
                    )

                    # Create Owner membership
                    Membership.objects.create(
                        user=request.user,
                        company=company,
                        role=Role.objects.get(name="Owner"),
                    )

                    # Set as active workspace
                    request.user.profile.set_workspace(company)

                    # Save onboarding choices
                    industry = form.cleaned_data.get("industry")
                    company_size = form.cleaned_data.get("company_size")

                    if industry:
                        OnboardingChoice.objects.create(
                            progress=progress,
                            step=2,
                            choice_key="industry",
                            choice_value=industry,
                        )

                    if company_size:
                        OnboardingChoice.objects.create(
                            progress=progress,
                            step=2,
                            choice_key="company_size",
                            choice_value=company_size,
                        )

                    # Mark step complete
                    progress.mark_step_complete(2)

                    # Log completion
                    AuditLog.log(
                        "ONBOARDING_COMPANY_COMPLETE",
                        user=request.user,
                        company=company,
                        description=f"Created workspace: {company.name}",
                        request=request,
                        success=True,
                        data={"industry": industry, "company_size": company_size},
                    )

                    messages.success(
                        request, f'Workspace "{company.name}" created successfully!'
                    )
                    return redirect(progress.next_step_url)
    else:
        form = CompanySetupForm()

    context = {
        "form": form,
        "progress": progress,
        "step_number": 2,
        "step_title": "Create Your Workspace",
        "step_description": "Set up your company workspace",
    }
    return render(request, "onboarding/step_company.html", context)


@login_required
def onboarding_team(request):
    """
    Step 3: Team Setup (Optional)
    """
    progress = get_or_create_progress(request.user)

    # Ensure previous steps are complete
    if not progress.company_created:
        return redirect(progress.next_step_url)

    # Skip if already completed
    if progress.team_setup_completed or progress.skipped_team:
        return redirect(progress.next_step_url)

    company = request.user.profile.workspace

    if request.method == "POST":
        if "skip" in request.POST:
            # Skip this step
            progress.skip_step(3)
            messages.info(request, "You can invite team members later from settings.")
            return redirect(progress.next_step_url)

        form = TeamInviteForm(request.POST)
        if form.is_valid():
            email_addresses = form.cleaned_data["email_addresses"]

            if email_addresses:
                # Send invitations
                invited_count = 0
                for email in email_addresses:
                    try:
                        # Create invitation
                        invitation = CompanyInvitation.objects.create(
                            email=email,
                            company=company,
                            inviter=request.user,
                            role=Role.objects.get(name="Member"),
                        )
                        invitation.send_invitation(request)
                        invited_count += 1
                    except Exception as e:
                        logger.error(f"Failed to invite {email}: {e}")

                messages.success(
                    request, f"Invitations sent to {invited_count} team members!"
                )

                # Log invitations
                AuditLog.log(
                    "ONBOARDING_TEAM_INVITE",
                    user=request.user,
                    company=company,
                    description=f"Invited {invited_count} team members",
                    request=request,
                    success=True,
                    data={"emails": email_addresses, "count": invited_count},
                )

            # Mark step complete
            progress.mark_step_complete(3)
            return redirect(progress.next_step_url)
    else:
        form = TeamInviteForm()

    context = {
        "form": form,
        "progress": progress,
        "step_number": 3,
        "step_title": "Invite Your Team",
        "step_description": "Collaborate with your team (Optional)",
        "company": company,
    }
    return render(request, "onboarding/step_team.html", context)


@login_required
def onboarding_tour(request):
    """
    Step 4: Feature Tour (Optional)
    """
    progress = get_or_create_progress(request.user)

    # Ensure previous steps are complete
    if not progress.company_created:
        return redirect(progress.next_step_url)

    # Skip if already completed
    if progress.tour_completed or progress.skipped_tour:
        return redirect("onboarding_complete")

    if request.method == "POST":
        if "skip" in request.POST:
            # Skip tour
            progress.skip_step(4)
            messages.info(request, "You can access help anytime from the menu.")
            return redirect("onboarding_complete")

        form = TourPreferencesForm(request.POST)
        if form.is_valid():
            # Save preferences
            primary_role = form.cleaned_data.get("primary_role")
            interested_features = form.cleaned_data.get("interested_features", [])

            if primary_role:
                OnboardingChoice.objects.create(
                    progress=progress,
                    step=4,
                    choice_key="primary_role",
                    choice_value=primary_role,
                )

            if interested_features:
                OnboardingChoice.objects.create(
                    progress=progress,
                    step=4,
                    choice_key="interested_features",
                    choice_value=",".join(interested_features),
                )

            # Mark tour complete
            progress.mark_step_complete(4)

            messages.success(request, "Great! Let's get started!")
            return redirect("onboarding_complete")
    else:
        form = TourPreferencesForm()

    context = {
        "form": form,
        "progress": progress,
        "step_number": 4,
        "step_title": "Feature Tour",
        "step_description": "Learn about key features",
    }
    return render(request, "onboarding/step_tour.html", context)


@login_required
def onboarding_complete(request):
    """
    Onboarding Complete - Celebrate and show next steps
    """
    progress = get_or_create_progress(request.user)

    # Ensure onboarding is complete
    if not progress.is_complete:
        progress.complete_onboarding()

    company = request.user.profile.workspace

    # Log completion
    AuditLog.log(
        "ONBOARDING_COMPLETE",
        user=request.user,
        company=company,
        description="Completed onboarding",
        request=request,
        success=True,
    )

    context = {
        "progress": progress,
        "company": company,
    }
    return render(request, "onboarding/complete.html", context)


@login_required
def onboarding_skip(request):
    """
    Skip onboarding entirely (not recommended)
    """
    progress = get_or_create_progress(request.user)

    # Force complete
    progress.complete_onboarding()

    messages.warning(request, "Onboarding skipped. You can access setup from settings.")
    return redirect("workspace_list")
