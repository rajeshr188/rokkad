from django.db import migrations

from apps.tenant_apps.loans.db_guards import cancellation
from apps.tenant_apps.loans.db_guards import collateral_evidence
from apps.tenant_apps.loans.db_guards import collateral_media
from apps.tenant_apps.loans.db_guards import funding
from apps.tenant_apps.loans.db_guards import license_revision
from apps.tenant_apps.loans.db_guards import operational_notice
from apps.tenant_apps.loans.db_guards import pawn_license
from apps.tenant_apps.loans.db_guards import reversals
from apps.tenant_apps.loans.db_guards import storage
from apps.tenant_apps.loans.db_guards import verification


class Migration(migrations.Migration):
    dependencies = [("loans", "0003_enable_workspace_rls")]

    operations = [
        migrations.RunSQL(funding.FORWARD_SQL, funding.REVERSE_SQL),
        migrations.RunSQL(reversals.FORWARD_SQL, reversals.REVERSE_SQL),
        migrations.RunSQL(
            cancellation.CANCELLATION_GUARD_SQL,
            cancellation.CANCELLATION_GUARD_REVERSE_SQL,
        ),
        migrations.RunSQL(
            license_revision.LICENSE_REVISION_GUARD_SQL,
            license_revision.LICENSE_REVISION_GUARD_REVERSE_SQL,
        ),
        migrations.RunSQL(
            pawn_license.LICENSE_LINK_GUARD_SQL,
            pawn_license.LICENSE_LINK_GUARD_REVERSE_SQL,
        ),
        migrations.RunPython(
            collateral_media.create_media_guards,
            collateral_media.drop_media_guards,
        ),
        migrations.RunPython(
            storage.create_storage_guards,
            storage.drop_storage_guards,
        ),
        verification.Migration.operations[-1],
        operational_notice.Migration.operations[-1],
        migrations.RunPython(
            collateral_evidence.apply_guards,
            collateral_evidence.restore_guards,
        ),
    ]
