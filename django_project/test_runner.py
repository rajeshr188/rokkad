from django.core.management import call_command
from django.test.runner import DiscoverRunner
from django_tenants.utils import get_public_schema_name


class TenantAwareDiscoverRunner(DiscoverRunner):
    """Run test DB setup via django-tenants migrate_schemas."""

    def setup_databases(self, **kwargs):
        # Skip Django's default migrate step and use tenant-aware migration flow.
        kwargs["migrate"] = False
        old_config = super().setup_databases(**kwargs)

        call_command(
            "migrate_schemas",
            schema_name=get_public_schema_name(),
            interactive=False,
            verbosity=self.verbosity,
        )

        return old_config
