from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.tenancy.models import WorkspaceOwnedModel

from .models import (
    NotificationEvent,
    NotificationEventType,
    NotificationJob,
    NotificationRecipient,
)


class NotifyWorkspaceIsolationTests(SimpleTestCase):
    def test_event_inherits_workspace_from_its_parents(self):
        event_type = NotificationEventType(id=1, workspace_id=4, key="LOAN_DUE")
        recipient = NotificationRecipient(id=2, workspace_id=4, name_snapshot="A")
        event = NotificationEvent(event_type=event_type, recipient=recipient)

        with patch.object(WorkspaceOwnedModel, "save", autospec=True):
            event.save()

        self.assertEqual(event.workspace_id, 4)

    def test_event_rejects_parents_from_different_workspaces(self):
        event = NotificationEvent(
            event_type=NotificationEventType(id=1, workspace_id=4, key="LOAN_DUE"),
            recipient=NotificationRecipient(id=2, workspace_id=5, name_snapshot="A"),
        )

        with self.assertRaises(ValidationError):
            event.save()

    def test_job_rejects_explicit_workspace_conflict(self):
        event = NotificationEvent(id=1, workspace_id=4)
        job = NotificationJob(
            workspace_id=5,
            event=event,
            channel=NotificationJob.Channel.EMAIL,
        )

        with self.assertRaises(ValidationError):
            job.save()
