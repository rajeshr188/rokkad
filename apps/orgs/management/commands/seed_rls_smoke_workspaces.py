from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.orgs.models import Company
from apps.tenancy.checks import check_restricted_runtime_role, check_workspace_rls
from apps.tenancy.context import workspace_context
from apps.tenant_apps.rates.models import RateSource


class Command(BaseCommand):
    help = (
        "Create two deterministic development Workspaces and verify runtime-role "
        "RLS isolation with one RateSource in each."
    )

    username = "rls-smoke-owner"
    workspace_specs = (
        ("rls-smoke-one", "RLS Smoke One", "One"),
        ("rls-smoke-two", "RLS Smoke Two", "Two"),
    )
    source_name = "RLS Smoke Source"

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("This development fixture command requires DEBUG=True.")

        role_errors = check_restricted_runtime_role(None, databases=["default"])
        if role_errors:
            raise CommandError(
                "The default connection is not a restricted runtime role: "
                + "; ".join(error.msg for error in role_errors)
            )
        rls_errors = check_workspace_rls(None, databases=["default"])
        if rls_errors:
            raise CommandError(
                "Workspace RLS metadata is incomplete: "
                + "; ".join(error.msg for error in rls_errors)
            )

        user_model = get_user_model()
        owner, _ = user_model.objects.get_or_create(username=self.username)
        if owner.has_usable_password():
            owner.set_unusable_password()
            owner.save(update_fields=["password"])

        fixtures = []
        for slug, name, location in self.workspace_specs:
            workspace, _ = Company.all_objects.get_or_create(
                schema_name=slug,
                defaults={"name": name, "owner": owner, "creator": owner},
            )
            if workspace.lifecycle_state != Company.LifecycleState.ACTIVE:
                raise CommandError(
                    f"Smoke Workspace {workspace.schema_name} is not active; "
                    "change it through the lifecycle service before seeding."
                )
            with workspace_context(workspace.pk):
                source, _ = RateSource.objects.get_or_create(
                    name=self.source_name,
                    defaults={"location": location},
                )
            fixtures.append((workspace, source))

        if RateSource.objects.filter(name=self.source_name).exists():
            raise CommandError("RLS failure: smoke rows are visible without context.")

        for workspace, expected_source in fixtures:
            other_ids = {
                source.pk for _, source in fixtures if source.pk != expected_source.pk
            }
            with workspace_context(workspace.pk):
                visible_ids = set(
                    RateSource.objects.filter(name=self.source_name).values_list(
                        "pk", flat=True
                    )
                )
                if visible_ids != {expected_source.pk}:
                    raise CommandError(
                        f"RLS failure for Workspace {workspace.pk}: "
                        f"visible RateSource ids are {sorted(visible_ids)}."
                    )
                if RateSource.objects.filter(pk__in=other_ids).update(
                    location=expected_source.location
                ):
                    raise CommandError(
                        f"RLS failure: Workspace {workspace.pk} updated another "
                        "Workspace's row."
                    )

        self.stdout.write(
            self.style.SUCCESS(
                "RLS smoke passed: no-context visibility=0; "
                "each Workspace can read only its own RateSource; "
                "cross-Workspace updates affect 0 rows."
            )
        )
        for workspace, source in fixtures:
            self.stdout.write(
                f"workspace={workspace.pk} slug={workspace.slug} "
                f"rate_source={source.pk}"
            )
