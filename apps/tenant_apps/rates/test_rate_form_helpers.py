from django.test import SimpleTestCase

from apps.tenant_apps.rates.forms import RateForm, RateSourceForm


def layout_text(layout):
    values = []

    def visit(node):
        values.append(str(getattr(node, "html", "")))
        values.append(str(getattr(node, "value", "")))
        values.append(str(getattr(node, "name", "")))
        for child in getattr(node, "fields", []):
            visit(child)

    visit(layout)
    return " ".join(values)


class RateFormHelperTests(SimpleTestCase):
    def test_rate_form_uses_crispy_helper_layout(self):
        form = RateForm()
        text = layout_text(form.helper.layout)

        self.assertEqual(form.helper.form_method, "post")
        self.assertIn("Save Rate", text)
        self.assertIn("Add rate source", text)

    def test_rate_source_form_uses_crispy_helper_layout(self):
        form = RateSourceForm()
        text = layout_text(form.helper.layout)

        self.assertEqual(form.helper.form_method, "post")
        self.assertIn("Save Source", text)
        self.assertIn("Rate source", text)
