from types import SimpleNamespace
from unittest.mock import patch

from django import forms
from django.test import SimpleTestCase

from apps.tenant_apps.loans.web.pawn_draft_actions import _pawn_number_preview_context


class SelectedNumberPreviewTests(SimpleTestCase):
    def form(self, data=None, initial=None):
        form = forms.Form(data=data, initial=initial)
        field = forms.ChoiceField(choices=[("1", "A"), ("2", "B")])
        field.queryset = [SimpleNamespace(pk=1), SimpleNamespace(pk=2)]
        form.fields["series"] = field
        return form

    def preview(self, series, kind):
        return {"value": "A-00001"} if series.pk == 1 else {"error": "Series exhausted"}

    @patch("apps.tenant_apps.loans.web.pawn_draft_actions._safe_preview")
    def test_initial_bound_empty_and_invalid_selection(self, preview):
        preview.side_effect = self.preview
        cases = [
            (self.form(initial={"series": "1"}), {"value": "A-00001"}),
            (self.form(data={"series": "2"}, initial={"series": "1"}), {"error": "Series exhausted"}),
            (self.form(data={"series": ""}), None),
            (self.form(data={"series": "999"}), None),
        ]
        for form, expected in cases:
            with self.subTest(selected=form["series"].value()):
                context = _pawn_number_preview_context(form)
                self.assertEqual(context["selected_number_preview"], expected)
                self.assertEqual(set(context["number_previews"]), {"1", "2"})
