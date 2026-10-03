from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from phonenumber_field.formfields import PhoneNumberField

from apps.tenant_apps.party.forms import PartyForm, PartyContactMethodForm, normalize_phone_number
from apps.tenant_apps.party.phone_numbers import PartyPhoneNumberField, display_phone
from apps.tenant_apps.party.templatetags.party_phone import contact_display


class PhoneNumberTests(SimpleTestCase):
    def test_library_field_accepts_local_and_international_formats(self):
        for raw, expected in (
            ('9876543210', '+919876543210'),
            ('+91 98765 43210', '+919876543210'),
            ('0416 222 1234', '+914162221234'),
            ('+44 20 7946 0018', '+442079460018'),
            ('+1 (202) 555-0123', '+12025550123'),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_phone_number(raw), expected)
        self.assertIsInstance(PartyForm().fields['primary_phone'], PhoneNumberField)
        self.assertEqual(normalize_phone_number(''), '')

    def test_invalid_numbers_and_notes_are_not_silently_rewritten(self):
        for raw in ('123', '0000000000', 'phone 9876543210', '+1 800 FLOWERS',
                    '9876543210 / 9123456789', '+91 9876543210 ext 123', '+999 123456789'):
            with self.subTest(raw=raw), self.assertRaises(ValidationError):
                normalize_phone_number(raw)

    def test_widget_and_display_format_valid_values_preserving_legacy_input(self):
        field = PartyPhoneNumberField(required=False)
        self.assertEqual(field.widget.format_value('+919876543210'), '+91 98765 43210')
        self.assertEqual(field.widget.format_value('9876543210'), '+91 98765 43210')
        for raw in ('not supplied', '12345', '98765 / 43210'):
            self.assertEqual(display_phone(raw), raw)
            self.assertEqual(field.widget.format_value(raw), raw)
        self.assertEqual(display_phone(''), '')

    def test_mixed_contacts_use_phone_field_only_for_phone_types(self):
        for kind in ('PHONE', 'MOBILE', 'WHATSAPP'):
            form = PartyContactMethodForm(data={'contact_type': kind, 'value': '9876543210'})
            self.assertIsInstance(form.fields['value'], PhoneNumberField)
            self.assertEqual(form.fields['value'].clean('9876543210').as_e164, '+919876543210')
        for kind, value in (('EMAIL', 'a@example.com'), ('WEBSITE', 'https://example.com'), ('OTHER', '9876543210')):
            form = PartyContactMethodForm(data={'contact_type': kind, 'value': value})
            self.assertNotIsInstance(form.fields['value'], PhoneNumberField)
            self.assertEqual(contact_display(SimpleNamespace(contact_type=kind, value=value)), value)
        self.assertEqual(contact_display(SimpleNamespace(contact_type='MOBILE', value='9876543210')), '+91 98765 43210')

    def test_prefixed_and_invalid_contact_types_do_not_bypass_selection(self):
        form = PartyContactMethodForm(prefix='contact', data={'contact-contact_type': 'MOBILE', 'contact-value': '123'})
        self.assertIsInstance(form.fields['value'], PhoneNumberField)
        with self.assertRaises(ValidationError):
            form.fields['value'].clean('123')
        form = PartyContactMethodForm(data={'contact_type': 'INVALID', 'value': '123'})
        with self.assertRaises(ValidationError):
            form.fields['contact_type'].clean('INVALID')
