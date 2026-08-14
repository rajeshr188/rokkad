from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.views.template import template_clone


class TemplateCloneViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=1, is_authenticated=True, username="tester")
        self.frames = [
            SimpleNamespace(
                frame_name="loan_id",
                template_type="B",
                field_type="text",
                x_pos=1,
                y_pos=1,
                width=3,
                height=1,
                font_size=10,
                font_name="Helvetica",
                show_boundary=1,
            ),
            SimpleNamespace(
                frame_name="amount",
                template_type="B",
                field_type="text",
                x_pos=2,
                y_pos=2,
                width=4,
                height=1,
                font_size=11,
                font_name="Helvetica",
                show_boundary=1,
            ),
        ]

    @patch("apps.tenant_apps.girvi.views.template.transaction.atomic")
    @patch("apps.tenant_apps.girvi.views.template.TemplateFrame")
    @patch("apps.tenant_apps.girvi.views.template.LoanTemplate.objects.create")
    @patch("apps.tenant_apps.girvi.views.template.LoanTemplate.objects.filter")
    @patch("apps.tenant_apps.girvi.views.template.get_object_or_404")
    @patch("apps.tenant_apps.girvi.views.template.messages.success")
    @patch("apps.tenant_apps.girvi.views.template._require_template_admin")
    def test_template_clone_copies_frames_and_resets_flags(
        self,
        mock_require_admin,
        mock_success,
        mock_get_object_or_404,
        mock_filter,
        mock_create,
        mock_template_frame,
        mock_atomic,
    ):
        mock_template_frame.side_effect = lambda **kwargs: SimpleNamespace(**kwargs)
        mock_atomic.return_value.__enter__.return_value = None
        mock_atomic.return_value.__exit__.return_value = False
        mock_require_admin.return_value = object()
        mock_filter.return_value.exists.return_value = False

        source_template = SimpleNamespace(
            pk=7,
            name="Gold Ticket",
            base_template=SimpleNamespace(name="base.pdf"),
            dup_template=SimpleNamespace(name="dup.pdf"),
            terms_template=None,
            form_d3_template=None,
            print_option="BS",
            page_width=14.8,
            page_height=21.0,
            templateframe_set=SimpleNamespace(all=lambda: self.frames),
        )
        cloned_template = SimpleNamespace(
            pk=8,
            name="Gold Ticket (Copy)",
            get_absolute_url=lambda: "/girvi/templates/8/",
        )
        mock_get_object_or_404.return_value = source_template
        mock_create.return_value = cloned_template

        request = self.factory.post("/girvi/templates/7/clone/")
        request.user = self.user

        response = template_clone.__wrapped__(request, pk=7)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/girvi/templates/8/")
        mock_create.assert_called_once_with(
            name="Gold Ticket (Copy)",
            base_template="base.pdf",
            dup_template="dup.pdf",
            terms_template=None,
            form_d3_template=None,
            print_option="BS",
            page_width=14.8,
            page_height=21.0,
            is_active=False,
            is_default=False,
        )
        self.assertEqual(len(mock_template_frame.objects.bulk_create.call_args.args[0]), 2)
        mock_success.assert_called_once()

    @patch("apps.tenant_apps.girvi.views.template.transaction.atomic")
    @patch("apps.tenant_apps.girvi.views.template.TemplateFrame")
    @patch("apps.tenant_apps.girvi.views.template.LoanTemplate.objects.create")
    @patch("apps.tenant_apps.girvi.views.template.LoanTemplate.objects.filter")
    @patch("apps.tenant_apps.girvi.views.template.get_object_or_404")
    @patch("apps.tenant_apps.girvi.views.template.messages.success")
    @patch("apps.tenant_apps.girvi.views.template._require_template_admin")
    def test_template_clone_uses_incremented_copy_name_when_needed(
        self,
        mock_require_admin,
        _mock_success,
        mock_get_object_or_404,
        mock_filter,
        mock_create,
        mock_template_frame,
        mock_atomic,
    ):
        mock_template_frame.side_effect = lambda **kwargs: SimpleNamespace(**kwargs)
        mock_atomic.return_value.__enter__.return_value = None
        mock_atomic.return_value.__exit__.return_value = False
        mock_require_admin.return_value = object()
        exists_responses = [MagicMock(), MagicMock()]
        exists_responses[0].exists.return_value = True
        exists_responses[1].exists.return_value = False
        mock_filter.side_effect = exists_responses

        source_template = SimpleNamespace(
            pk=7,
            name="Gold Ticket",
            base_template=None,
            dup_template=None,
            terms_template=None,
            form_d3_template=None,
            print_option="O",
            page_width=14.8,
            page_height=21.0,
            templateframe_set=SimpleNamespace(all=lambda: self.frames),
        )
        mock_get_object_or_404.return_value = source_template
        mock_create.return_value = SimpleNamespace(
            pk=9,
            name="Gold Ticket (Copy 2)",
            get_absolute_url=lambda: "/girvi/templates/9/",
        )

        request = self.factory.post("/girvi/templates/7/clone/")
        request.user = self.user

        template_clone.__wrapped__(request, pk=7)

        self.assertEqual(mock_create.call_args.kwargs["name"], "Gold Ticket (Copy 2)")
