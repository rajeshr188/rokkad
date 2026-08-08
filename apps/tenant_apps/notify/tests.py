from contextlib import nullcontext
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.http import HttpResponseRedirect
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.girvi.views.notice import create_loan_notification
from apps.tenant_apps.notify.models import (
    NoticeGroup,
    NoticeTypeConfig,
    Notification,
    NotificationTemplate,
)
from apps.tenant_apps.notify.services import (
    DEFAULT_LOAN_REMINDER_CODE,
    create_bulk_loan_reminder_group,
    create_loan_reminder_notification,
)
from apps.tenant_apps.notify_v2.models import NotificationChannel
from apps.tenant_apps.notify.views import (
    noticegroup_detail,
    noticegroup_print,
    notification_print,
)


class LoanReminderIntegrationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True)
        self.anon_user = SimpleNamespace(is_authenticated=False)

    def _build_loan(self, *, pk=1, loan_id="GL-001", borrower=None, amount="1000.00"):
        borrower = borrower or SimpleNamespace(pk=11, name="Asha")
        return SimpleNamespace(
            pk=pk,
            loan_id=loan_id,
            borrower=borrower,
            get_loan_amount=Decimal(amount),
            loan_date=timezone.make_aware(datetime(2026, 1, 10, 10, 0, 0)),
            tenure=3,
        )

    @patch(
        "apps.tenant_apps.notify.services.transaction.atomic",
        side_effect=lambda: nullcontext(),
    )
    @patch("apps.tenant_apps.notify.services.Notification.objects.create")
    @patch("apps.tenant_apps.notify.services.NoticeTypeConfig.objects.filter")
    def test_create_loan_reminder_notification_adds_items_and_generates_message(
        self,
        mock_notice_type_filter,
        mock_notification_create,
        _mock_atomic,
    ):
        notice_type_config = SimpleNamespace(code=DEFAULT_LOAN_REMINDER_CODE, name="First Reminder")
        mock_notice_type_filter.return_value.first.return_value = notice_type_config
        notification = MagicMock()
        mock_notification_create.return_value = notification

        borrower = SimpleNamespace(pk=21, name="Kiran")
        loan = self._build_loan(borrower=borrower)

        result = create_loan_reminder_notification(
            customer=borrower,
            loans=[loan],
            medium_type=Notification.MediumType.Letter,
        )

        self.assertEqual(result, notification)
        mock_notification_create.assert_called_once_with(
            group=None,
            customer=borrower,
            medium_type=Notification.MediumType.Letter,
            notice_type=Notification.NoticeType.First_Reminder,
            notice_type_config=notice_type_config,
            status=Notification.StatusType.Draft,
        )
        notification.add_item.assert_called_once()
        self.assertEqual(notification.add_item.call_args.kwargs["reference_number"], "GL-001")
        self.assertEqual(notification.add_item.call_args.kwargs["amount"], Decimal("1000.00"))
        notification.generate_message.assert_called_once_with()
        notification.save.assert_called_once()

    @patch("apps.tenant_apps.notify.services.create_loan_reminder_notification")
    @patch("apps.tenant_apps.notify.services.NoticeGroup.objects.create")
    def test_create_bulk_loan_reminder_group_groups_by_borrower(
        self,
        mock_group_create,
        mock_create_notification,
    ):
        group = SimpleNamespace(name="Loan reminders")
        mock_group_create.return_value = group

        borrower_a = SimpleNamespace(pk=1, name="Asha")
        borrower_b = SimpleNamespace(pk=2, name="Bina")
        loans = [
            self._build_loan(pk=1, loan_id="GL-001", borrower=borrower_a),
            self._build_loan(pk=2, loan_id="GL-002", borrower=borrower_a),
            self._build_loan(pk=3, loan_id="GL-003", borrower=borrower_b),
        ]

        result = create_bulk_loan_reminder_group(loans)

        self.assertEqual(result, group)
        self.assertEqual(mock_create_notification.call_count, 2)
        first_call = mock_create_notification.call_args_list[0].kwargs
        second_call = mock_create_notification.call_args_list[1].kwargs
        self.assertEqual(first_call["customer"], borrower_a)
        self.assertEqual(len(first_call["loans"]), 2)
        self.assertEqual(second_call["customer"], borrower_b)
        self.assertEqual(len(second_call["loans"]), 1)

    @patch(
        "apps.tenant_apps.notify.services.transaction.atomic",
        side_effect=lambda: nullcontext(),
    )
    @patch("apps.tenant_apps.notify.services.Notification.objects.create")
    @patch("apps.tenant_apps.notify.services.NoticeTypeConfig.objects.filter")
    def test_create_loan_reminder_notification_creates_email_copy_when_customer_has_email(
        self,
        mock_notice_type_filter,
        mock_notification_create,
        _mock_atomic,
    ):
        notice_type_config = SimpleNamespace(code=DEFAULT_LOAN_REMINDER_CODE, name="First Reminder")
        mock_notice_type_filter.return_value.first.return_value = notice_type_config
        primary_notification = MagicMock(name="letter_notification")
        email_notification = MagicMock(name="email_notification")
        mock_notification_create.side_effect = [primary_notification, email_notification]

        borrower = SimpleNamespace(pk=21, name="Kiran", email="kiran@example.com")
        loan = self._build_loan(borrower=borrower)

        result = create_loan_reminder_notification(
            customer=borrower,
            loans=[loan],
            medium_type=Notification.MediumType.Letter,
        )

        self.assertEqual(result, primary_notification)
        self.assertEqual(mock_notification_create.call_count, 2)
        self.assertEqual(
            mock_notification_create.call_args_list[0].kwargs["medium_type"],
            Notification.MediumType.Letter,
        )
        self.assertEqual(
            mock_notification_create.call_args_list[1].kwargs["medium_type"],
            Notification.MediumType.Email,
        )
        email_notification.send_notification.assert_called_once_with()

    @patch(
        "apps.tenant_apps.notify.services.transaction.atomic",
        side_effect=lambda: nullcontext(),
    )
    @patch("apps.tenant_apps.notify.services.Notification.objects.create")
    @patch("apps.tenant_apps.notify.services.NoticeTypeConfig.objects.filter")
    def test_create_loan_reminder_notification_excludes_email_copy_from_group(
        self,
        mock_notice_type_filter,
        mock_notification_create,
        _mock_atomic,
    ):
        notice_type_config = SimpleNamespace(code=DEFAULT_LOAN_REMINDER_CODE, name="First Reminder")
        mock_notice_type_filter.return_value.first.return_value = notice_type_config
        primary_notification = MagicMock(name="letter_notification")
        email_notification = MagicMock(name="email_notification")
        mock_notification_create.side_effect = [primary_notification, email_notification]

        borrower = SimpleNamespace(pk=21, name="Kiran", email="kiran@example.com")
        loan = self._build_loan(borrower=borrower)
        group = NoticeGroup(name="Loan reminders")

        create_loan_reminder_notification(
            customer=borrower,
            loans=[loan],
            medium_type=Notification.MediumType.Letter,
            group=group,
        )

        self.assertIs(mock_notification_create.call_args_list[0].kwargs["group"], group)
        self.assertIsNone(mock_notification_create.call_args_list[1].kwargs["group"])

    @patch("apps.tenant_apps.notify.models.Notification.update_status")
    @patch("apps.tenant_apps.notify.models.send_mail")
    def test_notification_send_email_uses_customer_email(
        self,
        mock_send_mail,
        mock_update_status,
    ):
        notification = Notification(
            medium_type=Notification.MediumType.Email,
            message="Reminder body",
        )
        notification.customer = Customer(firstname="Kiran", email="kiran@example.com")
        notification.notice_type_config = NoticeTypeConfig(
            code="LOAN_FIRST_REMINDER",
            name="First Reminder",
            category=NoticeTypeConfig.CategoryChoices.LOAN,
            email_subject_template="Reminder for {{customer.name}}",
        )
        notification.notice_type = Notification.NoticeType.First_Reminder
        notification._build_template_context = MagicMock(
            return_value={"customer": notification.customer}
        )

        sent = notification.send_email()

        self.assertTrue(sent)
        mock_send_mail.assert_called_once_with(
            "Reminder for Kiran",
            "Reminder body",
            settings.DEFAULT_FROM_EMAIL,
            ["kiran@example.com"],
            fail_silently=False,
        )
        mock_update_status.assert_called_once_with(Notification.StatusType.Sent)

    @patch("apps.tenant_apps.girvi.views.notice.create_girvi_reminder_batch")
    @patch("apps.tenant_apps.girvi.views.notice.get_object_or_404")
    def test_create_loan_notification_view_uses_real_reminder_service(
        self,
        mock_get_object_or_404,
        mock_create_batch,
    ):
        loan = self._build_loan()
        mock_get_object_or_404.return_value = loan
        mock_create_batch.return_value = SimpleNamespace(
            batch=SimpleNamespace(get_absolute_url=lambda: "/notify/notification/1/")
        )

        request = self.factory.get(
            "/girvi/loan/1/notify/?notice_code=LOAN_FINAL_NOTICE&medium_type=S"
        )
        request.user = self.user

        response = create_loan_notification.__wrapped__(request, pk=1)

        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, "/notify/notification/1/")
        mock_create_batch.assert_called_once_with(
            loans=[loan],
            created_by=self.user,
            event_key="loan.final_notice_due",
            channel=NotificationChannel.SMS,
            notes="Created from single-loan notice entrypoint.",
        )

    @patch("apps.tenant_apps.notify.models.NotificationTemplate.resolve_for")
    def test_get_renderer_type_defaults_to_pdf_for_letters(self, mock_resolve_template):
        mock_resolve_template.return_value = None

        notification = Notification(medium_type=Notification.MediumType.Letter)

        self.assertEqual(
            notification.get_renderer_type(),
            NotificationTemplate.RendererType.PDF,
        )

    @patch("apps.tenant_apps.notify.models.NotificationTemplate.resolve_for")
    def test_generate_message_uses_notification_template_override(self, mock_resolve_template):
        template = MagicMock(renderer=NotificationTemplate.RendererType.DJANGO)
        template.render.return_value = "Custom rendered reminder"
        mock_resolve_template.return_value = template

        notification = Notification(medium_type=Notification.MediumType.Email)
        notification.customer = Customer(firstname="Kiran", email="kiran@example.com")
        notification.notice_type_config = NoticeTypeConfig(
            code="LOAN_FIRST_REMINDER",
            name="First Reminder",
            category=NoticeTypeConfig.CategoryChoices.LOAN,
        )
        notification.notice_type = Notification.NoticeType.First_Reminder

        notification.generate_message()

        self.assertEqual(notification.message, "Custom rendered reminder")
        template.render.assert_called_once_with(notification)

    @patch("apps.tenant_apps.notify.models.get_notice_pdf", return_value=b"%PDF-1.4 notice")
    @patch("apps.tenant_apps.notify.models.NotificationTemplate.resolve_for")
    def test_print_letter_uses_pdf_renderer_and_template_key(
        self,
        mock_resolve_template,
        mock_get_notice_pdf,
    ):
        mock_resolve_template.return_value = SimpleNamespace(
            renderer=NotificationTemplate.RendererType.PDF,
            pdf_template_key="loan_notice_v1",
        )

        notification = Notification(medium_type=Notification.MediumType.Letter)
        notification.customer = Customer(firstname="Kiran")
        notification.notice_type_config = NoticeTypeConfig(
            code="LOAN_FIRST_REMINDER",
            name="First Reminder",
            category=NoticeTypeConfig.CategoryChoices.LOAN,
        )
        notification.get_printable_items = MagicMock(
            return_value=[SimpleNamespace(loan_id="GL-001")]
        )
        notification.save = MagicMock()

        pdf = notification.print_letter()

        self.assertEqual(pdf, b"%PDF-1.4 notice")
        mock_get_notice_pdf.assert_called_once_with(
            selection=[SimpleNamespace(loan_id="GL-001")],
            template_key="loan_notice_v1",
        )

    @patch("apps.tenant_apps.notify.views.ContentType.objects.get_for_model")
    @patch("apps.tenant_apps.notify.views.get_object_or_404")
    @patch("apps.tenant_apps.notify.views.GivenLoan")
    def test_noticegroup_detail_counts_given_loan_items(
        self,
        mock_given_loan,
        mock_get_object_or_404,
        mock_get_content_type,
    ):
        request = self.factory.get("/notify/noticegroup/3/")
        request.user = self.user

        notifications_qs = MagicMock(name="notifications_qs")
        items_qs = MagicMock(name="items_qs")
        ng = SimpleNamespace(
            pk=3,
            name="Loan reminders",
            notifications=SimpleNamespace(all=MagicMock(return_value=notifications_qs)),
        )
        mock_get_object_or_404.return_value = ng
        notifications_qs.prefetch_related.return_value = items_qs
        items_qs.select_related.return_value = items_qs
        printable_items = MagicMock(name="printable_items")
        items_qs.filter.return_value = printable_items
        printable_items.values_list.return_value = [1, 2]
        mock_get_content_type.return_value = SimpleNamespace(pk=7)

        released_filter = MagicMock(name="released_filter")
        borrower_values = MagicMock(name="borrower_values")
        borrower_distinct = MagicMock(name="borrower_distinct")
        mock_given_loan.objects.filter.return_value = released_filter
        released_filter.distinct.return_value = released_filter
        released_filter.count.return_value = 2
        released_filter.values.return_value = borrower_values
        borrower_values.distinct.return_value = borrower_distinct
        borrower_distinct.count.return_value = 1

        response = noticegroup_detail.__wrapped__(request, pk=3)

        notifications_qs.prefetch_related.assert_called_once_with("items__content_type")
        self.assertEqual(response.context_data["loans"], 2)
        self.assertEqual(response.context_data["customers"], 1)

    @patch("apps.tenant_apps.notify.models.get_notice_pdf", return_value=b"%PDF-1.4 notice")
    def test_notice_group_print_notice_skips_non_printable_and_deduplicates(self, mock_get_notice_pdf):
        printable_notification = MagicMock()
        printable_notification.get_renderer_type.return_value = NotificationTemplate.RendererType.PDF
        printable_notification.get_printable_items.return_value = [
            SimpleNamespace(
                pk=1,
                loan_id="GL-001",
                borrower=SimpleNamespace(pk=10),
                _meta=SimpleNamespace(label_lower="girvi.givenloan"),
            )
        ]
        printable_notification.get_selected_template.return_value = SimpleNamespace(
            pdf_template_key="loan_notice_v1"
        )

        duplicate_printable_notification = MagicMock()
        duplicate_printable_notification.get_renderer_type.return_value = NotificationTemplate.RendererType.PDF
        duplicate_printable_notification.get_printable_items.return_value = [
            SimpleNamespace(
                pk=1,
                loan_id="GL-001",
                borrower=SimpleNamespace(pk=10),
                _meta=SimpleNamespace(label_lower="girvi.givenloan"),
            )
        ]
        duplicate_printable_notification.get_selected_template.return_value = SimpleNamespace(
            pdf_template_key="loan_notice_v1"
        )

        email_notification = MagicMock()
        email_notification.get_renderer_type.return_value = NotificationTemplate.RendererType.DJANGO

        notifications = [printable_notification, duplicate_printable_notification, email_notification]
        group = SimpleNamespace(
            notifications=SimpleNamespace(
            select_related=MagicMock(
                return_value=SimpleNamespace(prefetch_related=MagicMock(return_value=notifications))
            )
            )
        )

        pdf = NoticeGroup.print_notice(group)

        self.assertEqual(pdf, b"%PDF-1.4 notice")
        mock_get_notice_pdf.assert_called_once()
        self.assertEqual(len(mock_get_notice_pdf.call_args.kwargs["selection"]), 1)
        self.assertEqual(
            mock_get_notice_pdf.call_args.kwargs["template_key"],
            "loan_notice_v1",
        )
        email_notification.get_printable_items.assert_not_called()

    def test_noticegroup_print_requires_login(self):
        request = self.factory.get("/notify/noticegroup/1/print")
        request.user = self.anon_user

        response = noticegroup_print(request, pk=1)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)

    def test_notification_print_requires_login(self):
        request = self.factory.get("/notify/notification/1/print")
        request.user = self.anon_user

        response = notification_print(request, pk=1)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
