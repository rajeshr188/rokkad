from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.printing import LoanPrintService


class LoanPrintServiceReadinessTests(SimpleTestCase):
    def _template(self, **overrides):
        defaults = {
            "pk": 1,
            "name": "Demo Template",
            "is_active": True,
            "print_option": "O",
            "base_template": None,
            "dup_template": None,
            "terms_template": None,
            "form_d3_template": None,
            "page_width": 14.8,
            "page_height": 21.0,
            "templateframe_set": SimpleNamespace(all=lambda: []),
        }
        defaults.update(overrides)
        return SimpleNamespace(**defaults)

    def test_assess_template_readiness_flags_missing_frames_as_blocking(self):
        template = self._template()

        report = LoanPrintService.assess_template_readiness(template)

        self.assertFalse(report["is_ready"])
        self.assertTrue(report["blocking_issues"])
        self.assertIn("No frames configured yet.", report["blocking_issues"])

    def test_assess_template_readiness_warns_when_back_page_assets_are_missing(self):
        frames = [SimpleNamespace(frame_name="loan_id"), SimpleNamespace(frame_name="customer_info")]
        template = self._template(
            print_option="OT",
            templateframe_set=SimpleNamespace(all=lambda: frames),
        )

        report = LoanPrintService.assess_template_readiness(template)

        self.assertTrue(report["is_ready"])
        self.assertTrue(report["warnings"])
        self.assertTrue(any("Terms PDF" in item for item in report["warnings"]))

    def test_assess_template_readiness_tracks_missing_recommended_frames(self):
        frames = [
            SimpleNamespace(frame_name="loan_id"),
            SimpleNamespace(frame_name="loan_date"),
            SimpleNamespace(frame_name="customer_info"),
            SimpleNamespace(frame_name="loan_desc"),
            SimpleNamespace(frame_name="amount"),
            SimpleNamespace(frame_name="amount_words"),
            SimpleNamespace(frame_name="loan_qr"),
        ]
        template = self._template(
            print_option="BS",
            templateframe_set=SimpleNamespace(all=lambda: frames),
        )

        report = LoanPrintService.assess_template_readiness(template)

        self.assertTrue(report["is_ready"])
        self.assertIn("Duplicate PDF", " ".join(report["warnings"]))
        self.assertEqual(report["missing_recommended_frames"], [])
