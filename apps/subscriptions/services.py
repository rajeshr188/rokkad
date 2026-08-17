from dataclasses import dataclass
from typing import Any, Optional

from django.conf import settings
from django.core.exceptions import ValidationError


def build_billing_account_defaults(subscription: Any) -> dict[str, Any]:
    """Build default billing-account values from a workspace subscription."""
    company = getattr(subscription, "company", None)
    owner = getattr(company, "owner", None)
    billing_email = getattr(owner, "email", None) or getattr(company, "email", None)

    return {
        "company": company,
        "provider": "razorpay",
        "billing_email": billing_email or "",
        "contact_name": getattr(company, "name", "") or "",
        "billing_phone": "",
    }


def build_entitlement_defaults(subscription: Any) -> list[dict[str, Any]]:
    """Build entitlement defaults from the plan attached to a subscription."""
    plan = getattr(subscription, "plan", None)
    if plan is None:
        return []

    return [
        {
            "feature_code": "reporting.advanced",
            "enabled": bool(getattr(plan, "has_advanced_reporting", False)),
        },
        {
            "feature_code": "inventory.multi_warehouse",
            "enabled": bool(getattr(plan, "has_multi_warehouse", False)),
        },
        {
            "feature_code": "workflow.approvals",
            "enabled": bool(getattr(plan, "has_approvals_workflow", False)),
        },
        {
            "feature_code": "api.access",
            "enabled": bool(getattr(plan, "has_api_access", False)),
        },
        {
            "feature_code": "workspace.custom_fields",
            "enabled": bool(getattr(plan, "has_custom_fields", False)),
        },
        {
            "feature_code": "workspace.max_members",
            "enabled": True,
            "value": str(getattr(plan, "max_users", 0)),
        },
        {
            "feature_code": "inventory.max_products",
            "enabled": True,
            "value": str(getattr(plan, "max_products", 0)),
        },
        {
            "feature_code": "inventory.max_warehouses",
            "enabled": True,
            "value": str(getattr(plan, "max_warehouses", 0)),
        },
        {
            "feature_code": "workspace.max_transactions_per_month",
            "enabled": True,
            "value": str(getattr(plan, "max_transactions_per_month", 0)),
        },
        {
            "feature_code": "workspace.max_invoices_per_month",
            "enabled": True,
            "value": str(getattr(plan, "max_invoices_per_month", 0)),
        },
    ]


def ensure_billing_account_for_subscription(subscription: Any, dry_run: bool = False) -> tuple[Any, bool]:
    """Create or update the billing account for a workspace subscription."""
    from apps.subscriptions.models import BillingAccount

    company = getattr(subscription, "company", None)
    if company is None:
        return None, False

    defaults = build_billing_account_defaults(subscription)
    defaults.pop("company", None)

    if dry_run:
        account = BillingAccount.objects.filter(company=company).first()
        return account, account is None

    account, created = BillingAccount.objects.get_or_create(
        company=company,
        defaults=defaults,
    )

    if not created:
        changed = False
        for field_name, value in defaults.items():
            if getattr(account, field_name) != value:
                setattr(account, field_name, value)
                changed = True
        if changed:
            account.save(update_fields=list(defaults.keys()))

    return account, created


def ensure_entitlements_for_subscription(subscription: Any, dry_run: bool = False) -> list[tuple[Any, bool]]:
    """Ensure the subscription has entitlement rows for its current plan."""
    from apps.subscriptions.models import SubscriptionEntitlement

    created_entities: list[tuple[Any, bool]] = []
    for payload in build_entitlement_defaults(subscription):
        if dry_run:
            entitlement = SubscriptionEntitlement.objects.filter(
                subscription=subscription,
                feature_code=payload["feature_code"],
            ).first()
            created_entities.append((entitlement, entitlement is None))
            continue

        entitlement, created = SubscriptionEntitlement.objects.get_or_create(
            subscription=subscription,
            feature_code=payload["feature_code"],
            defaults={
                "enabled": payload.get("enabled", True),
                "value": payload.get("value", ""),
            },
        )
        if not created:
            if entitlement.source == "override":
                created_entities.append((entitlement, False))
                continue
            changed = False
            if entitlement.enabled != payload.get("enabled", True):
                entitlement.enabled = payload.get("enabled", True)
                changed = True
            if entitlement.value != payload.get("value", ""):
                entitlement.value = payload.get("value", "")
                changed = True
            if changed:
                entitlement.save(update_fields=["enabled", "value"])
        created_entities.append((entitlement, created))

    return created_entities


def _parse_positive_int(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def resolve_workspace_max_users_limit(*, workspace: Any, subscription: Optional[Any] = None) -> Optional[int]:
    """Resolve the effective member limit through the canonical entitlement API."""
    if workspace is None or "subscriptions" not in settings.INSTALLED_APPS:
        return None

    from apps.subscriptions.entitlements import limit

    return limit(workspace, "workspace.max_members")


def get_workspace_member_usage(*, workspace: Any, include_pending_invitations: bool = False) -> int:
    """Return current seat usage for a workspace."""
    if workspace is None:
        return 0

    from apps.orgs.models import Membership

    member_count = Membership.objects.filter(company=workspace).count()
    if not include_pending_invitations:
        return member_count

    from apps.orgs.models import CompanyInvitation

    pending_invitation_count = CompanyInvitation.pending_queryset().filter(
        company=workspace
    ).count()
    return member_count + pending_invitation_count


def ensure_workspace_member_capacity(
    *,
    workspace: Any,
    include_pending_invitations: bool = False,
    extra_slots: int = 1,
) -> None:
    """Fail when adding new users/invitations would exceed workspace seat capacity."""
    seat_limit = resolve_workspace_max_users_limit(workspace=workspace)
    if seat_limit is None:
        return

    extra_slots = max(0, int(extra_slots))
    used_seats = get_workspace_member_usage(
        workspace=workspace,
        include_pending_invitations=include_pending_invitations,
    )

    if used_seats + extra_slots > seat_limit:
        raise ValidationError(
            f"Workspace seat limit reached ({used_seats}/{seat_limit}). Upgrade your plan to add more members."
        )


@dataclass
class AccessDecision:
    allowed: bool
    reason: str = "AUTHORIZED"
    message: str = ""
    membership: Optional[Any] = None
    subscription: Optional[Any] = None
    entitlement: Optional[Any] = None


class SubscriptionAccessService:
    """Centralized subscription and entitlement access evaluation for workspaces."""

    def evaluate_access(
        self,
        *,
        user: Any,
        workspace: Any,
        membership: Optional[Any] = None,
        subscription: Optional[Any] = None,
        entitlement: Optional[Any] = None,
        feature_code: Optional[str] = None,
    ) -> AccessDecision:
        if not user:
            return AccessDecision(False, "AUTH_REQUIRED", "Authentication required.")

        has_authenticated_flag = hasattr(user, "is_authenticated")
        is_authenticated = getattr(user, "is_authenticated", True)
        if has_authenticated_flag and not is_authenticated:
            return AccessDecision(False, "AUTH_REQUIRED", "Authentication required.")

        if workspace is None:
            return AccessDecision(False, "NO_WORKSPACE", "No workspace selected.")

        if getattr(workspace, "schema_name", None) == "public":
            return AccessDecision(True, "PUBLIC_WORKSPACE", "")

        if membership is None:
            membership = self._get_membership(user=user, workspace=workspace)

        if membership is None:
            return AccessDecision(
                False,
                "NO_MEMBERSHIP",
                "You are not a member of this workspace.",
                membership=None,
            )

        if subscription is None:
            subscription = self._get_subscription(workspace=workspace)

        if subscription is None:
            return AccessDecision(
                False,
                "NO_SUBSCRIPTION",
                "This workspace does not have an active subscription.",
                membership=membership,
                subscription=None,
            )

        from apps.subscriptions.billing import effective_billing_state

        if not effective_billing_state(subscription).commercially_available:
            return AccessDecision(
                False,
                "SUBSCRIPTION_INACTIVE",
                "This workspace subscription is not active.",
                membership=membership,
                subscription=subscription,
            )

        if feature_code:
            from apps.subscriptions.entitlements import enabled

            feature_enabled = (
                bool(entitlement.enabled)
                if entitlement is not None
                else enabled(workspace, feature_code)
            )
            if not feature_enabled:
                return AccessDecision(
                    False,
                    "FEATURE_BLOCKED",
                    f"This workspace does not have access to {feature_code}.",
                    membership=membership,
                    subscription=subscription,
                    entitlement=entitlement,
                )

        return AccessDecision(True, "AUTHORIZED", "", membership=membership, subscription=subscription, entitlement=entitlement)

    def can_access_workspace(self, *, user: Any, workspace: Any) -> bool:
        return self.evaluate_access(user=user, workspace=workspace).allowed

    def can_access_feature(self, *, user: Any, workspace: Any, feature_code: str) -> bool:
        return self.evaluate_access(
            user=user,
            workspace=workspace,
            feature_code=feature_code,
        ).allowed

    def ensure_access(self, *, user: Any, workspace: Any, feature_code: Optional[str] = None) -> AccessDecision:
        return self.evaluate_access(user=user, workspace=workspace, feature_code=feature_code)

    def _get_membership(self, *, user: Any, workspace: Any) -> Optional[Any]:
        if not getattr(user, "is_authenticated", False):
            return None

        try:
            from apps.orgs.models import Membership

            return Membership.objects.select_related("role").get(user=user, company=workspace)
        except Exception:
            return None

    def _get_subscription(self, *, workspace: Any) -> Optional[Any]:
        if "subscriptions" not in settings.INSTALLED_APPS:
            return None

        try:
            from apps.subscriptions.models import Subscription

            return (
                Subscription.objects.filter(company=workspace)
                .order_by("-created_at")
                .first()
            )
        except Exception:
            return None

    def _get_entitlement(self, *, subscription: Any, feature_code: str) -> Optional[Any]:
        try:
            from apps.subscriptions.models import SubscriptionEntitlement

            return SubscriptionEntitlement.objects.filter(
                subscription=subscription,
                feature_code=feature_code,
            ).first()
        except Exception:
            return None
