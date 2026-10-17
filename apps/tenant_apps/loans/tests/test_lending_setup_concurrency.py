"""Current entry preference confirmations serialize and retry once."""

from datetime import date
from django.db import connections
from django.test import TransactionTestCase
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.economic_policy_reviews import (
    preview_economic_change,
    confirm_economic_change,
)
from . import test_economic_policy_review_concurrency as fixtures


class EntryPreferenceConcurrencyTests(TransactionTestCase):
    setUp = fixtures.EconomicReviewConcurrencyTests.setUp
    race = fixtures.EconomicReviewConcurrencyTests.race

    def submission(self, purpose):
        from django.utils import timezone

        args = dict(
            workspace=self.workspace,
            actor=self.actor,
            kind="entry",
            values=dict(purpose=purpose, effective_from=timezone.localdate()),
        )
        with workspace_context(self.workspace.pk):
            _, token = preview_economic_change(**args)
        return args | dict(token=token, acknowledged=True)

    def test_identical_preference_confirmation_is_once_only(self):
        values = self.submission("PAPER")
        results = self.race([values, values])
        self.assertEqual(sorted(row["already_saved"] for row in results), [False, True])
        self.assertEqual(results[0]["policy_ids"], results[1]["policy_ids"])
        with workspace_context(self.workspace.pk):
            self.assertEqual(m.LoanEntryPreference.objects.count(), 1)
            self.assertFalse(m.PawnLoanEconomicPolicy.objects.exists())
            self.assertFalse(m.PawnMetalInterestRatePolicy.objects.exists())

    def test_competing_preferences_require_fresh_review(self):
        results = self.race([self.submission("PAPER"), self.submission("DIRECT")])
        self.assertEqual(sum(row is not None for row in results), 1)
        with workspace_context(self.workspace.pk):
            self.assertEqual(m.LoanEntryPreference.objects.count(), 1)
