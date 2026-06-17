from pathlib import Path

from django.test import SimpleTestCase


class RateSourceSetupUITests(SimpleTestCase):
    def template(self, name):
        return Path("templates/rates", name).read_text(encoding="utf-8")

    def test_rate_list_links_to_rate_source_setup(self):
        content = self.template("rate_list.html")

        self.assertIn("Add Source", content)
        self.assertIn("No rate source exists yet", content)
        self.assertIn("ratesource_create", content)

    def test_rate_create_guides_user_to_add_rate_source(self):
        content = self.template("rate_form.html")

        self.assertIn("A rate source is required", content)
        self.assertIn("ratesource_create", content)

    def test_rate_source_list_has_create_action(self):
        content = self.template("ratesource_list.html")

        self.assertIn("Add Source", content)
        self.assertIn("No rate sources yet", content)
