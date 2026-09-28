"""Upgrade from the deployed billing schema in Django's disposable test database."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from apps.orgs.models import Company
from .models import (Invoice, Payment, Plan, RecurringAccessResolution, RecurringAgreement,
                     RecurringAgreementEvent, RecurringCycle, RecurringPlanBinding,
                     Subscription, SubscriptionEntitlement, WorkspaceAccessDecision)


class PausedReleaseMigrationTests(TransactionTestCase):
    def test_upgrade_preserves_existing_trials_entitlements_and_access_without_backfill(self):
        before = [("subscriptions", "0011_access_decision_evidence_guard")]
        after = [("subscriptions", "0017_recurring_access_resolution")]
        executor = MigrationExecutor(connection)
        executor.migrate(before)
        try:
            old_apps = executor.loader.project_state(before).apps
            old_plan = old_apps.get_model("subscriptions", "Plan")
            old_subscription = old_apps.get_model("subscriptions", "Subscription")
            plan = old_plan.objects.create(name="Existing offer", tier="starter", price="500.00",
                yearly_price=None, max_users=9, trial_days=14)
            owner = get_user_model().objects.create_user(username="billing-upgrade-fixture")
            now = timezone.now()
            for index in range(3):
                workspace = Company.all_objects.create(name=f"Upgrade fixture {index}",
                    schema_name=f"billing_upgrade_{index}", owner=owner, creator=owner)
                sub = old_subscription.objects.create(company_id=workspace.pk, plan=plan,
                    status="trial", start_date=now-timedelta(days=5), end_date=now+timedelta(days=9),
                    trial_end_date=now+timedelta(days=9), auto_renew=False)
                SubscriptionEntitlement.objects.create(subscription_id=sub.pk,
                    feature_code="workspace.max_members", value="9", source="plan")
                WorkspaceAccessDecision.objects.create(workspace=workspace, actor=owner,
                    mode="full", expires_at=now+timedelta(days=30), reason="Existing operator access")
            models = (Plan, Subscription, SubscriptionEntitlement, WorkspaceAccessDecision)
            snapshots = {model: list(model.objects.order_by("pk").values()) for model in models}
            executor = MigrationExecutor(connection)
            pending = [(m.app_label, m.name) for m, backwards in executor.migration_plan(after)]
            self.assertEqual([app for app, name in pending], ["subscriptions"]*6)
            self.assertEqual([name[:4] for app, name in pending], [f"{n:04d}" for n in range(12,18)])
        finally:
            # Restore the schema even if a seed/assertion fails, before test DB cleanup.
            MigrationExecutor(connection).migrate(after)
        for model, snapshot in snapshots.items():
            self.assertEqual(list(model.objects.order_by("pk").values()), snapshot, model.__name__)
        for model in (Invoice, Payment, RecurringPlanBinding, RecurringAgreement,
                      RecurringAgreementEvent, RecurringCycle, RecurringAccessResolution):
            self.assertFalse(model.objects.exists(), model.__name__)
        self.assertFalse(MigrationExecutor(connection).migration_plan(after))
