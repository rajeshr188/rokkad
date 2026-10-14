"""One bounded explicit-Workspace turn; no trial mutation or historical replay."""
from datetime import datetime, timedelta

from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.utils import timezone

from apps.orgs.models import Company
from apps.subscriptions.access_policy import workspace_activity
from apps.subscriptions.models import Subscription, SubscriptionEvent
from apps.tenancy.checks import check_restricted_runtime_role
from apps.tenancy.context import current_workspace_id, workspace_context
from .intents import _capture, _target, _trial_facts
from .models import Delivery, TrialReminder
from .controls import ZONE


def reminder_current(workspace, event, end, *, at):
    sub = event.subscription
    activity = workspace_activity(workspace, at=at)
    days = (end.astimezone(ZONE).date() - at.astimezone(ZONE).date()).days
    return (workspace.lifecycle_state == "ACTIVE" and sub.company_id == workspace.pk and sub.status == "trial"
        and sub.trial_end_date == end and end > at and 1 <= days <= 3 and activity.mode == "full"
        and activity.grant is None and activity.subscription and activity.subscription.pk == sub.pk)


def reminder_facts(reminder):
    facts = _trial_facts(reminder.trial_event)
    return {**facts, "reminder_id": reminder.pk, "workspace_id": reminder.workspace_id,
        "stage": reminder.stage, "trial_end": reminder.trial_end.isoformat(),
        "recorded_at": reminder.created_at.isoformat()}


def queue_trial_reminder(*, workspace_id):
    if (type(workspace_id) is not int or workspace_id <= 0 or connection.in_atomic_block
        or current_workspace_id() is not None or check_restricted_runtime_role(None, databases=["default"])):
        raise PermissionDenied("An explicit Workspace and standalone restricted runtime are required.")
    with transaction.atomic(durable=True), workspace_context(workspace_id):
        workspace = Company.all_objects.select_for_update().select_related("owner").get(pk=workspace_id)
        sub = Subscription.objects.select_for_update().filter(company=workspace).first()
        if not sub or sub.status != "trial" or not sub.trial_end_date:
            return None
        event = SubscriptionEvent.objects.filter(subscription=sub, event_type="trial.started").order_by("-pk").first()
        if not event:
            return None
        facts = _trial_facts(event)
        end = datetime.fromisoformat(facts["trial_end"])
        now = timezone.now()
        if sub.trial_end_date != end or not reminder_current(workspace, event, end, at=now):
            return None
        target = _target(workspace, "subscription", at=now, lock=True)
        if not target:
            return None
        existing = TrialReminder.objects.filter(trial_event=event).first()
        if existing:
            saved = Delivery.objects.get(reminder=existing)
            return saved if (saved.contact_id == target[0].pk and saved.contact_revision == target[0].revision
                and saved.consent_id == target[1].pk and saved.owner_id == workspace.owner_id) else None
        source = TrialReminder.objects.create(workspace=workspace, trial_event=event, trial_end=end, created_at=now)
        return _capture(workspace=workspace, contact=target[0], consent=target[1], purpose=Delivery.Purpose.ENDING,
            facts=reminder_facts(source), source_recorded_at=now, reminder=source,
            expiry=min(end, now+timedelta(days=1)))
