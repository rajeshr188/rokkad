from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.bulk_operations import (
    BulkLoanOperationError,
    LoanBulkDeleteCommand,
    LoanBulkOperationService,
    LoanMergeCommand,
    parse_selected_ids,
)


class _ExistsResult:
    def __init__(self, exists):
        self._exists = exists

    def exists(self):
        return self._exists


class _FakeLoanQuerySet:
    def __init__(self, loans, *, released=False, closed=False):
        self.loans = list(loans)
        self.released = released
        self.closed = closed
        self.delete_called = False

    def count(self):
        return len(self.loans)

    def earliest(self, _field_name):
        return self.loans[0]

    def values_list(self, field_name, flat=False):
        return [getattr(loan, field_name) for loan in self.loans]

    def filter(self, *args, **kwargs):
        if "status" in kwargs:
            return _ExistsResult(self.closed)
        return _ExistsResult(self.released or self.closed)

    def exclude(self, **kwargs):
        excluded_id = kwargs["id"]
        return _FakeLoanQuerySet(
            [loan for loan in self.loans if loan.id != excluded_id],
            released=self.released,
            closed=self.closed,
        )

    def delete(self):
        self.delete_called = True

    def __iter__(self):
        return iter(self.loans)


class LoanBulkOperationServiceTests(SimpleTestCase):
    def test_parse_selected_ids_deduplicates_and_counts_invalid_tokens(self):
        ids, invalid_count = parse_selected_ids(["2", "bad", "2", "0", "5"])

        self.assertEqual(ids, [2, 5])
        self.assertEqual(invalid_count, 2)

    @patch("apps.tenant_apps.girvi.service_modules.bulk_operations.LoanMergeService")
    @patch("apps.tenant_apps.girvi.service_modules.bulk_operations._get_given_loan_model")
    @patch("apps.tenant_apps.girvi.service_modules.bulk_operations._loan_lifecycle_state")
    def test_merge_given_loans_validates_and_delegates_to_merge_service(
        self,
        mock_lifecycle_state,
        mock_get_given_loan_model,
        mock_merge_service,
    ):
        loans = [
            SimpleNamespace(id=1, borrower_id=10),
            SimpleNamespace(id=2, borrower_id=10),
            SimpleNamespace(id=3, borrower_id=10),
        ]
        qs = _FakeLoanQuerySet(loans)
        mock_lifecycle_state.return_value = SimpleNamespace(CLOSED="Closed")
        mock_given_loan = MagicMock()
        mock_get_given_loan_model.return_value = mock_given_loan
        mock_given_loan.objects.filter.return_value = qs

        result = LoanBulkOperationService.merge_given_loans(
            LoanMergeCommand(raw_ids=["1", "2", "3"], loan_kind="given", merged_by="user")
        )

        self.assertEqual(result.target_loan, loans[0])
        self.assertEqual(result.merged_count, 2)
        mock_merge_service.assert_called_once_with(target_loan=loans[0], merged_by="user")
        mock_merge_service.return_value.merge.assert_called_once_with(
            source_loans=[loans[1], loans[2]]
        )

    @patch("apps.tenant_apps.girvi.service_modules.bulk_operations._get_given_loan_model")
    def test_merge_rejects_different_borrowers(self, mock_get_given_loan_model):
        mock_given_loan = MagicMock()
        mock_get_given_loan_model.return_value = mock_given_loan
        mock_given_loan.objects.filter.return_value = _FakeLoanQuerySet(
            [
                SimpleNamespace(id=1, borrower_id=10),
                SimpleNamespace(id=2, borrower_id=11),
            ]
        )

        with self.assertRaises(BulkLoanOperationError) as ctx:
            LoanBulkOperationService.merge_given_loans(
                LoanMergeCommand(raw_ids=["1", "2"], loan_kind="given", merged_by="user")
            )

        self.assertEqual(ctx.exception.message, "Selected loans must belong to the same borrower")

    @patch("apps.tenant_apps.girvi.service_modules.bulk_operations._get_given_loan_model")
    def test_delete_given_loans_rejects_released_records(self, mock_get_given_loan_model):
        mock_given_loan = MagicMock()
        mock_get_given_loan_model.return_value = mock_given_loan
        mock_given_loan.objects.filter.return_value = _FakeLoanQuerySet(
            [SimpleNamespace(id=1)],
            released=True,
        )

        with self.assertRaises(BulkLoanOperationError) as ctx:
            LoanBulkOperationService.delete_selected_loans(
                LoanBulkDeleteCommand(raw_ids=["1"], loan_kind="given")
            )

        self.assertEqual(ctx.exception.message, "Cannot bulk delete released given loans")

    @patch("apps.tenant_apps.girvi.service_modules.bulk_operations._taken_loan_lifecycle_state")
    @patch("apps.tenant_apps.girvi.service_modules.bulk_operations._get_taken_loan_model")
    def test_delete_taken_loans_deletes_valid_selection(
        self,
        mock_get_taken_loan_model,
        mock_lifecycle_state,
    ):
        qs = _FakeLoanQuerySet([SimpleNamespace(id=1), SimpleNamespace(id=2)])
        mock_lifecycle_state.return_value = SimpleNamespace(CLOSED="Closed")
        mock_taken_loan = MagicMock()
        mock_get_taken_loan_model.return_value = mock_taken_loan
        mock_taken_loan.objects.filter.return_value = qs

        result = LoanBulkOperationService.delete_selected_loans(
            LoanBulkDeleteCommand(raw_ids=["1", "2"], loan_kind="taken")
        )

        self.assertEqual(result.deleted_count, 2)
        self.assertEqual(result.loan_kind, "taken")
        self.assertTrue(qs.delete_called)

    def test_delete_all_tab_is_disabled(self):
        with self.assertRaises(BulkLoanOperationError) as ctx:
            LoanBulkOperationService.delete_selected_loans(
                LoanBulkDeleteCommand(raw_ids=["1"], loan_kind="all")
            )

        self.assertEqual(
            ctx.exception.message,
            "Delete from All tab is disabled. Use Given or Taken tab.",
        )
