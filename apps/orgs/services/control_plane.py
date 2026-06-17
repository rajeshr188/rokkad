from __future__ import annotations

from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django_tenants.utils import get_public_schema_name, remove_www, schema_context

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company, CompanyInvitation, Domain, Membership, Role
from apps.orgs.services import role_policy


def _public_schema_context():
    return schema_context(get_public_schema_name())


def create_workspace_from_form(*, form, user, request):
    """Create workspace and owner membership in public schema."""
    with _public_schema_context():
        company = form.save(commit=False)
        company.schema_name = build_schema_name(company.name)
        company.creator = user
        company.owner = user
        if Company.all_objects.filter(schema_name=company.schema_name).exists():
            raise ValidationError("Workspace schema name already exists.")
        company.save()

        domain = remove_www(request.get_host().split(":")[0]).lower()
        company_domain = f"{company.schema_name}.{domain}"
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


def build_schema_name(name):
    schema_name = slugify(name).replace("-", "_")
    if not schema_name:
        raise ValidationError("Workspace name must contain letters or numbers.")
    if schema_name[0].isdigit():
        schema_name = f"ws_{schema_name}"
    if schema_name == get_public_schema_name():
        raise ValidationError("Workspace schema name cannot be public.")
    return schema_name[:63]


def save_workspace_update_form(*, form, actor, request):
    """Save workspace updates in public schema."""
    with _public_schema_context():
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


def archive_workspace(*, company, actor, request):
    """Archive workspace in public schema."""
    with _public_schema_context():
        company.archive()

    AuditLog.log(
        "COMPANY_DELETE",
        user=actor,
        company=company,
        description=f"Archived workspace: {company.name}",
        request=request,
        success=True,
    )


def create_membership(*, user, company, role, request, actor=None, invite_reason=""):
    """Create membership in public schema."""
    with _public_schema_context():
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

    with _public_schema_context():
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
    role_policy.assert_can_change_role(
        actor=actor,
        workspace=membership.company,
        membership=membership,
        new_role=new_role,
    )
    old_role = membership.role.name
    company = membership.company
    target_user = membership.user

    with _public_schema_context():
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
    with _public_schema_context():
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


def accept_invitation(*, invitation, user, request):
    """Accept invitation in public schema and ensure membership exists."""
    with _public_schema_context():
        existing = Membership.objects.filter(user=user, company=invitation.company).exists()
        if not existing:
            Membership.objects.create(
                user=user,
                company=invitation.company,
                role=invitation.role,
                invite_reason="invitation_accept",
            )

        invitation.accept(request)

    AuditLog.log(
        "TEAM_INVITE_ACCEPT",
        user=user,
        company=invitation.company,
        description=f"Accepted invitation to {invitation.company.name}",
        request=request,
        success=True,
        content_object=invitation,
    )


def decline_invitation(*, invitation, actor, request):
    """Decline invitation in public schema."""
    with _public_schema_context():
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
    with _public_schema_context():
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
