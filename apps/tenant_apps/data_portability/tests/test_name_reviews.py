from copy import deepcopy
from django.core.exceptions import PermissionDenied
from apps.tenant_apps.data_portability import services
from apps.tenant_apps.data_portability.name_reviews import review_distinct_names
from apps.tenant_apps.data_portability.presets import save_preset
from apps.tenant_apps.data_portability.parsers import PortabilityError
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.data_portability.models import SourceIdentity
from . import test_portability as fixtures

MAPPING = fixtures.MAPPING


class NameReviewTests(fixtures.PortabilityTests):
    def test_review_http_action_only_revalidates_and_existing_name_stays_separate(self):
        from django.test import RequestFactory
        from apps.tenant_apps.data_portability import views
        with self.scoped():
            existing=Party.objects.create(workspace=self.a,display_name='Same Name',party_type='INDIVIDUAL')
            b=self.prepare_names()
            request=RequestFactory().post('/', {'action':'review_distinct_names','source_ids':'a\nb',
                'reason':'Preserve separate source customer records.','approval_digest':b.approval_digest})
            request.user=self.actor;request.workspace=self.a
            response=views.batch_detail(request,b.public_id)
            self.assertEqual(response.status_code,302)
            self.assertEqual(Party.objects.count(),1)
            b.refresh_from_db()
            self.assertEqual(b.mapping['name_reviews']['a']['party_ids'],[existing.pk])
            self.commit_names(b)
            self.assertEqual(Party.objects.filter(display_name='Same Name').count(),3)

    def test_review_does_not_allow_existing_customer_phone_match(self):
        with self.scoped():
            existing=Party.objects.create(workspace=self.a,display_name='Same Name',party_type='INDIVIDUAL')
            b=self.review_names(self.prepare_names(b'Legacy,Party,Phone\na,Same Name,9876543210\n'),ids=('a',))
            existing.primary_phone=b.rows.get().canonical['primary_phone'];existing.save()
            with self.assertRaises(PortabilityError):self.commit_names(b)
            self.assertEqual(Party.objects.count(),1)

    def prepare_names(self, content=b'Legacy,Party,Phone\na,Same Name,\nb,Same Name,\n'):
        b=self.stage(content=content)
        return services.validate_import(workspace_id=self.a.pk,actor=self.actor,batch_id=b.public_id,mapping=deepcopy(MAPPING))

    def review_names(self,b,ids=('a','b'),**overrides):
        return review_distinct_names(**{**dict(workspace_id=self.a.pk,actor=self.actor,batch_id=b.public_id,
            external_ids=list(ids),reason='Reviewed separate customer IDs in the source register.',approval_digest=b.approval_digest),**overrides})

    def commit_names(self,b,ack=True):
        return services.commit_import(workspace_id=self.a.pk,actor=self.actor,batch_id=b.public_id,
            approval_digest=b.approval_digest,acknowledge_warnings=ack)

    def test_name_review_creates_distinct_identities_and_replay_does_not_merge(self):
        with self.scoped():
            b=self.prepare_names()
            self.assertEqual(b.summary['conflicts'],2)
            b=self.review_names(b)
            self.assertEqual(b.state,'READY')
            self.assertEqual(b.summary['rows_with_warnings'],2)
            with self.assertRaises(PortabilityError): self.commit_names(b,ack=False)
            self.commit_names(b)
            self.commit_names(b)
            self.assertEqual(Party.objects.filter(display_name='Same Name').count(),2)
            self.assertEqual(len(set(SourceIdentity.objects.values_list('identity__party_id',flat=True))),2)

    def test_one_review_does_not_silently_resolve_an_unreviewed_row(self):
        with self.scoped():
            b=self.review_names(self.prepare_names(),ids=('a',))
            self.assertEqual(b.summary['conflicts'],2)

    def test_name_review_keeps_stronger_identity_and_duplicate_source_checks(self):
        with self.scoped():
            b=self.prepare_names(b'Legacy,Party,Phone\na,Same Name,9876543210\nb,Same Name,9876543210\n')
            b=self.review_names(b)
            self.assertEqual(b.summary['conflicts'],2)
            b=self.prepare_names(b'Legacy,Party,Phone\na,Same Name,\na,Same Name,\n')
            with self.assertRaises(PortabilityError): self.review_names(b,ids=('a',))

    def test_new_destination_name_collision_invalidates_approval(self):
        with self.scoped():
            b=self.review_names(self.prepare_names())
            Party.objects.create(workspace=self.a,display_name='Same Name',party_type='INDIVIDUAL')
            with self.assertRaises(PortabilityError): self.commit_names(b)
            self.assertEqual(Party.objects.count(),1)

    def test_changed_values_require_new_review_and_decisions_cannot_be_presets(self):
        with self.scoped():
            b=self.review_names(self.prepare_names())
            with self.assertRaises(PortabilityError):
                save_preset(workspace_id=self.a.pk,actor=self.actor,batch_id=b.public_id,name='Reusable',approval_digest=b.approval_digest)
            mapping=deepcopy(b.mapping)
            mapping['defaults']['relation_name']='Changed source mapping'
            b=services.validate_import(workspace_id=self.a.pk,actor=self.actor,batch_id=b.public_id,mapping=mapping)
            self.assertEqual(b.summary['rows_with_errors'],2)

    def test_name_review_checks_actor_workspace_stale_approval_and_reason(self):
        with self.scoped():
            b=self.prepare_names()
            with self.assertRaises(PermissionDenied): self.review_names(b,actor=self.other_actor)
            with self.assertRaises(PortabilityError): self.review_names(b,approval_digest='old')
            with self.assertRaises(PortabilityError): self.review_names(b,reason='')
        with self.scoped(self.b):
            with self.assertRaises(PermissionDenied): self.review_names(b,workspace_id=self.b.pk)
