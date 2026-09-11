from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.loans.web.appraisal import AppraisalSuggestionForm, collateral_appraisal_suggestion


class AppraisalSuggestionTests(SimpleTestCase):
    def data(self, **changes):
        data = dict(metal="GOLD", gross_weight="10", net_weight="9", purity="90", as_of="2026-09-09", request_key="1")
        data.update(changes)
        return data

    @patch("apps.tenant_apps.loans.access._resolve_loans_access")
    @patch("apps.tenant_apps.loans.web.appraisal.get_latest_commodity_valuation_rate")
    def test_suggestion_uses_net_weight_and_purity(self, lookup, access):
        policy = SimpleNamespace(can=lambda action: True, require=lambda action: None)
        workspace = SimpleNamespace(pk=1)
        access.return_value = workspace, policy
        request = RequestFactory().get("/suggestion/", self.data())
        request.user = SimpleNamespace(is_authenticated=True)
        request.loans_workspace_access = policy
        lookup.return_value = SimpleNamespace(status="FOUND", rate=SimpleNamespace(buying_rate=Decimal("7000"), effective_at=datetime(2026, 9, 9)))
        response = collateral_appraisal_suggestion(request)
        self.assertContains(response, 'data-value="56700.00"')
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(lookup.call_args.kwargs["purity"], "24k")
        lookup.return_value = SimpleNamespace(status="MISSING_RATE", rate=None)
        self.assertContains(collateral_appraisal_suggestion(request), "No usable INR pure-metal buying price per gram")

    def test_invalid_dimensions_and_nonfinite_numbers_are_rejected(self):
        for change in ({"net_weight": "11"}, {"purity": "101"}, {"gross_weight": "NaN"}, {"net_weight": "-1"}, {"as_of": "bad"}):
            with self.subTest(change=change):
                data = self.data()
                data.update(change)
                self.assertFalse(AppraisalSuggestionForm(data).is_valid())
