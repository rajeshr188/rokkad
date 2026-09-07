from __future__ import annotations

from allauth.account.models import EmailAddress
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company, CompanyInvitation, Domain, Membership, Role
from apps.orgs.services.membership_capacity import (
    ensure_role_change_within_capacity,
    ensure_workspace_has_member_capacity,
)
from apps.orgs.services import role_policy
from apps.orgs.lifecycle import validate_transition


def _control_plane_transaction():
    """Open one ordinary atomic control-plane transaction."""

    return transaction.atomic()


def assert_verified_invitation_identity(*, invitation, user):
    """Require proof that the accepting user controls the invited email."""
    invited_email = (invitation.email or "").strip().casefold()
    user_email = (getattr(user, "email", "") or "").strip().casefold()

    if not invited_email or invited_email != user_email:
        raise ValidationError("This invitation was sent to a different email address.")

    if not EmailAddress.objects.filter(
        user=user,
        email__iexact=invitation.email,
        verified=True,
    ).exists():
        raise ValidationError(
            "Verify the invited email address before accepting this invitation."
        )


def create_workspace_from_form(*, form, user, request):
    """Create Workspace, domain, and owner membership atomically."""
    with _control_plane_transaction():
        company = form.save(commit=False)
        company.schema_name = build_schema_name(company.name)
        company.slug = build_workspace_slug(company.name)
        company.creator = user
        company.owner = user
        if Company.all_objects.filter(schema_name=company.schema_name).exists():
            raise ValidationError("Workspace schema name already exists.")
        company.save()

        domain = request.get_host().split(":")[0].lower().removeprefix("www.")
        company_domain = f"{company.slug}.{domain}"
        if Domain.objects.filter(domain=company_domain).exists():
            raise ValidationError("Workspace domain already exists.")
        Domain.objects.create(tenant=company, domain=company_domain, is_primary=True)

        owner_role = Role.objects.get(name="Owner")
        Membership.objects.create(user=user, company=company, role=owner_role)

    AuditLog.log(
        "COMPANY_CREATE",
        user=user,
        company=company,
        description=f"Created company: {company.name}",
        request=request,
        success=True,
    )
    return company


def create_onboarding_workspace_from_form(
    *,
    form,
    user,
    request,
    provision_workspace=None,
    seed_workspace_defaults=None,
):
    """Create an onboarding Workspace without provisioning a database schema."""
    with _control_plane_transaction():
        company = form.save(commit=False)
        company.schema_name = build_schema_name(company.name)
        company.slug = build_workspace_slug(company.name)
        company.creator = user
        company.owner = user
        company.save()
        provisioning_mode = "shared"

        domain = request.get_host().split(":")[0].lower().removeprefix("www.")
        company_domain = f"{company.slug}.{domain}"
        Domain.objects.create(tenant=company, domain=company_domain, is_primary=True)

        owner_role = Role.objects.get(name="Owner")
        Membership.objects.create(user=user, company=company, role=owner_role)

    return company, provisioning_mode


def build_schema_name(name):
    schema_name = slugify(name).replace("-", "_")
    if not schema_name:
        raise ValidationError("Workspace name must contain letters or numbers.")
    if schema_name[0].isdigit():
        schema_name = f"ws_{schema_name}"
    if schema_name == "public":
        raise ValidationError("Workspace slug cannot be public.")
    return schema_name[:63]


def build_workspace_slug(name):
    """Build the canonical immutable route slug for a new Workspace."""
    base = slugify(name)[:63]
    if not base:
        raise ValidationError("Workspace name must contain letters or numbers.")
    if base == "public":
        raise ValidationError("Workspace slug cannot be public.")

    candidate = base
    suffix = 2
    while Company.all_objects.filter(slug=candidate).exists():
        marker = f"-{suffix}"
        candidate = f"{base[: 63 - len(marker)]}{marker}"
        suffix += 1
    return candidate


def save_workspace_update_form(*, form, actor, request):
    """Save workspace updates in public schema."""
    with _control_plane_transaction():
        company = form.save()

    AuditLog.log(
        "COMPANY_UPDATE",
        user=actor,
        company=company,
        description=f"Updated company: {company.name}",
        request=request,
        success=True,
    )
    return company


def transition_workspace_lifecycle(
    *, workspace, target_state, actor, reason, request=None
):
    """Lock and perform one authorized operational lifecycle transition."""
    if not (reason or "").strip():
        raise ValidationError("A lifecycle transition reason is required.")
    with _control_plane_transaction():
        locked = Company.all_objects.select_for_update().get(pk=workspace.pk)
        validate_transition(workspace=locked, target_state=target_state, actor=actor)
        previous_state = locked.lifecycle_state
        locked.lifecycle_state = target_state
        locked.lifecycle_reason = reason.strip()
        locked.lifecycle_changed_at = timezone.now()
        locked.save(
            update_fields=[
                "lifecycle_state",
                "lifecycle_reason",
                "lifecycle_changed_at",
                "updated_at",
            ]
        )
        AuditLog.log(
            "WORKSPACE_LIFECYCLE_CHANGE",
            user=actor,
            company=locked,
            description=f"Workspace lifecycle changed: {previous_state} -> {target_state}",
            request=request,
            success=True,
            data={
                "from_state": previous_state,
                "to_state": target_state,
                "reason": reason.strip(),
            },
        )
    return locked


def archive_workspace(*, company, actor, request, reason="Owner requested archive"):
    return transition_workspace_lifecycle(
        workspace=company,
        target_state=Company.LifecycleState.ARCHIVED,
        actor=actor,
        reason=reason,
        request=request,
    )


def restore_workspace(*, company, actor, request, reason="Owner restored archive"):
    return transition_workspace_lifecycle(
        workspace=company,
        target_state=Company.LifecycleState.ACTIVE,
        actor=actor,
        reason=reason,
        request=request,
    )


def transfer_workspace_ownership(
    *, workspace, new_owner, actor, previous_owner_role, reason, request=None
):
    """Atomically transfer canonical ownership and its mirrored roles."""
    from apps.orgs.permissions import is_platform_admin

    if not (reason or "").strip():
        raise ValidationError("An ownership-transfer reason is required.")
    if previous_owner_role.name.casefold() == "owner":
        raise ValidationError("The previous owner requires a non-owner role.")

    with _control_plane_transaction():
        locked = Company.all_objects.select_for_update().get(pk=workspace.pk)
        if actor != locked.owner and not is_platform_admin(actor):
            raise PermissionDenied("Only the current owner can transfer ownership.")
        if new_owner == locked.owner:
            raise ValidationError("The new owner must be a different member.")

        memberships = {
            item.user_id: item
            for item in Membership.objects.select_for_update()
            .select_related("role")
            .filter(company=locked, user__in=[locked.owner, new_owner])
        }
        previous = memberships.get(locked.owner_id)
        target = memberships.get(new_owner.pk)
        if previous is None or target is None:
            raise ValidationError("Both owners must have Workspace memberships.")

        owner_role = Role.objects.get(name__iexact="Owner")
        locked.owner = new_owner
        locked.save(update_fields=["owner", "updated_at"])
        previous.role = previous_owner_role
        target.role = owner_role
        Membership.objects.bulk_update([previous, target], ["role"])

        AuditLog.log(
            "OWNERSHIP_TRANSFER",
            user=actor,
            company=locked,
            description=f"Transferred ownership to {getattr(new_owner, 'email', new_owner)}",
            request=request,
            success=True,
            data={
                "previous_owner_id": previous.user_id,
                "new_owner_id": target.user_id,
                "reason": reason.strip(),
            },
        )
    return locked


def create_membership(*, user, company, role, request, actor=None, invite_reason=""):
    """Create membership in public schema."""
    ensure_workspace_has_member_capacity(
        workspace=company,
        include_pending_invitations=False,
        extra_slots=1,
    )

    with _control_plane_transaction():
        membership, created = Membership.objects.get_or_create(
            user=user,
            company=company,
            defaults={"role": role, "invite_reason": invite_reason},
        )

    if created and actor is not None:
        AuditLog.log(
            "TEAM_MEMBER_ADD",
            user=actor,
            company=company,
            description=f"Added member: {getattr(user, 'email', user)}",
            request=request,
            success=True,
            content_object=user,
        )

    return membership, created


def remove_membership(*, membership, actor, request):
    """Remove membership in public schema."""
    role_policy.assert_can_remove_membership(
        actor=actor,
        workspace=membership.company,
        membership=membership,
    )
    company = membership.company
    removed_user = membership.user

    with _control_plane_transaction():
        membership.delete()

    AuditLog.log(
        "TEAM_MEMBER_REMOVE",
        user=actor,
        company=company,
        description=f"Removed member: {getattr(removed_user, 'email', removed_user)}",
        request=request,
        success=True,
        content_object=removed_user,
    )


def change_membership_role(*, membership, new_role, actor, request):
    """Change membership role in public schema."""
    ensure_role_change_within_capacity(
        workspace=membership.company,
        old_role=membership.role,
        new_role=new_role,
    )

    role_policy.assert_can_change_role(
        actor=actor,
        workspace=membership.company,
        membership=membership,
        new_role=new_role,
    )
    old_role = membership.role.name
    company = membership.company
    target_user = membership.user

    with _control_plane_transaction():
        membership.role = new_role
        membership.save(update_fields=["role"])

    AuditLog.log(
        "TEAM_ROLE_CHANGE",
        user=actor,
        company=company,
        description=f"Changed {getattr(target_user, 'email', target_user)} role from {old_role} to {new_role.name}",
        request=request,
        success=True,
        content_object=target_user,
        data={"old_role": old_role, "new_role": new_role.name},
    )


def send_team_invitation(*, form, actor, company, request):
    """Create and send invitation in public schema."""
    role_policy.assert_can_invite_role(
        actor=actor,
        workspace=company,
        role=form.cleaned_data["role"],
    )
    ensure_workspace_has_member_capacity(
        workspace=company,
        include_pending_invitations=True,
        extra_slots=1,
    )

    with _control_plane_transaction():
        invitation = form.save()

    AuditLog.log(
        "TEAM_INVITE",
        user=actor,
        company=company,
        description=f"Invited {invitation.email} to company",
        request=request,
        success=True,
        content_object=invitation,
    )
    return invitation


def send_onboarding_team_invitations(
    *,
    email_addresses,
    actor,
    company,
    request,
    role_name="Member",
):
    """Create and send onboarding team invitations in public schema."""
    invited_invitations = []
    failed_invitations = []

    with _control_plane_transaction():
        role = Role.objects.get(name=role_name)
        role_policy.assert_can_invite_role(
            actor=actor,
            workspace=company,
            role=role,
        )

        for email in email_addresses:
            try:
                ensure_workspace_has_member_capacity(
                    workspace=company,
                    include_pending_invitations=True,
                    extra_slots=1,
                )
                invitation = CompanyInvitation.create(
                    email=email,
                    company=company,
                    inviter=actor,
                    role=role,
                )
                invitation.send_invitation(request)
                invited_invitations.append(invitation)
            except Exception as exc:
                failed_invitations.append({"email": email, "error": exc})

    return {
        "invitations": invited_invitations,
        "failed": failed_invitations,
        "invited_count": len(invited_invitations),
        "failed_count": len(failed_invitations),
    }


def accept_invitation(*, invitation, user, request):
    """Accept one verified invitation under lock, idempotently."""
    with _control_plane_transaction():
        locked = (
            CompanyInvitation.objects.select_for_update()
            .select_related("company", "role")
            .get(pk=invitation.pk)
        )
        assert_verified_invitation_identity(invitation=locked, user=user)

        state = locked.lifecycle_state()
        if state == "expired":
            raise ValidationError("This invitation has expired.")
        if state in {
            CompanyInvitation.Status.DECLINED,
            CompanyInvitation.Status.REVOKED,
        }:
            raise ValidationError(f"This invitation is already {state}.")
        if locked.company.lifecycle_state != Company.LifecycleState.ACTIVE:
            raise ValidationError("This Workspace is not accepting invitations.")

        membership = Membership.objects.filter(
            user=user,
            company=locked.company,
        ).first()
        created = False
        if membership is None:
            ensure_workspace_has_member_capacity(
                workspace=locked.company,
                include_pending_invitations=False,
                extra_slots=1,
            )
            membership = Membership.objects.create(
                user=user,
                company=locked.company,
                role=locked.role,
                invite_reason="invitation_accept",
            )
            created = True

        if locked.status != CompanyInvitation.Status.ACCEPTED or not locked.accepted:
            locked.status = CompanyInvitation.Status.ACCEPTED
            locked.accepted = True
            locked.responded_at = timezone.now()
            locked.save(update_fields=["status", "accepted", "responded_at"])

    if created or state != CompanyInvitation.Status.ACCEPTED:
        AuditLog.log(
            "TEAM_INVITE_ACCEPT",
            user=user,
            company=locked.company,
            description=f"Accepted invitation to {locked.company.name}",
            request=request,
            success=True,
            content_object=locked,
        )
    return membership


def decline_invitation(*, invitation, actor, request):
    """Decline invitation in public schema."""
    with _control_plane_transaction():
        invitation.mark_declined()

    AuditLog.log(
        "TEAM_INVITE_DECLINE",
        user=actor,
        company=invitation.company,
        description=f"Declined invitation from {invitation.company.name}",
        request=request,
        success=True,
        content_object=invitation,
    )


def revoke_invitation(*, invitation, actor, request):
    """Revoke invitation in public schema."""
    with _control_plane_transaction():
        invitation.mark_revoked()

    AuditLog.log(
        "TEAM_INVITE_REVOKE",
        user=actor,
        company=invitation.company,
        description=f"Revoked invitation for {invitation.email}",
        request=request,
        success=True,
        content_object=invitation,
    )
