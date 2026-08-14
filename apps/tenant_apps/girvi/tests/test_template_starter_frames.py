from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.models.template import TemplateFrame
from apps.tenant_apps.girvi.views.template import _starter_frame_blueprint


class TemplateStarterFrameBlueprintTests(SimpleTestCase):
    def test_starter_frame_blueprint_matches_standard_17_frame_layout_without_label(self):
        template_obj = SimpleNamespace(name="custom_template", page_width=14.8, page_height=21.0)

        frames = _starter_frame_blueprint(template_obj)
        by_name = {frame["frame_name"]: frame for frame in frames}

        self.assertEqual(len(frames), 17)
        self.assertNotIn("label", by_name)

        expected_positioned = {
            "amount_words": ("text", 7.20, 6.00, 6.50, 1.00),
            "amount": ("text", 2.70, 6.00, 3.00, 1.00),
            "value": ("text", 11.00, 7.00, 2.50, 1.00),
            "weight": ("text", 2.50, 7.00, 7.00, 1.00),
            "loanitem_pic": ("image", 11.00, 8.00, 2.00, 2.00),
            "loan_desc": ("text", 1.00, 8.00, 10.00, 4.00),
            "loan_qr": ("qr", 10.00, 11.20, 1.80, 1.80),
            "loan_date": ("text", 10.00, 14.20, 3.50, 1.00),
            "loan_id": ("text", 10.00, 15.00, 3.50, 1.00),
            "customer_info": ("text", 4.00, 13.00, 6.00, 3.00),
            "customer_pic": ("image", 1.00, 11.00, 2.50, 2.50),
            "license_no": ("text", 11.00, 18.60, 3.00, 1.00),
        }

        for frame_name, (field_type, x_pos, y_pos, width, height) in expected_positioned.items():
            frame = by_name[frame_name]
            self.assertEqual(frame["template_type"], TemplateFrame.TemplateType.BOTH)
            self.assertEqual(frame["field_type"], field_type)
            self.assertEqual(frame["x_pos"], x_pos)
            self.assertEqual(frame["y_pos"], y_pos)
            self.assertEqual(frame["width"], width)
            self.assertEqual(frame["height"], height)
            self.assertEqual(frame["font_name"], "Helvetica")
            self.assertEqual(frame["show_boundary"], 1)

        for frame_name in [
            "license_name",
            "license_address",
            "license_propreitor",
            "customer_name",
            "pure",
        ]:
            self.assertIn(frame_name, by_name)
