from pathlib import Path

from django.test import SimpleTestCase


class LoanListBulkActionsTemplateTests(SimpleTestCase):
    def test_release_selected_targets_workspace_content(self):
        template_path = Path(__file__).resolve().parents[4] / "templates" / "girvi" / "loan" / "loan_list.html"
        content = template_path.read_text(encoding="utf-8")

        self.assertIn('hx-get="{% url \'girvi:bulk_release\' %}"', content)
        self.assertIn('hx-target="#content" hx-swap="innerHTML transition:true"', content)

    def test_loan_table_partial_exposes_expected_htmx_target(self):
        template_path = Path(__file__).resolve().parents[4] / "templates" / "girvi" / "loan" / "loan_list.html"
        content = template_path.read_text(encoding="utf-8")

        self.assertIn('<div id="table" class="table-responsive">', content)
        self.assertIn('<div id="loan-table-container">', content)
