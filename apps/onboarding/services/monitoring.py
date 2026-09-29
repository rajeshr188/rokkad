"""Read-only platform report over existing control-plane evidence."""
from datetime import timedelta

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.utils import timezone

from apps.orgs.models import Company, CompanyInvitation, Membership
from apps.orgs.permissions import is_platform_admin
from apps.subscriptions.access_policy import workspace_activity
from apps.subscriptions.models import Subscription, SubscriptionEvent
from apps.tenancy.context import current_workspace_id


def require_report_access(actor):
    if not is_platform_admin(actor) or not actor.is_active or current_workspace_id() is not None:
        raise PermissionDenied("An active platform administrator in global context is required.")


def _workspace_row(workspace, now):
    subscription = Subscription.objects.filter(company=workspace).first()
    acceptance = (SubscriptionEvent.objects.filter(subscription=subscription,
        event_type="trial.started", payload__accepted_terms__version__startswith="public-trial-")
        .only("created_at", "payload").first()) if subscription else None
    invitations = CompanyInvitation.objects.filter(company=workspace)
    outcomes = dict(invitations.values("status").annotate(total=Count("pk"))
                    .values_list("status", "total"))
    recent = []
    for invitation in invitations.select_related("email_delivery").defer("key").order_by("-created", "-pk")[:10]:
        delivery = getattr(invitation, "email_delivery", None)
        recent.append({"email": invitation.email, "state": invitation.lifecycle_state(),
            "responded_at": invitation.responded_at,
            "mail": delivery.get_status_display() if delivery else "No delivery record",
            "attempts": delivery.attempt_count if delivery else 0,
            "current_member": Membership.objects.filter(company=workspace,
                user__email__iexact=invitation.email).exists()})
    activity = workspace_activity(workspace, at=now)
    members = Membership.objects.filter(company=workspace).count()
    step = "Workspace created"
    if acceptance:
        step = "Public trial accepted"
    if outcomes:
        step = "Team invited"
    if outcomes.get("accepted"):
        step = "Team invitation accepted"
    return {"id": workspace.pk, "name": workspace.name, "slug": workspace.slug,
        "lifecycle": workspace.lifecycle_state, "step": step,
        "access": activity.mode, "access_until": activity.until,
        "subscription_status": subscription.status if subscription else "none",
        "trial_kind": "Public trial" if acceptance else "No public trial acceptance recorded",
        "trial_end": subscription.trial_end_date if subscription else None,
        "trial_accepted_at": acceptance.created_at if acceptance else None,
        "trial_original_actor_id": acceptance.payload.get("actor_id") if acceptance else None,
        "members": members, "invitation_count": sum(outcomes.values()),
        "invitation_status_counts": outcomes, "recent_invitations": recent}


def onboarding_report(*, actor, since=None, query="", page=1):
    """No tracking writes, tokens, borrower data or provider requests.

    Account pagination and per-owner Workspace/invitation limits bound detail.
    Stored invitation counts include expired pending rows; detail uses lifecycle.
    """
    require_report_access(actor)
    now = timezone.now()
    since = since or now - timedelta(days=30)
    if timezone.is_naive(since):
        raise ValidationError("The signup cutoff must include a time zone.")
    query = (query or "").strip()[:200]
    accounts = get_user_model().objects.filter(is_active=True, is_superuser=False,
        date_joined__gte=since).select_related("onboarding_progress").order_by("-date_joined", "-pk")
    if query:
        accounts = accounts.filter(Q(email__icontains=query) | Q(username__icontains=query)
            | Q(owned_companies__name__icontains=query) | Q(owned_companies__slug__icontains=query)).distinct()
    pagination = Paginator(accounts, 25).get_page(page)
    rows = []
    for user in pagination.object_list:
        progress = getattr(user, "onboarding_progress", None)
        verified = EmailAddress.objects.filter(user=user, email__iexact=user.email, verified=True).exists()
        workspaces = Company.all_objects.filter(owner=user).order_by("-created_at", "-pk")
        workspace_count = workspaces.count()
        has_membership = Membership.objects.filter(user=user).exists()
        step = "Email verified" if verified else "Account created; email unverified"
        if progress and progress.profile_completed:
            step = "Profile completed"
        rows.append({"id": user.pk, "email": user.email, "signed_up_at": user.date_joined,
            "email_verified": verified, "account_step": step,
            "relationship": "Owner" if workspace_count else "Team member" if has_membership else "No Workspace yet",
            "wizard_complete": bool(progress and progress.is_complete),
            "team_step_skipped": bool(progress and progress.skipped_team),
            "progress_updated_at": progress.updated_at if progress else None,
            "workspace_count": workspace_count,
            "workspaces": [_workspace_row(workspace, now) for workspace in workspaces[:10]]})
    return {"checked_at": now, "since": since, "query": query, "page": pagination.number,
        "pages": pagination.paginator.num_pages, "account_count": pagination.paginator.count,
        "has_previous": pagination.has_previous(), "has_next": pagination.has_next(), "accounts": rows}
