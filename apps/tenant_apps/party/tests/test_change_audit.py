from unittest.mock import patch
from apps.orgs.audit import AuditLog
from apps.tenant_apps.data_portability.tests.fixtures import PortabilityFixture
from apps.tenant_apps.party.forms import PartyContactMethodForm, PartyAddressForm
from apps.tenant_apps.party.models import Party, PartyContactMethod, PartyAddress
from apps.tenant_apps.party.services.contact_details import save_contact_form, save_address_form, delete_contact, delete_address


class PartyDefaultAuditTests(PortabilityFixture):
    def test_contact_promotion_demotion_and_deletion_have_actor_and_no_contact_values(self):
        with self.scoped():
            party=Party.objects.create(display_name='Fictional borrower')
            old=PartyContactMethod.objects.create(party=party,contact_type='PHONE',value='+919876543210',is_primary=True)
            form=PartyContactMethodForm({'contact_type':'PHONE','value':'+919876543211','is_primary':'on'})
            self.assertTrue(form.is_valid(),form.errors)
            new=save_contact_form(form,party,actor=self.actor)
            old.refresh_from_db();self.assertFalse(old.is_primary)
            logs=AuditLog.objects.filter(company=self.a,data__operation='PARTY_DEFAULT_CHANGE')
            self.assertEqual(logs.count(),2)
            self.assertEqual(set(logs.values_list('user_id',flat=True)),{self.actor.pk})
            self.assertNotIn('+919876',str(list(logs.values_list('data',flat=True))))
            delete_contact(party=party,contact_id=new.pk,actor=self.actor)
            self.assertEqual(logs.count(),3)

    def test_address_audit_failure_rolls_back_both_default_changes(self):
        with self.scoped():
            party=Party.objects.create(display_name='Fictional borrower')
            old=PartyAddress.objects.create(party=party,address_type='HOME',line1='1 First Street',city='Town',is_default=True)
            form=PartyAddressForm({'address_type':'HOME','line1':'2 Second Street','city':'Town','country':'IN','is_default':'on'})
            self.assertTrue(form.is_valid(),form.errors)
            with patch('apps.tenant_apps.party.services.contact_details.AuditLog.log',side_effect=RuntimeError('audit failed')):
                with self.assertRaises(RuntimeError):save_address_form(form,party,actor=self.actor)
            old.refresh_from_db();self.assertTrue(old.is_default)
            self.assertEqual(PartyAddress.objects.count(),1)

    def test_address_promotion_and_deletion_are_object_linked(self):
        with self.scoped():
            party=Party.objects.create(display_name='Fictional borrower')
            old=PartyAddress.objects.create(party=party,address_type='HOME',line1='1 First Street',city='Town',is_default=True)
            form=PartyAddressForm({'address_type':'HOME','line1':'2 Second Street','city':'Town','country':'IN','is_default':'on'})
            self.assertTrue(form.is_valid(),form.errors)
            new=save_address_form(form,party,actor=self.actor)
            self.assertEqual(AuditLog.objects.filter(object_id=old.pk,content_type__model='partyaddress',data__after=False,user=self.actor).count(),1)
            delete_address(party=party,address_id=new.pk,actor=self.actor)
            self.assertTrue(AuditLog.objects.filter(object_id=new.pk,data__after=None,user=self.actor).exists())
