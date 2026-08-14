from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase
from django.utils import timezone

from apps.tenant_apps.loans.services.notice_dispatch import (
    dispatch_due_notices,
    dispatch_linked_notice,
)


class NoticeDispatchTests(SimpleTestCase):
    def test_sent_is_idempotent_and_cancelled_fails_closed(self):
        notice = SimpleNamespace(
            scheduled_for=timezone.now(), notification_job_id=7
        )
        delivery = Mock()
        sent = SimpleNamespace(status="SENT")

        receipt = dispatch_linked_notice(
            notice,
            error_type=ValueError,
            delivery_handler=delivery,
            states_loader=lambda _ids: {7: sent},
        )

        self.assertIs(receipt, sent)
        delivery.assert_not_called()

        with self.assertRaisesRegex(ValueError, "cancelled"):
            dispatch_linked_notice(
                notice,
                error_type=ValueError,
                delivery_handler=delivery,
                states_loader=lambda _ids: {7: SimpleNamespace(status="CANCELLED")},
            )

    def test_due_dispatch_is_bounded_and_counts_notify_receipts(self):
        queryset = _FakeNoticeQuerySet([(1, 11), (2, 12), (3, 13)])
        states = {
            11: SimpleNamespace(status="QUEUED"),
            12: SimpleNamespace(status="SENT"),
            13: SimpleNamespace(status="QUEUED"),
        }
        dispatch = Mock(
            side_effect=[SimpleNamespace(status="SENT"), SimpleNamespace(status="FAILED")]
        )

        summary = dispatch_due_notices(
            queryset,
            dispatch=dispatch,
            limit=2,
            states_loader=lambda _ids: states,
        )

        self.assertEqual((summary.due_count, summary.sent_count, summary.failed_count), (2, 1, 1))
        self.assertEqual([call.args[0] for call in dispatch.call_args_list], [1, 3])


class _FakeNoticeQuerySet:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, **_kwargs):
        return self

    def order_by(self, *_fields):
        return self

    def values_list(self, *_fields):
        return self.rows
