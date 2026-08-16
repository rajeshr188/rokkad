"""Read-only consistency inventory for the public SaaS control plane."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Exists, F, OuterRef
from django.db.models.functions import Lower

from apps.orgs.models import (
    Company,
    CompanyInvitation,
    CompanyOwnership,
    Membership,
    PendingInvitation,
    Role,
)


def _source_reference_counts():
    """Count active Python references that define competing foundation paths."""
    root = Path(settings.BASE_DIR)
    needles = {
        "pending_invitation": "PendingInvitation",
        "company_ownership": "CompanyOwnership",
        "guardian": "guardian",
        "hardcoded_role_permissions": "RolePermissions",
        "subscription_access_service": "SubscriptionAccessService",
        "profile_workspace_fallback": "profile_workspace",
    }
    counts = {name: 0 for name in needles}

    search_roots = [root / "accounts", root / "apps", root / "django_project"]
    for search_root in search_roots:
        if not search_root.exists():
            continue
        for path in search_root.rglob("*.py"):
            if "migrations" in path.parts or "__pycache__" in path.parts:
                continue
            try:
                content = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                continue
            for name, needle in needles.items():
                counts[name] += content.count(needle)
    return counts


def collect_saas_foundation_inventory():
    """Return public-schema consistency counts without mutating data."""
    public_schema = "public"

    with transaction.atomic():
        companies = Company.all_objects.exclude(schema_name=public_schema)
        owner_membership = Membership.objects.filter(
            company_id=OuterRef("pk"),
            user_id=OuterRef("owner_id"),
        )
        owner_role_membership = owner_membership.filter(role__name__iexact="Owner")

        owner_missing_membership = companies.annotate(
            has_owner_membership=Exists(owner_membership)
        ).filter(has_owner_membership=False)
        owner_wrong_role = companies.annotate(
            has_owner_role=Exists(owner_role_membership)
        ).filter(has_owner_role=False)

        active_ownerships = CompanyOwnership.objects.filter(end_date__isnull=True)
        multiple_active_ownerships = (
            active_ownerships.values("company_id")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
        )
        ownership_disagreements = active_ownerships.exclude(
            user_id=F("company__owner_id")
        )

        authoritative_pending = CompanyInvitation.pending_queryset()
        matching_invitation = authoritative_pending.filter(
            company_id=OuterRef("company_id"),
            email__iexact=OuterRef("email"),
        )
        orphan_pending_bridges = PendingInvitation.objects.annotate(
            has_invitation=Exists(matching_invitation)
        ).filter(has_invitation=False)

        case_variant_invitation_groups = (
            authoritative_pending.annotate(normalized_email=Lower("email"))
            .values("company_id", "normalized_email")
            .annotate(total=Count("id"))
            .filter(total__gt=1)
        )

        role_rows = list(
            Role.objects.annotate(permission_count=Count("permissions"))
            .order_by("name")
            .values("id", "name", "permission_count")
        )

        guardian_user_assignments = 0
        guardian_group_assignments = 0
        if "guardian" in settings.INSTALLED_APPS:
            from guardian.models import GroupObjectPermission, UserObjectPermission

            guardian_user_assignments = UserObjectPermission.objects.count()
            guardian_group_assignments = GroupObjectPermission.objects.count()

        inventory = {
            "schema": public_schema,
            "read_only": True,
            "companies": {
                "total_non_public": companies.count(),
                "archived": companies.filter(is_deleted=True).count(),
                "owner_missing_membership": owner_missing_membership.count(),
                "owner_without_owner_role": owner_wrong_role.count(),
            },
            "memberships": {
                "total": Membership.objects.count(),
                "null_role": Membership.objects.filter(role__isnull=True).count(),
            },
            "ownership": {
                "history_rows": CompanyOwnership.objects.count(),
                "multiple_active_company_groups": multiple_active_ownerships.count(),
                "active_row_disagrees_with_company_owner": ownership_disagreements.count(),
            },
            "invitations": {
                "company_invitation_total": CompanyInvitation.objects.count(),
                "company_invitation_pending": authoritative_pending.count(),
                "pending_bridge_total": PendingInvitation.objects.count(),
                "orphan_pending_bridge": orphan_pending_bridges.count(),
                "case_variant_pending_groups": case_variant_invitation_groups.count(),
            },
            "roles": role_rows,
            "guardian": {
                "installed": "guardian" in settings.INSTALLED_APPS,
                "user_object_permission_rows": guardian_user_assignments,
                "group_object_permission_rows": guardian_group_assignments,
            },
        }

    inventory["source_references"] = _source_reference_counts()
    return inventory


class Command(BaseCommand):
    help = "Report read-only SaaS foundation consistency and duplication counts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Emit machine-readable JSON.",
        )
        parser.add_argument(
            "--fail-on-findings",
            action="store_true",
            help="Exit non-zero when integrity findings are present.",
        )

    def handle(self, *args, **options):
        inventory = collect_saas_foundation_inventory()
        finding_count = sum(
            [
                inventory["companies"]["owner_missing_membership"],
                inventory["companies"]["owner_without_owner_role"],
                inventory["memberships"]["null_role"],
                inventory["ownership"]["multiple_active_company_groups"],
                inventory["ownership"]["active_row_disagrees_with_company_owner"],
                inventory["invitations"]["orphan_pending_bridge"],
                inventory["invitations"]["case_variant_pending_groups"],
            ]
        )
        inventory["integrity_finding_count"] = finding_count

        if options["as_json"]:
            self.stdout.write(json.dumps(inventory, indent=2, sort_keys=True))
        else:
            self.stdout.write("SaaS foundation inventory (read-only)")
            self.stdout.write(json.dumps(inventory, indent=2, sort_keys=True))

        if options["fail_on_findings"] and finding_count:
            raise SystemExit(1)
