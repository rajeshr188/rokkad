"""Bulk loan operation orchestration for Girvi views."""

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db.models import Q

from apps.tenant_apps.girvi.service_modules.split_merge import LoanMergeService


class BulkLoanOperationError(Exception):
    def __init__(self, message, *, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class LoanMergeCommand:
    raw_ids: list
    loan_kind: str
    merged_by: object


@dataclass
class LoanMergeResult:
    target_loan: object
    merged_count: int


@dataclass
class LoanBulkDeleteCommand:
    raw_ids: list
    loan_kind: str


@dataclass
class LoanBulkDeleteResult:
    deleted_count: int
    loan_kind: str


def parse_selected_ids(raw_ids):
    """Return cleaned integer IDs and count of invalid tokens."""
    cleaned = []
    invalid_count = 0
    for raw_id in raw_ids:
        try:
            parsed = int(raw_id)
            if parsed > 0:
                cleaned.append(parsed)
            else:
                invalid_count += 1
        except (TypeError, ValueError):
            invalid_count += 1
    return list(dict.fromkeys(cleaned)), invalid_count


def _get_given_loan_model():
    from apps.tenant_apps.girvi.models import GivenLoan

    return GivenLoan


def _get_taken_loan_model():
    from apps.tenant_apps.girvi.models import TakenLoan

    return TakenLoan


def _loan_lifecycle_state():
    from apps.tenant_apps.girvi.models import LoanLifecycleState

    return LoanLifecycleState


def _taken_loan_lifecycle_state():
    from apps.tenant_apps.girvi.models import TakenLoanLifecycleState

    return TakenLoanLifecycleState


class LoanBulkOperationService:
    @classmethod
    def merge_given_loans(cls, command: LoanMergeCommand) -> LoanMergeResult:
        if command.loan_kind != "given":
            raise BulkLoanOperationError("Merge is available only for Given loans")

        loan_ids, invalid_count = parse_selected_ids(command.raw_ids)
        if invalid_count:
            raise BulkLoanOperationError("Invalid loan selection.")

        if len(loan_ids) < 2:
            raise BulkLoanOperationError("Please select at least 2 loans to merge")

        given_loan_model = _get_given_loan_model()
        loan_lifecycle_state = _loan_lifecycle_state()
        loans = given_loan_model.objects.filter(id__in=loan_ids)
        loan_count = loans.count()
        if loan_count != len(loan_ids):
            raise BulkLoanOperationError("Some selected loans no longer exist")

        if loan_count < 2:
            raise BulkLoanOperationError("Please select at least 2 loans to merge")

        base_loan = loans.earliest("loan_date")
        borrowers = set(loans.values_list("borrower_id", flat=True))
        if len(borrowers) > 1:
            raise BulkLoanOperationError("Selected loans must belong to the same borrower")

        if loans.filter(
            Q(release__isnull=False) | Q(status=loan_lifecycle_state.CLOSED)
        ).exists():
            raise BulkLoanOperationError("Cannot merge released loans")

        loans_to_merge = list(loans.exclude(id=base_loan.id))

        try:
            LoanMergeService(target_loan=base_loan, merged_by=command.merged_by).merge(
                source_loans=loans_to_merge
            )
        except ValidationError as exc:
            raise BulkLoanOperationError(str(exc)) from exc

        return LoanMergeResult(target_loan=base_loan, merged_count=len(loans_to_merge))

    @classmethod
    def delete_selected_loans(
        cls, command: LoanBulkDeleteCommand
    ) -> LoanBulkDeleteResult:
        loan_ids, invalid_count = parse_selected_ids(command.raw_ids)
        if invalid_count:
            raise BulkLoanOperationError("Invalid loan selection.")

        if not loan_ids:
            raise BulkLoanOperationError("Please select at least one loan to delete.")

        if command.loan_kind == "taken":
            taken_loan_model = _get_taken_loan_model()
            taken_loan_lifecycle_state = _taken_loan_lifecycle_state()
            loans = taken_loan_model.objects.filter(id__in=loan_ids)
            if loans.count() != len(loan_ids):
                raise BulkLoanOperationError("Some selected taken loans no longer exist")
            if loans.filter(status=taken_loan_lifecycle_state.CLOSED).exists():
                raise BulkLoanOperationError("Cannot bulk delete released taken loans")
        elif command.loan_kind == "all":
            raise BulkLoanOperationError(
                "Delete from All tab is disabled. Use Given or Taken tab."
            )
        else:
            given_loan_model = _get_given_loan_model()
            loans = given_loan_model.objects.filter(id__in=loan_ids)
            if loans.count() != len(loan_ids):
                raise BulkLoanOperationError("Some selected given loans no longer exist")
            if loans.filter(release__isnull=False).exists():
                raise BulkLoanOperationError("Cannot bulk delete released given loans")

        deleted_count = loans.count()
        loans.delete()
        return LoanBulkDeleteResult(
            deleted_count=deleted_count,
            loan_kind=command.loan_kind,
        )
