from dataclasses import dataclass
from typing import Literal

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from .billing import effective_billing_state
from .models import Subscription, SubscriptionEntitlement


EntitlementKind = Literal["boolean", "limit"]


@dataclass(frozen=True)
class EntitlementDefinition:
    code: str
    kind: EntitlementKind


REGISTRY = {
    "reporting.advanced": EntitlementDefinition("reporting.advanced", "boolean"),
    "inventory.multi_warehouse": EntitlementDefinition("inventory.multi_warehouse", "boolean"),
    "workflow.approvals": EntitlementDefinition("workflow.approvals", "boolean"),
    "api.access": EntitlementDefinition("api.access", "boolean"),
    "workspace.custom_fields": EntitlementDefinition("workspace.custom_fields", "boolean"),
    "workspace.max_members": EntitlementDefinition("workspace.max_members", "limit"),
    "inventory.max_products": EntitlementDefinition("inventory.max_products", "limit"),
    "inventory.max_warehouses": EntitlementDefinition("inventory.max_warehouses", "limit"),
    "workspace.max_transactions_per_month": EntitlementDefinition("workspace.max_transactions_per_month", "limit"),
    "workspace.max_invoices_per_month": EntitlementDefinition("workspace.max_invoices_per_month", "limit"),
}

ALIASES = {
    "advanced_reporting": "reporting.advanced",
    "multi_warehouse": "inventory.multi_warehouse",
    "approvals": "workflow.approvals",
    "api": "api.access",
    "custom_fields": "workspace.custom_fields",
    "max_users": "workspace.max_members",
    "max_products": "inventory.max_products",
    "max_warehouses": "inventory.max_warehouses",
    "max_transactions_per_month": "workspace.max_transactions_per_month",
    "max_invoices_per_month": "workspace.max_invoices_per_month",
}


def canonical_code(code):
    return ALIASES.get(code, code)


def _row(workspace, code):
    code = canonical_code(code)
    definition = REGISTRY.get(code)
    if definition is None:
        return definition, None
    subscription = Subscription.objects.filter(company=workspace).first()
    if subscription is None or not effective_billing_state(subscription).commercially_available:
        return definition, None
    row = SubscriptionEntitlement.objects.filter(subscription=subscription, feature_code=code).first()
    if row and row.expires_at and row.expires_at <= timezone.now():
        row = None
    return definition, row


def enabled(workspace, code):
    definition, row = _row(workspace, code)
    return bool(definition and definition.kind == "boolean" and row and row.enabled)


def require(workspace, code):
    if not enabled(workspace, code):
        raise PermissionDenied(f"Workspace entitlement denied: {canonical_code(code)}")


def limit(workspace, code):
    definition, row = _row(workspace, code)
    if not definition or definition.kind != "limit" or not row or not row.enabled:
        return None
    try:
        value = int(row.value)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None
