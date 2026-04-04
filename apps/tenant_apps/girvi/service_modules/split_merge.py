from django.db import transaction


class LoanSplitService:
    """
    Service to split a GivenLoan into multiple loans by separating items.

    Business logic:
    - First item always stays with original loan
    - Remaining items can be moved to new loans
    - Each new loan inherits borrower, dates, tenure, interest_type from original
    - All operations logged in LoanChangeLog
    - Atomic transaction ensures consistency
    """

    def __init__(self, loan, created_by):
        """
        Initialize split service.

        Args:
            loan: GivenLoan instance to split
            created_by: User performing the split
        """
        from ..models import GivenLoan

        if not isinstance(loan, GivenLoan):
            raise ValueError("split_items expects GivenLoan instance")

        self.loan = loan
        self.created_by = created_by

    def split_items(self, item_ids=None):
        """
        Execute split: move selected items to new loans.

        Args:
            item_ids: List of LoanItem IDs to split off
                     If None, splits all but first item

        Returns:
            List of newly created GivenLoan objects

        Raises:
            ValidationError: If split not possible (e.g., single item loan)
        """
        self._validate_can_split()
        items_to_split = self._get_items_to_split(item_ids)
        new_loans = self._create_new_loans(items_to_split)
        return new_loans

    def _validate_can_split(self):
        """Validate that loan can be split."""
        from django.core.exceptions import ValidationError

        if not self.loan.can_split():
            raise ValidationError("Loan must have more than one item to split")

    def _get_items_to_split(self, item_ids):
        """
        Get items to split (keeping first item with original loan).

        Args:
            item_ids: Specific IDs to split, or None for all except first

        Returns:
            QuerySet of items to move to new loans
        """
        first_item = self.loan.loanitems.earliest("id")

        if item_ids:
            items = self.loan.loanitems.filter(id__in=item_ids).exclude(
                id=first_item.id
            )
        else:
            items = self.loan.loanitems.exclude(id=first_item.id)

        if not items.exists():
            from django.core.exceptions import ValidationError

            raise ValidationError("No valid items to split")

        return items

    def _create_new_loans(self, items_to_split):
        """
        Create new loans and move items.

        Args:
            items_to_split: QuerySet of items to move

        Returns:
            List of created GivenLoan objects
        """
        from ..models import GivenLoan, LoanChangeLog

        new_loans = []

        with transaction.atomic():
            for item in items_to_split:
                new_loan = GivenLoan.objects.create(
                    borrower=self.loan.borrower,
                    loan_date=self.loan.loan_date,
                    series=self.loan.series,
                    tenure=self.loan.tenure,
                    status=self.loan.status,
                    interest_type=self.loan.interest_type,
                    created_by=self.created_by,
                )

                item.loan = new_loan
                item.save(update_fields=["loan"])

                LoanChangeLog.objects.create(
                    loan=self.loan,
                    source=f"Split item {item.id}",
                    target=f"Created loan {new_loan.loan_id}",
                    author=self.created_by,
                    diff=f"Moved {item.itemdesc} to new loan",
                )

                new_loans.append(new_loan)

        return new_loans


class LoanMergeService:
    """
    Service to merge multiple GivenLoans into a single target loan.

    Business logic:
    - All loans must have same borrower
    - No released loans can be merged
    - All items moved to target loan
    - Source loans deleted (cascading delete)
    - All operations logged in LoanChangeLog
    - Atomic transaction ensures consistency
    """

    def __init__(self, target_loan, merged_by):
        """
        Initialize merge service.

        Args:
            target_loan: GivenLoan to merge into (typically oldest)
            merged_by: User performing the merge
        """
        from ..models import GivenLoan

        if not isinstance(target_loan, GivenLoan):
            raise ValueError("merge expects GivenLoan instance")

        self.target_loan = target_loan
        self.merged_by = merged_by

    def merge(self, source_loans):
        """
        Execute merge: combine multiple loans into target.

        Args:
            source_loans: List of GivenLoan objects to merge into target

        Returns:
            The target loan with all items merged

        Raises:
            ValidationError: If merge not possible (e.g., different borrower)
        """
        self._validate_can_merge(source_loans)
        self._move_items(source_loans)
        self._delete_sources(source_loans)
        return self.target_loan

    def _validate_can_merge(self, source_loans):
        """
        Validate that all loans can be merged.

        Checks:
        - All are GivenLoan instances
        - Same borrower as target
        - None are released
        - Not merging target with itself
        """
        from django.core.exceptions import ValidationError
        from ..models import GivenLoan

        for loan in source_loans:
            if not isinstance(loan, GivenLoan):
                raise ValidationError("Can only merge GivenLoan objects")

            if loan.borrower != self.target_loan.borrower:
                raise ValidationError(f"Loan {loan.loan_id} has different borrower")

            if loan.is_released:
                raise ValidationError(f"Loan {loan.loan_id} is already released")

            if loan.pk == self.target_loan.pk:
                raise ValidationError("Cannot merge loan with itself")

    def _move_items(self, source_loans):
        """Move all items from source loans to target."""
        from ..models import LoanChangeLog

        with transaction.atomic():
            for loan in source_loans:
                item_count = loan.loanitems.count()
                loan.loanitems.update(loan=self.target_loan)

                LoanChangeLog.objects.create(
                    loan=self.target_loan,
                    source=f"Merged loan {loan.loan_id}",
                    target=f"Into {self.target_loan.loan_id}",
                    author=self.merged_by,
                    diff=f"Merged {item_count} items",
                )

    def _delete_sources(self, source_loans):
        """Delete source loans after items moved."""
        with transaction.atomic():
            for loan in source_loans:
                loan.delete()
