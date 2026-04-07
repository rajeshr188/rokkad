from contextlib import nullcontext
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.conf import settings
from django.http import HttpResponseRedirect
from django.test import RequestFactory, SimpleTestCase
from django.utils import timezone

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.girvi.views.notice import create_loan_notification
from apps.tenant_apps.notify.models import NoticeTypeConfig, Notification
from apps.tenant_apps.notify.services import (
    DEFAULT_LOAN_REMINDER_CODE,
    create_bulk_loan_reminder_group,
    create_loan_reminder_notification,
)


class LoanReminderIntegrationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True)

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
        notification.loans.set.assert_called_once_with([loan])
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

    @patch("apps.tenant_apps.girvi.views.notice.create_loan_reminder_notification")
    @patch("apps.tenant_apps.girvi.views.notice.get_object_or_404")
    def test_create_loan_notification_view_uses_real_reminder_service(
        self,
        mock_get_object_or_404,
        mock_create_reminder,
    ):
        loan = self._build_loan()
        mock_get_object_or_404.return_value = loan
        mock_create_reminder.return_value = SimpleNamespace(
            get_absolute_url=lambda: "/notify/notification/1/"
        )

        request = self.factory.get(
            "/girvi/loan/1/notify/?notice_code=LOAN_FINAL_NOTICE&medium_type=S"
        )
        request.user = self.user

        response = create_loan_notification.__wrapped__(request, pk=1)

        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, "/notify/notification/1/")
        mock_create_reminder.assert_called_once_with(
            customer=loan.borrower,
            loans=[loan],
            notice_code="LOAN_FINAL_NOTICE",
            medium_type=Notification.MediumType.SMS,
        )
