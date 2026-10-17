"""Two confirmations serialize on the same ordinary Workspace policy lock."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.economic_policy_reviews import (
    preview_economic_change,
    confirm_economic_change,
)


class EconomicReviewConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(
            username="economic-review-race-" + uuid4().hex
        )
        self.workspace = Company.objects.create(
            name="Configuration concurrency",
            schema_name=uuid4().hex,
            owner=self.actor,
            creator=self.actor,
        )
        Membership.objects.create(
            user=self.actor,
            company=self.workspace,
            role=Role.objects.get_or_create(name="Owner")[0],
        )
        self.values = dict(
            valuation_method="LATEST_APPRAISAL",
            maximum_ltv_ratio=Decimal(".8"),
            gold_monthly_interest_rate=Decimal("1.1"),
            silver_monthly_interest_rate=Decimal("3"),
            effective_from=date(2026, 10, 17),
        )

    def submission(self, **changes):
        args = dict(
            workspace=self.workspace,
            actor=self.actor,
            kind="configuration",
            values=self.values | changes,
        )
        with workspace_context(self.workspace.pk):
            _, token = preview_economic_change(**args)
        return args | dict(token=token, acknowledged=True)

    def race(self, submissions):
        ready = Barrier(2)

        def submit(values):
            try:
                ready.wait(timeout=15)
                with workspace_context(self.workspace.pk):
                    return confirm_economic_change(**values)
            except ValueError:
                return None
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as workers:
            return list(workers.map(submit, submissions))

    def test_identical_confirmation_writes_one_configuration(self):
        args = self.submission()
        results = self.race([args, args])
        self.assertEqual(results[0]["policy_ids"], results[1]["policy_ids"])
        self.assertEqual(sorted(row["already_saved"] for row in results), [False, True])
        with workspace_context(self.workspace.pk):
            self.assertEqual(m.PawnLoanEconomicPolicy.objects.count(), 1)
            self.assertEqual(m.PawnMetalInterestRatePolicy.objects.count(), 2)

    def test_competing_different_reviews_cannot_both_append_from_stale_setup(self):
        results = self.race(
            [self.submission(), self.submission(maximum_ltv_ratio=Decimal(".7"))]
        )
        self.assertEqual(sum(row is not None for row in results), 1)
        with workspace_context(self.workspace.pk):
            self.assertEqual(m.PawnLoanEconomicPolicy.objects.count(), 1)
