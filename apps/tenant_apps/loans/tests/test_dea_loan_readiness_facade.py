from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.dea.facades.loan_readiness import _ledger_by_key


class DeaLoanReadinessFacadeTests(SimpleTestCase):
    @patch("apps.tenant_apps.dea.facades.loan_readiness.Ledger.objects.filter")
    @patch(
        "apps.tenant_apps.dea.facades.loan_readiness.get_ledger_id_by_key",
        return_value=41,
    )
    def test_fee_readiness_uses_the_same_canonical_key_resolver_as_posting(
        self, resolve_key, filter_ledgers
    ):
        expected = object()
        filter_ledgers.return_value.first.return_value = expected

        result = _ledger_by_key("DOCUMENT_CHARGE_INCOME")

        self.assertIs(result, expected)
        resolve_key.assert_called_once_with("DOCUMENT_CHARGE_INCOME")
        filter_ledgers.assert_called_once_with(pk=41)

    @patch("apps.tenant_apps.dea.facades.loan_readiness.get_ledger_id_by_key")
    def test_missing_canonical_key_remains_an_actionable_readiness_blocker(
        self, resolve_key
    ):
        from django.core.exceptions import ValidationError

        resolve_key.side_effect = ValidationError("missing")

        self.assertIsNone(_ledger_by_key("DOCUMENT_CHARGE_INCOME"))

    def test_all_pawn_posting_rules_use_the_canonical_ledger_key_resolver(self):
        rule_modules = (
            "pawn_loan_disbursal",
            "pawn_loan_repayment",
            "pawn_loan_interest",
            "pawn_loan_release",
            "pawn_loan_renewal",
        )
        for module_name in rule_modules:
            target = (
                "apps.tenant_apps.dea.posting.rules."
                f"{module_name}.get_ledger_id_by_key"
            )
            module = __import__(
                f"apps.tenant_apps.dea.posting.rules.{module_name}",
                fromlist=["_ledger_id"],
            )
            with self.subTest(rule=module_name), patch(target, return_value=73) as resolver:
                self.assertEqual(module._ledger_id("DOCUMENT_CHARGE_INCOME"), 73)
                resolver.assert_called_once_with("DOCUMENT_CHARGE_INCOME")
