"""
Refactored Loan Models - Addressing Critical Design Issues

Key Changes:
1. BaseLoan as abstract parent with shared fields
2. GivenLoan and TakenLoan with distinct semantic fields
3. Redundant fields removed - replaced with properties
4. Cleaner separation of concerns
5. Removed conditional loan_type logic

Migration Strategy:
- Keep original loan.py intact initially
- Test this new structure
- Create data migration to split existing Loan records
- Switch imports gradually
"""

import logging
import re
from decimal import Decimal

from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Func, Sum
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from moneyed import Money

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import BusinessDoc, JournalEntry
from apps.tenant_apps.girvi.models.custody_tracking import (
    GivenLoanReleaseMixin,
    TakenLoanCollateralMixin,
)
from ..managers_refactored import GivenLoanManager, TakenLoanManager

logger = logging.getLogger(__name__)


class LoanStatus(models.TextChoices):
    """Loan lifecycle status"""

    CREATED = "Created", "Created"
    APPROVED = "Approved", "Approved"
    REJECTED = "Rejected", "Rejected"
    DISBURSED = "Disbursed", "Disbursed"
    CLOSED = "Closed", "Closed"
    RELEASED = "Released", "Released"
    REPLEDGED = "Repledged", "Repledged"
    SOLD = "Sold", "Sold"
    DEFAULTED = "Defaulted", "Defaulted"
    AUCTIONED = "Auctioned", "Auctioned"
    CANCELLED = "Cancelled", "Cancelled"


class InterestType(models.TextChoices):
    """Interest calculation method"""

    SIMPLE = "Simple", "Simple"
    COMPOUND = "Compound", "Compound"


# ============================================================================
# Base Loan Model
# ============================================================================


class BaseLoan(BusinessDoc):
    """
    Abstract base class for all loan types.
    Contains shared fields and common behavior.

    All redundant calculated fields have been removed and replaced with @property methods.
    """

    # Core identification - globally unique formatted ID
    loan_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Globally unique loan ID with series prefix (e.g., 'A00123')",
    )

    # Series is mandatory - every loan must belong to a series
    series = models.ForeignKey(
        "girvi.Series",
        on_delete=models.PROTECT,
        verbose_name="Series",
        help_text="Series - determines loan ID prefix and sequence (required)",
    )

    # Dates and timing
    loan_date = models.DateTimeField(
        default=timezone.now, db_index=True, verbose_name=_("Loan Date")
    )
    tenure = models.PositiveIntegerField(default=3, help_text="Loan tenure in months")

    # Status
    status = models.CharField(
        max_length=20,
        choices=LoanStatus.choices,
        default=LoanStatus.CREATED,
        db_index=True,
    )

    # Interest configuration
    interest_type = models.CharField(
        max_length=10, choices=InterestType.choices, default=InterestType.SIMPLE
    )

    class Meta:
        abstract = True
        ordering = ("loan_id",)  # Natural alphabetical ordering
        get_latest_by = "id"
        indexes = [
            models.Index(fields=["status", "loan_date"]),
            models.Index(fields=["loan_date", "status"]),
            models.Index(fields=["series", "loan_id"]),
        ]
        permissions = [
            ("can_approve_loan", "Can approve loan"),
            ("can_disburse_loan", "Can disburse loan"),
            ("can_release_loan", "Can release loan"),
            ("can_cancel_loan", "Can cancel loan"),
            ("can_mark_defaulted", "Can mark loan as defaulted"),
            ("can_mark_auctioned", "Can mark loan as auctioned"),
            ("can_mark_sold", "Can mark loan as sold"),
        ]

    def __str__(self):
        return f"{self.loan_id} - ₹{self.get_loan_amount} - {self.loan_date.date()}"

    @property
    def license(self):
        """Get license through series relationship."""
        return self.series.license if self.series else None

    def save(self, *args, **kwargs):
        """
        Override save to auto-generate loan_id if not provided.
        Uses unified LoanIDGenerator for thread-safe generation.
        """
        from ..services import LoanIDGenerator

        # Only generate if this is a new loan (no pk) and loan_id not set
        if not self.pk and not self.loan_id:
            if not self.series:
                raise ValueError("Series is required to create a loan")

            # Generate formatted loan ID using series
            self.loan_id = LoanIDGenerator.generate(self.series)

        super().save(*args, **kwargs)

    @property
    def get_next(self):
        """Return the next loan in the same series for this concrete loan type."""
        return (
            self.__class__.objects.filter(series=self.series, loan_id__gt=self.loan_id)
            .order_by("loan_id")
            .first()
        )

    @property
    def get_previous(self):
        """Return the previous loan in the same series for this concrete loan type."""
        return (
            self.__class__.objects.filter(series=self.series, loan_id__lt=self.loan_id)
            .order_by("loan_id")
            .last()
        )

    # ========================================================================
    # Abstract methods - must be implemented by subclasses
    # ========================================================================

    @property
    def get_loan_amount(self) -> Decimal:
        """Calculate total loan amount from items. Must be implemented by subclass."""
        raise NotImplementedError("Subclass must implement get_loan_amount")

    @property
    def get_interest_amount(self) -> Decimal:
        """Calculate base interest amount. Must be implemented by subclass."""
        raise NotImplementedError("Subclass must implement get_interest_amount")

    @property
    def get_weight_summary(self) -> dict:
        """Get weight breakdown by metal type. Must be implemented by subclass."""
        raise NotImplementedError("Subclass must implement get_weight_summary")

    @property
    def get_item_description(self) -> str:
        """Get comma-separated item descriptions. Must be implemented by subclass."""
        raise NotImplementedError("Subclass must implement get_item_description")

    # ========================================================================
    # Common calculated properties (work across all loan types)
    # ========================================================================

    @property
    def is_released(self) -> bool:
        """Check if loan has been released."""
        return hasattr(self, "release")

    @property
    def is_overdue(self) -> bool:
        """Check if loan is overdue (defaulted or auctioned status)."""
        return self.status in [LoanStatus.DEFAULTED, LoanStatus.AUCTIONED]

    @property
    def months_elapsed(self) -> int:
        """Calculate months since loan was created."""
        from ..services import InterestCalculationService

        return InterestCalculationService.months_between(self.loan_date)

    def interest_due(self, as_of_date=None) -> Decimal:
        """
        Calculate total interest due as of a specific date.

        Args:
            as_of_date: Calculate interest up to this date (default: today)

        Returns:
            Total interest amount due
        """
        from ..services import InterestCalculationService

        months = InterestCalculationService.months_between(self.loan_date, as_of_date)
        return round(self.get_interest_amount * months, 2)

    @property
    def total_due(self) -> Decimal:
        """Total amount due including principal and interest."""
        return self.get_loan_amount + self.interest_due()

    @property
    def total_due_with_currency(self):
        """Total due as Money object."""
        return Money(self.total_due, "INR")

    def get_total_payments(self) -> Decimal:
        """Sum of all payments made on this loan."""
        return self.loan_payments.aggregate(Sum("payment_amount"))[
            "payment_amount__sum"
        ] or Decimal(0)

    def get_total_principal_payments(self) -> Decimal:
        """Sum of principal payments."""
        return self.loan_payments.aggregate(Sum("principal_payment"))[
            "principal_payment__sum"
        ] or Decimal(0)

    def get_total_interest_payments(self) -> Decimal:
        """Sum of interest payments."""
        return self.loan_payments.aggregate(Sum("interest_payment"))[
            "interest_payment__sum"
        ] or Decimal(0)

    @property
    def current_value(self) -> Decimal:
        """
        Current market value of collateral.
        Must be implemented by subclass since collateral structure differs.
        """
        raise NotImplementedError("Subclass must implement current_value")

    @property
    def is_underwater(self) -> bool:
        """Check if current collateral value is less than amount due."""
        try:
            return self.current_value < self.total_due
        except NotImplementedError:
            return False

    @property
    def equity(self) -> Decimal:
        """Collateral value minus amount due (can be negative)."""
        return self.current_value - self.total_due

    # ========================================================================
    # Common business methods
    # ========================================================================

    def get_absolute_url(self):
        """Detail view URL."""
        if self.__class__.__name__ == "TakenLoan":
            return reverse(
                "girvi:taken_loan_collateral_detail", kwargs={"loan_id": self.pk}
            )
        return reverse("girvi:girvi_loan_detail", args=(self.pk,))

    def get_update_url(self):
        """Update view URL."""
        return reverse("girvi:girvi_loan_update", args=(self.pk,))

    @classmethod
    def validate_loan_id(cls, loan_id: str, series_prefix: str) -> bool:
        """Validate loan ID format matches series pattern."""
        pattern = f"^{re.escape(series_prefix)}\\d+$"
        return bool(re.match(pattern, loan_id))

    def create_release(self, release_date, released_by, created_by):
        """Create a release document for this loan via the lifecycle service."""
        from ..services import ReleaseLifecycleService

        return ReleaseLifecycleService.create_release(
            loan=self,
            release_date=release_date,
            released_by=released_by,
            created_by=created_by,
        )

    def get_status_history(self):
        """Get complete status change history."""
        return self.loanchangelog_set.all().order_by("-changed")


# ============================================================================
# Concrete Loan Types with Distinct Fields
# ============================================================================


class GivenLoan(BaseLoan, GivenLoanReleaseMixin):

    def create_release_payment(
        self,
        principal=None,
        interest=None,
        payment_date=None,
        payment_method="CASH",
        reference_number="",
        description="",
        created_by=None,
    ):
        """
        Create a PaymentVoucher for releasing this loan (cash in on closure).
        Ensures direction is 'RECEIPT', payment_type is 'RECEIPT', and principal/interest are set.
        """
        from decimal import Decimal
        from moneyed import Money
        from apps.tenant_apps.dea.models import PaymentVoucher

        if not created_by:
            raise ValidationError("created_by user is required")

        # Compute principal and interest if not provided
        if principal is None:
            principal = self.outstanding_principal
        if interest is None:
            interest = self.interest_due()
        if isinstance(principal, Decimal):
            principal = Money(principal, "INR")
        elif not isinstance(principal, Money):
            principal = Money(Decimal(str(principal)), "INR")
        if isinstance(interest, Decimal):
            interest = Money(interest, "INR")
        elif not isinstance(interest, Money):
            interest = Money(Decimal(str(interest)), "INR")

        total = principal + interest

        payment = PaymentVoucher.objects.create(
            source_document=self,
            total_amount=total,
            principal_amount=principal,
            interest_amount=interest,
            direction="RECEIPT",  # Cash in
            payment_type="RECEIPT",
            payment_method=payment_method,
            reference_number=reference_number,
            description=description,
            payment_date=payment_date or timezone.now(),
            created_by=created_by,
            updated_by=created_by,
        )
        return payment

        
    """
    Loan given TO a customer (pawn/pledge loan).

    Semantics:
    - We are the lender
    - Customer is the borrower
    - Customer provides collateral and receives money
    - Items tracked via LoanItem

    Key Fields:
    - borrower: The customer receiving the loan
    """

    borrower = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="loans_received",
        verbose_name="Borrower",
        help_text="Customer receiving this loan",
    )

    # Override series from BaseLoan with explicit related_name
    series = models.ForeignKey(
        "girvi.Series",
        on_delete=models.PROTECT,
        verbose_name="Series",
        help_text="Series - determines loan ID prefix and sequence (required)",
        related_name="given_loans",
    )

    # Generic relation to PaymentVouchers
    payments = GenericRelation(
        "dea.PaymentVoucher",
        content_type_field="source_content_type",
        object_id_field="source_object_id",
        related_query_name="given_loans",
    )

    objects = GivenLoanManager()

    @property
    def loan_type(self) -> str:
        """Return loan type identifier for template compatibility."""
        return "Given"

    class Meta:
        verbose_name = "Given Loan (Pawn)"
        verbose_name_plural = "Given Loans (Pawns)"
        constraints = [
            models.UniqueConstraint(
                fields=["series", "loan_id"], name="unique_givenloan_id_per_series"
            )
        ]
        indexes = [
            models.Index(fields=["borrower", "status"]),
            models.Index(fields=["status", "loan_date"]),
        ]

    # ========================================================================
    # Implement abstract properties
    # ========================================================================

    @property
    def get_loan_amount(self) -> Decimal:
        """Sum of all loan item amounts."""
        return self.loanitems.aggregate(Sum("loanamount"))[
            "loanamount__sum"
        ] or Decimal(0)

    @property
    def get_loan_amount_with_currency(self):
        return Money(self.get_loan_amount, "INR")

    @property
    def get_interest_amount(self) -> Decimal:
        """Sum of base interest from all items."""
        return self.loanitems.aggregate(Sum("interest"))["interest__sum"] or Decimal(0)

    @property
    def get_weight_summary(self) -> dict:
        """Weight breakdown by metal type."""
        return self.loanitems.values("itemtype").annotate(
            total_weight=Sum("weight"),
            pure_weight=Sum(
                Func(
                    ExpressionWrapper(
                        F("weight") * F("purity") / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    function="ROUND",
                    template="%(function)s(%(expressions)s, 3)",
                )
            ),
        )

    def formatted_weight(self, joiner=", ") -> str:
        """Human-readable weight string."""
        return joiner.join(
            f"{item['itemtype']} {item['total_weight']}g"
            for item in self.get_weight_summary
        )

    def formatted_pure_weight(self, joiner=", ") -> str:
        """Human-readable pure weight string."""
        return joiner.join(
            f"{item['itemtype']} {item['pure_weight']}g"
            for item in self.get_weight_summary
        )

    @property
    def get_item_description(self) -> str:
        """Comma-separated item descriptions."""
        return ", ".join(self.loanitems.values_list("itemdesc", flat=True))

    # ========================================================================
    # Table-friendly properties (for django-tables2 rendering)
    # ========================================================================

    @property
    def item_desc(self) -> str:
        """Item descriptions for table display."""
        return self.get_item_description or "—"

    @property
    def loan_amount(self) -> Decimal:
        """Loan amount (alias for get_loan_amount for table display)."""
        return self.get_loan_amount

    @property
    def total_interest(self) -> Decimal:
        """Total interest due (alias for interest_due for table display)."""
        return self.interest_due()

    @property
    def current_value(self) -> Decimal:
        """Current market value of all pledged items."""
        return sum(item.current_value() for item in self.loanitems.all())

    # ========================================================================
    # GivenLoan-specific methods
    # ========================================================================

    def can_split(self) -> bool:
        """Check if loan has multiple items that can be split."""
        return self.loanitems.count() > 1

    def split_items(self, loan_item_ids: list[int] = None, created_by=None):
        """
        Split selected loan items into separate loans.

        Delegates to LoanSplitService for clean separation of concerns.

        Args:
            loan_item_ids: IDs of items to split off (first item always stays)
            created_by: User performing the split

        Returns:
            List of newly created GivenLoan objects
        """
        from ..services import LoanSplitService

        service = LoanSplitService(loan=self, created_by=created_by or self.created_by)
        return service.split_items(item_ids=loan_item_ids)

    @classmethod
    def merge_loans(cls, target_loan, source_loans: list, merged_by=None):
        """
        Merge multiple given loans into one target loan.

        Delegates to LoanMergeService for clean separation of concerns.

        Args:
            target_loan: GivenLoan to merge into
            source_loans: List of GivenLoan objects to merge
            merged_by: User performing the merge

        Returns:
            The target loan with all items merged
        """
        from ..services import LoanMergeService

        service = LoanMergeService(
            target_loan=target_loan, merged_by=merged_by or target_loan.created_by
        )
        return service.merge(source_loans=source_loans)

    # ========================================================================
    # Payment Management (PaymentVoucher Integration)
    # ========================================================================
    def create_disbursal_payment(
        self,
        amount=None,
        payment_date=None,
        payment_method="CASH",
        reference_number="",
        description="",
        created_by=None,
    ):
        """
        Create a PaymentVoucher for disbursing this loan (cash out).
        Ensures direction is 'PAYMENT' and payment_type is 'DISBURSAL',
        so DEA posting engine uses 'GIVENLOAN_PAYMENT' as voucher type.
        """
        from decimal import Decimal
        from moneyed import Money
        from apps.tenant_apps.dea.models import PaymentVoucher

        if not created_by:
            raise ValidationError("created_by user is required")

        # Default to full loan amount if not specified
        if amount is None:
            amount = self.get_loan_amount_with_currency
        elif isinstance(amount, Decimal):
            amount = Money(amount, "INR")
        elif not isinstance(amount, Money):
            amount = Money(Decimal(str(amount)), "INR")

        payment = PaymentVoucher.objects.create(
            source_document=self,
            total_amount=amount,
            principal_amount=amount,
            direction="PAYMENT",  # Cash out
            payment_type="DISBURSAL",
            payment_method=payment_method,
            reference_number=reference_number,
            description=description,
            payment_date=payment_date or timezone.now(),
            created_by=created_by,
            updated_by=created_by,
        )
        return payment
    def create_payment(
        self,
        amount,
        payment_date=None,
        payment_method="CASH",
        reference_number="",
        interest=None,
        principal=None,
        description="",
        is_final=False,
        create_release=False,
        created_by=None,
    ):
        """
        Create a payment voucher for this loan.

        PAYMENT-CENTRIC ARCHITECTURE:
        - Only creates PaymentVoucher when cash actually moves
        - Automatically posts to accounting via posting rules
        - Handles IFRS 9 compliance (recognizes at cash transfer)

        Args:
            amount: Total payment amount (Decimal or Money)
            payment_date: When payment was made (default: now)
            payment_method: How payment was made (CASH, BANK, CHEQUE, UPI, CARD)
            reference_number: Bank reference, cheque num, etc
            interest: Interest portion (if None, uses total_amount)
            principal: Principal portion
            description: Additional notes
            is_final: Mark if this closes the loan
            create_release: If True, creates Release record after posting
            created_by: User making the payment (required)

        Returns:
            PaymentVoucher instance that has been posted to accounting
        """
        from decimal import Decimal
        from moneyed import Money
        from apps.tenant_apps.dea.models import PaymentVoucher

        if not created_by:
            raise ValidationError("created_by user is required")

        # Normalize amount to Money object
        if isinstance(amount, Decimal):
            amount = Money(amount, "INR")
        elif not isinstance(amount, Money):
            amount = Money(Decimal(str(amount)), "INR")

        # Create payment voucher
        payment = PaymentVoucher.objects.create(
            source_document=self,
            total_amount=amount,
            principal_amount=principal or amount,
            interest_amount=interest,
            direction="RECEIPT",  # We receive money
            payment_type="RECEIPT",
            payment_method=payment_method,
            reference_number=reference_number,
            description=description,
            is_final_payment=is_final,
            create_release=create_release,
            payment_date=payment_date or timezone.now(),
            created_by=created_by,
            updated_by=created_by,
        )

        return payment

    @property
    def total_received(self):
        """Total amount received from all payments."""
        from django.db.models import Sum
        from moneyed import Money

        total = self.payments.filter(direction="RECEIPT").aggregate(
            total=Sum("amount_in_base_currency")
        )["total"]

        return total or Money(0, "INR")

    @property
    def outstanding_principal(self):
        """Remaining principal balance."""
        from moneyed import Money

        principal = self.get_loan_amount_with_currency
        received = self.total_received

        if hasattr(received, "amount"):
            outstanding = principal.amount - received.amount
        else:
            outstanding = principal.amount - received

        return Money(outstanding, "INR")

    def all_payments(self):
        """Get all payments for this loan (forward compatibility)."""
        return self.payments.all().order_by("-payment_date")


class TakenLoan(BaseLoan, TakenLoanCollateralMixin):
    """
    Loan taken FROM a customer (repledge/reverse pawn).

    Semantics:
    - Customer is the lender
    - We are the borrower
    - Customer receives collateral and gives money
    - Items tracked via RepledgedLoanItem (references original LoanItem)

    Key Fields:
    - lender: The customer providing this loan
    - original_loan: The GivenLoan being repledged (optional reference)
    """

    lender = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="loans_given",
        verbose_name="Lender",
        help_text="Customer providing this loan to us",
    )

    original_loan = models.ForeignKey(
        "GivenLoan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="repledged_as",
        help_text="Original GivenLoan being repledged",
    )

    # Override series from BaseLoan with explicit related_name
    series = models.ForeignKey(
        "girvi.Series",
        on_delete=models.PROTECT,
        verbose_name="Series",
        help_text="Series - determines loan ID prefix and sequence (required)",
        related_name="taken_loans",
    )

    # Generic relation to PaymentVouchers
    payments = GenericRelation(
        "dea.PaymentVoucher",
        content_type_field="source_content_type",
        object_id_field="source_object_id",
        related_query_name="taken_loans",
    )

    objects = TakenLoanManager()

    @property
    def loan_type(self) -> str:
        """Return loan type identifier for template compatibility."""
        return "Taken"

    class Meta:
        verbose_name = "Taken Loan (Repledge)"
        verbose_name_plural = "Taken Loans (Repledges)"
        constraints = [
            models.UniqueConstraint(
                fields=["series", "loan_id"], name="unique_takenloan_id_per_series"
            )
        ]
        indexes = [
            models.Index(fields=["lender", "status"]),
            models.Index(fields=["original_loan"]),
        ]

    # ========================================================================
    # Implement abstract properties
    # ========================================================================

    @property
    def get_loan_amount(self) -> Decimal:
        """Sum of all repledged item amounts."""
        return self.repledgedloanitems.aggregate(Sum("repledged_loanamount"))[
            "repledged_loanamount__sum"
        ] or Decimal(0)

    @property
    def get_loan_amount_with_currency(self):
        return Money(self.get_loan_amount, "INR")

    @property
    def get_interest_amount(self) -> Decimal:
        """Sum of interest from repledged items."""
        return self.repledgedloanitems.aggregate(Sum("interest"))[
            "interest__sum"
        ] or Decimal(0)

    @property
    def get_weight_summary(self) -> dict:
        """Weight breakdown from original items."""
        return self.repledgedloanitems.values("original_loanitem__itemtype").annotate(
            total_weight=Sum("original_loanitem__weight"),
            pure_weight=Sum(
                Func(
                    ExpressionWrapper(
                        F("original_loanitem__weight")
                        * F("original_loanitem__purity")
                        / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    function="ROUND",
                    template="%(function)s(%(expressions)s, 3)",
                )
            ),
        )

    @property
    def get_item_description(self) -> str:
        """Descriptions from original items."""
        return ", ".join(
            self.repledgedloanitems.select_related("original_loanitem").values_list(
                "original_loanitem__itemdesc", flat=True
            )
        )

    @property
    def current_value(self) -> Decimal:
        """Current value of repledged items."""
        return sum(
            item.original_loanitem.current_value()
            for item in self.repledgedloanitems.select_related(
                "original_loanitem__item"
            ).all()
        )

    # ========================================================================
    # Payment Management (PaymentVoucher Integration)
    # ========================================================================

    def create_payment(
        self,
        amount,
        payment_date=None,
        payment_method="CASH",
        reference_number="",
        interest=None,
        principal=None,
        description="",
        is_final=False,
        created_by=None,
    ):
        """
        Create a payment voucher for repaying this loan.

        PAYMENT-CENTRIC ARCHITECTURE:
        - Only creates PaymentVoucher when cash actually moves
        - Automatically posts to accounting via posting rules
        - Handles IFRS 9 compliance

        Args:
            amount: Total payment amount (Decimal or Money)
            payment_date: When payment was made (default: now)
            payment_method: How payment was made (CASH, BANK, CHEQUE, UPI, CARD)
            reference_number: Bank reference, cheque num, etc
            interest: Interest portion (if None, uses total_amount)
            principal: Principal portion
            description: Additional notes
            is_final: Mark if this closes the loan
            created_by: User making the payment (required)

        Returns:
            PaymentVoucher instance that has been posted to accounting
        """
        from decimal import Decimal
        from moneyed import Money
        from apps.tenant_apps.dea.models import PaymentVoucher

        if not created_by:
            raise ValidationError("created_by user is required")

        # Normalize amount to Money object
        if isinstance(amount, Decimal):
            amount = Money(amount, "INR")
        elif not isinstance(amount, Money):
            amount = Money(Decimal(str(amount)), "INR")

        # Create payment voucher (we pay back the lender)
        payment = PaymentVoucher.objects.create(
            source_document=self,
            total_amount=amount,
            principal_amount=principal or amount,
            interest_amount=interest,
            direction="PAYMENT",  # We pay money
            payment_type="RECEIPT",
            payment_method=payment_method,
            reference_number=reference_number,
            description=description,
            is_final_payment=is_final,
            payment_date=payment_date or timezone.now(),
            created_by=created_by,
            updated_by=created_by,
        )

        return payment

    @property
    def total_paid(self):
        """Total amount paid back to lender."""
        from django.db.models import Sum
        from moneyed import Money

        total = self.payments.filter(direction="PAYMENT").aggregate(
            total=Sum("amount_in_base_currency")
        )["total"]

        return total or Money(0, "INR")

    @property
    def outstanding_balance(self):
        """Remaining balance to pay back."""
        from moneyed import Money

        total_due = self.get_loan_amount_with_currency
        paid = self.total_paid

        if hasattr(paid, "amount"):
            outstanding = total_due.amount - paid.amount
        else:
            outstanding = total_due.amount - paid

        return Money(outstanding, "INR")

    def all_payments(self):
        """Get all payments for this loan (forward compatibility)."""
        return self.payments.all().order_by("-payment_date")


# ============================================================================
# Helper function for data migration (loan.py -> loan_refactored.py)
# ============================================================================


def migrate_old_loan_to_new_structure(old_loan):
    """
    Migrate a Loan object from old structure to new.

    This is for the data migration script.
    """
    from .loan import Loan as OldLoan

    if not isinstance(old_loan, OldLoan):
        raise TypeError("Expected old Loan model instance")

    common_fields = {
        "loan_id": old_loan.loan_id,
        "series": old_loan.series,
        "loan_date": old_loan.loan_date,
        "tenure": old_loan.tenure,
        "status": old_loan.status,
        "interest_type": old_loan.interest_type,
        "created_by": old_loan.created_by,
        "updated_by": old_loan.updated_by,
    }

    if old_loan.loan_type == OldLoan.LoanType.GIVEN:
        new_loan = GivenLoan.objects.create(borrower=old_loan.customer, **common_fields)
        # Items automatically linked via FK

    elif old_loan.loan_type == OldLoan.LoanType.TAKEN:
        new_loan = TakenLoan.objects.create(lender=old_loan.customer, **common_fields)
        # RepledgedLoanItems automatically linked via FK

    else:
        raise ValueError(f"Unknown loan type: {old_loan.loan_type}")

    return new_loan
