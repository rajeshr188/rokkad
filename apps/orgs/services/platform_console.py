"""Read-only global platform metadata; never enters a business Workspace."""
from datetime import timedelta

from allauth.account.models import EmailAddress
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.orgs.models import Company, CompanyInvitation, Membership
from apps.orgs.audit import AuditLog
from apps.orgs.permissions import is_platform_admin
from apps.platform_mail.models import Delivery
from apps.subscriptions.access_policy import workspace_activity
from apps.subscriptions.models import WorkspaceAccessDecision
from apps.tenancy.context import current_workspace_id


ATTENTION = (("", "All workspaces"), ("trial_ending", "Trials ending within 7 days"),
             ("no_subscription", "No subscription record"), ("mail", "Invitation email needs review"))
MAIL_REVIEW = ("failed", "unknown", "bounced", "complaint", "suppressed")
ACCESS_LABELS = {"full": "Full access", "grace": "Grace period", "read_only": "Read-only",
                 "blocked": "Blocked by lifecycle", "recovery": "Setup / recovery only"}


def require_console_access(actor):
    if not actor or not is_platform_admin(actor) or not actor.is_active or current_workspace_id() is not None:
        raise PermissionDenied("An active platform administrator in global context is required.")


def workspaces():
    # The historical public sentinel is not a customer Workspace.
    return Company.all_objects.exclude(slug="public")


def filtered_workspaces(*, query="", lifecycle="", attention="", at=None):
    now = at or timezone.now()
    rows = workspaces()
    if query:
        rows = rows.filter(Q(name__icontains=query) | Q(slug__icontains=query) | Q(owner__email__icontains=query))
    if lifecycle:
        rows = rows.filter(lifecycle_state=lifecycle)
    if attention == "trial_ending":
        rows = rows.filter(lifecycle_state="ACTIVE", subscription__status="trial",
                           subscription__trial_end_date__gte=now,
                           subscription__trial_end_date__lte=now + timedelta(days=7))
    elif attention == "no_subscription":
        rows = rows.filter(subscription__isnull=True)
    elif attention == "mail":
        rows = rows.filter(Exists(Delivery.objects.filter(invitation__company_id=OuterRef("pk"),
                                                          status__in=MAIL_REVIEW)))
    return rows


def workspace_row(workspace, *, at):
    activity = workspace_activity(workspace, at=at)
    subscription = getattr(workspace, "subscription", None)
    return {"workspace": workspace, "activity": activity,
            "access_label": ACCESS_LABELS[activity.mode], "subscription": subscription,
            "subscription_label": "Trial" if subscription and subscription.status == "trial"
                else subscription.get_status_display() if subscription else "No subscription"}


def console_overview(*, actor):
    require_console_access(actor)
    now = timezone.now()
    counts = workspaces().aggregate(total=Count("pk"), active=Count("pk", filter=Q(lifecycle_state="ACTIVE")),
        suspended=Count("pk", filter=Q(lifecycle_state="SUSPENDED")))
    counts["trial_ending"] = filtered_workspaces(attention="trial_ending", at=now).count()
    counts["no_subscription"] = filtered_workspaces(attention="no_subscription", at=now).count()
    counts["mail"] = filtered_workspaces(attention="mail", at=now).count()
    return {"counts": counts, "checked_at": now,
            "recent": list(workspaces().select_related("owner").order_by("-created_at", "-pk")[:5])}


def console_directory(*, actor, query="", lifecycle="", attention="", page=1):
    require_console_access(actor)
    now = timezone.now()
    rows = filtered_workspaces(query=query, lifecycle=lifecycle, attention=attention, at=now)
    rows = rows.select_related("owner", "subscription", "subscription__plan").annotate(
        member_count=Count("memberships", distinct=True)).order_by("name", "pk")
    pagination = Paginator(rows, 25).get_page(page)
    return {"page": pagination, "rows": [workspace_row(w, at=now) for w in pagination.object_list],
            "checked_at": now}


def console_workspace(*, actor, slug, invitation_page=1):
    require_console_access(actor)
    now = timezone.now()
    workspace = get_object_or_404(workspaces().select_related("owner", "subscription", "subscription__plan"), slug=slug)
    result = workspace_row(workspace, at=now)
    invitations = CompanyInvitation.objects.filter(company=workspace).select_related("email_delivery", "role").defer(
        "key", "role_fingerprint").order_by("-created", "-pk")
    pagination = Paginator(invitations, 10).get_page(invitation_page)
    from django.db.models.functions import Lower
    member_emails = set(Membership.objects.filter(company=workspace).annotate(normalized_email=Lower("user__email"))
        .filter(normalized_email__in=[i.email.casefold() for i in pagination.object_list])
        .values_list("normalized_email", flat=True))
    recent = []
    for invitation in pagination.object_list:
        delivery = getattr(invitation, "email_delivery", None)
        recent.append({"email": invitation.email, "role": invitation.role.name,
            "state": invitation.lifecycle_state(), "mail": delivery.get_status_display() if delivery else "No delivery record",
            "member": invitation.email.casefold() in member_emails, "created": invitation.created})
    result.update({"checked_at": now, "invitations": recent, "invitation_page": pagination,
        "member_count": Membership.objects.filter(company=workspace).count(),
        "owner_verified": EmailAddress.objects.filter(user=workspace.owner,
            email__iexact=workspace.owner.email, verified=True).exists(),
        "decisions": list(WorkspaceAccessDecision.objects.filter(workspace=workspace).select_related("actor")[:10]),
        # Do not render arbitrary audit JSON, tokens or borrower-related events.
        "audit_url_query": f"company__id__exact={workspace.pk}"})
    result["lifecycle_history"] = [{"actor": event.user, "at": event.timestamp,
        "before": event.data.get("from_state", ""), "after": event.data.get("to_state", ""),
        "reason": event.data.get("reason", "")} for event in AuditLog.objects.filter(
            company=workspace, action="WORKSPACE_LIFECYCLE_CHANGE", success=True)
            .select_related("user").order_by("-timestamp", "-pk")[:10]]
    return result
