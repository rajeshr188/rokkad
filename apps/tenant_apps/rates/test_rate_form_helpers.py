from datetime import datetime
from django.test import SimpleTestCase
from django.utils import timezone, translation
from apps.tenant_apps.rates.forms import RateForm, RateSourceForm


class RateFormHelperTests(SimpleTestCase):
    def test_native_datetime_value_survives_hindi_locale(self):
        with translation.override("hi"):
            form = RateForm(initial={"effective_at": timezone.make_aware(datetime(2026, 9, 22, 10, 30))})
            self.assertIn('value="2026-09-22T10:30"', str(form["effective_at"]))

    def test_sources_only_expose_operator_fields_and_escaped_values(self):
        form = RateSourceForm(data={"name": "<script>x</script>", "location": "Market"})
        self.assertEqual(set(form.fields), {"name", "location", "tax_included"})
        self.assertIn('&lt;script&gt;', str(form["name"]))
