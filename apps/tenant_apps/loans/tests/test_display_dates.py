from datetime import date

from django import forms
from django.test import SimpleTestCase
from django.utils import formats, translation

from apps.tenant_apps.loans.documents.display import display_date


class DisplayDateTests(SimpleTestCase):
    def test_display_and_html_date_input_formats(self):
        for language in ("en-us", "en", "hi"):
            with translation.override(language):
                self.assertEqual(formats.date_format(date(2026, 9, 25)), "25/09/2026")
                html = forms.DateInput(attrs={"type": "date"}).render("date", date(2026, 9, 25))
                self.assertIn('value="2026-09-25"', html)

    def test_document_iso_dates_display_day_first(self):
        self.assertEqual(display_date("2026-09-25"), "25/09/2026")
        self.assertEqual(display_date("C07548"), "C07548")
        self.assertEqual(display_date("2026-99-25"), "2026-99-25")
