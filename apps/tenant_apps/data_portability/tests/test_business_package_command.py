from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

from django.core.management import call_command, CommandError
from django.db import connection
from django.test import override_settings

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.data_portability import business_package as package
from apps.tenant_apps.data_portability.models import BusinessPackageReceipt, WorkspaceNamespace
from .test_concurrency import PortabilityConcurrencyTests


class BusinessPackageCommandTests(PortabilityConcurrencyTests):
    def test_explicit_monitoring_choice_uses_version_three_in_real_command_restore(self):
        from datetime import date
        from apps.tenant_apps.loans.models import LoanMonitoringPolicy
        with workspace_context(self.workspace.pk):
            LoanMonitoringPolicy.objects.create(workspace=self.workspace,version=1,effective_from=date(2020,1,1),
                compliance_profile='Reviewed current metal monitoring',valuation_basis='CALCULATED_METAL_VALUE',
                ltv_warning_ratio='.7',ltv_breach_ratio='.8',ltv_critical_ratio='.9',
                eligible_custody_states=['IN_VAULT'],severity_mapping={'strategy':'derived-v1'},created_by=self.actor)
        target=Company.objects.create(name='Empty monitoring destination',schema_name='monitor-'+self.workspace.schema_name,
            owner=self.actor,creator=self.actor)
        Membership.objects.create(company=target,user=self.actor,role=Role.objects.get(name='Owner'))
        with TemporaryDirectory() as private,override_settings(MEDIA_ROOT=Path(private)/'storage'):
            directory=Path(private)/'source'
            with connection.cursor() as cursor:cursor.execute(f'SET ROLE {self.role}')
            try:
                output=StringIO()
                call_command('business_package','export',workspace_id=self.workspace.pk,actor_id=self.actor.pk,
                    directory=str(directory),stdout=output)
                checksum=json.loads(output.getvalue())['sha256']
                doc,_,_=package.read_package(directory,expected_sha256=checksum)
                self.assertEqual(doc['profile'],package.MONITORING_PROFILE)
                self.assertEqual(doc['snapshot']['consistency'],'repeatable-read')
                args=dict(workspace_id=target.pk,actor_id=self.actor.pk,directory=str(directory),
                    expected_sha256=checksum,review_file=str(Path(private)/'review.json'))
                call_command('business_package','preview',**args,stdout=StringIO())
                call_command('business_package','restore',**args,confirm=True,stdout=StringIO())
                with workspace_context(target.pk):
                    self.assertEqual(LoanMonitoringPolicy.objects.get().valuation_basis,'CALCULATED_METAL_VALUE')
                    self.assertEqual(BusinessPackageReceipt.objects.get().summary['profile'],package.MONITORING_PROFILE)
            finally:
                with connection.cursor() as cursor:cursor.execute('RESET ROLE')

    def test_fresh_command_snapshot_preview_restore_and_retry(self):
        with workspace_context(self.workspace.pk):
            Party.objects.create(display_name='Fresh command source',party_code='SRC01')
        target=Company.objects.create(name='Empty command destination',schema_name='dest-'+self.workspace.schema_name,
            owner=self.actor,creator=self.actor)
        Membership.objects.get_or_create(company=target,user=self.actor,defaults={'role':Role.objects.get(name='Owner')})
        with TemporaryDirectory() as private, override_settings(MEDIA_ROOT=Path(private)/'storage'):
            directory=Path(private)/'export'
            review_file=Path(private)/'review.json'
            with connection.cursor() as cursor:
                cursor.execute(f'SET ROLE {self.role}')
            try:
                output=StringIO()
                call_command('business_package','export',workspace_id=self.workspace.pk,actor_id=self.actor.pk,
                    directory=str(directory),stdout=output)
                checksum=json.loads(output.getvalue())['sha256']
                doc,_,_=package.read_package(directory,expected_sha256=checksum)
                self.assertEqual(doc['snapshot']['consistency'],'repeatable-read')
                args=dict(workspace_id=target.pk,actor_id=self.actor.pk,directory=str(directory),
                    expected_sha256=checksum,review_file=str(review_file))
                call_command('business_package','preview',**args,stdout=StringIO())
                with workspace_context(target.pk):
                    self.assertFalse(Party.objects.exists())
                with self.assertRaises(CommandError):
                    call_command('business_package','restore',**args,stdout=StringIO())
                for _ in range(2):
                    call_command('business_package','restore',**args,confirm=True,stdout=StringIO())
                with workspace_context(target.pk):
                    self.assertEqual(Party.objects.get().party_code,'SRC01')
                    self.assertEqual(BusinessPackageReceipt.objects.count(),1)
            finally:
                with connection.cursor() as cursor:
                    cursor.execute('RESET ROLE')

    def test_failed_package_export_never_publishes_source_or_identities(self):
        with workspace_context(self.workspace.pk):
            Party.objects.create(display_name='Failed command source',party_code='SRC01')
        with TemporaryDirectory() as private:
            directory=Path(private)/'export'
            with patch.object(package.setup,'export_setup',side_effect=ValueError('Unsupported setup')):
                with self.assertRaises(CommandError):
                    call_command('business_package','export',workspace_id=self.workspace.pk,actor_id=self.actor.pk,
                        directory=str(directory),stdout=StringIO())
            self.assertFalse(directory.exists())
            self.assertEqual(list(Path(private).iterdir()),[])
        with workspace_context(self.workspace.pk):
            self.assertFalse(WorkspaceNamespace.objects.exists())
