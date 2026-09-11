import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connections
from django.test import TransactionTestCase
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenant_apps.rates.models import Rate, RateSource
from apps.tenant_apps.rates.services import record_quote


class QuoteConcurrencyTests(TransactionTestCase):
    def test_two_corrections_append_only_one_successor(self):
        suffix = uuid.uuid4().hex[:10]
        actor = get_user_model().objects.create_user(username=f"quote-race-{suffix}")
        workspace = Company.objects.create(name="Quote race", schema_name=f"quote-race-{suffix}", owner=actor, creator=actor)
        Membership.objects.create(user=actor, company=workspace, role=Role.objects.get_or_create(name="Owner")[0])
        with workspace_context(workspace.pk):
            source = RateSource.objects.create(name="Market", location="Local")
            values = dict(rate_source=source, metal="Gold", currency="INR", purity="24k", buying_rate=10, selling_rate=11, effective_at=timezone.now())
            original = record_quote(workspace=workspace, actor=actor, values=values)
        barrier = Barrier(2)

        def correct(amount):
            try:
                barrier.wait(timeout=10)
                with workspace_context(workspace.pk):
                    result = record_quote(workspace=workspace, actor=actor, supersedes_id=original.pk,
                                          values={**values, "buying_rate": amount, "reason": "Correct amount"})
                    return result.pk
            except ValidationError:
                return None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(correct, (12, 13)))
        self.assertEqual(sum(result is not None for result in results), 1)
        with workspace_context(workspace.pk):
            self.assertEqual(Rate.objects.filter(supersedes=original).count(), 1)
            original.refresh_from_db()
            self.assertEqual(original.buying_rate, 10)
