from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.dea.services.pre_close import CheckResult, PreCloseChecklist


class PreCloseRetirementBoundaryTests(SimpleTestCase):
    def test_checklist_contains_only_dea_owned_checks(self):
        result = CheckResult(
            key="placeholder",
            label="Placeholder",
            status="pass",
            is_fatal=False,
            count=0,
            status_text="Ready",
        )
        checklist = PreCloseChecklist()
        methods = (
            "_unposted_vouchers_check",
            "_unreconciled_bank_items_check",
            "_depreciation_posted_check",
            "_prepaid_expired_check",
            "_balance_sheet_trial_check",
        )
        patches = [patch.object(checklist, method, return_value=result) for method in methods]
        mocks = [item.start() for item in patches]
        self.addCleanup(lambda: [item.stop() for item in reversed(patches)])

        rows = checklist.run(period=object())

        self.assertEqual(len(rows), len(methods))
        self.assertFalse(hasattr(checklist, "_interest_accrual_check"))
        for mock in mocks:
            mock.assert_called_once()
