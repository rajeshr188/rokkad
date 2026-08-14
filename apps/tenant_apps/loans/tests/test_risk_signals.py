from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.tenant_apps.loans import risk_signals
from apps.tenant_apps.rates.models import Rate


class RiskSignalScopeTests(SimpleTestCase):
    def test_supported_rate_invalidates_only_matching_metal_and_later_snapshots(self):
        rate = SimpleNamespace(
            pk=None,
            metal=Rate.Metal.GOLD,
            currency=Rate.Currency.INR,
            purity=Rate.Purity.K24,
            timestamp=datetime(2026, 8, 13, 10, tzinfo=timezone.utc),
        )
        queryset = Mock()
        queryset.update.return_value = 2

        with patch.object(
            risk_signals.transaction, "on_commit", side_effect=lambda callback: callback()
        ), patch.object(
            risk_signals.LoanRiskSnapshot.objects, "filter", return_value=queryset
        ) as filtered:
            risk_signals._mark_rate_change(Rate, rate)

        query = filtered.call_args.args[0]
        self.assertIn(("loan__collateral_items__metal", "GOLD"), query.children)
        self.assertIn(
            ("as_of_date__gte", datetime(2026, 8, 13).date()), query.children
        )
        queryset.update.assert_called_once()

    def test_irrelevant_currency_or_purity_does_not_invalidate_snapshots(self):
        rate = SimpleNamespace(
            pk=None,
            metal=Rate.Metal.GOLD,
            currency=Rate.Currency.USD,
            purity=Rate.Purity.K24,
            timestamp=datetime(2026, 8, 13, 10, tzinfo=timezone.utc),
        )
        with patch.object(
            risk_signals.transaction, "on_commit", side_effect=lambda callback: callback()
        ), patch.object(risk_signals.LoanRiskSnapshot.objects, "filter") as filtered:
            risk_signals._mark_rate_change(Rate, rate)

        filtered.assert_not_called()

