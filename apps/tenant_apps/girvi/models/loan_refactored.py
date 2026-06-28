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
from django.core.exceptions import FieldDoesNotExist, ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Func, Sum, Value
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from moneyed import Money

from django.contrib.auth import get_user_model

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.girvi.models.custody_tracking import (
    GivenLoanReleaseMixin,
    TakenLoanCollateralMixin,
)
from ..managers_refactored import GivenLoanManager, TakenLoanManager

User = get_user_model()
logger = logging.getLogger(__name__)


def _party_from_customer(customer):
    if not customer:
        return None
    party_id = getattr(customer, "party_id", None)
    return customer.party if party_id else None


class LoanStatus(models.TextChoices):
    """Legacy loan lifecycle status used by the current production flow."""

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


class LoanLifecycleState(models.TextChoices):
    """Deterministic lifecycle states for the next-generation GivenLoan FSM."""

    DRAFT = "Draft", "Draft"
    PENDING_APPROVAL = "PendingApproval", "Pending Approval"
    APPROVED = "Approved", "Approved"

    ACTIVE_CURRENT = "ActiveCurrent", "Active Current"
    ACTIVE_OVERDUE = "ActiveOverdue", "Active Overdue"
    ACTIVE_NPA = "ActiveNPA", "Active NPA"

    CLOSURE_PENDING = "ClosurePending", "Closure Pending"
    RENEWAL_PENDING = "RenewalPending", "Renewal Pending"
    AUCTION_INITIATED = "AuctionInitiated", "Auction Initiated"
    AUCTION_IN_PROGRESS = "AuctionInProgress", "Auction In Progress"
    AUCTION_COMPLETE = "AuctionComplete", "Auction Complete"

    CLOSED = "Closed", "Closed"
    RENEWED = "Renewed", "Renewed"
    WRITTEN_OFF = "WrittenOff", "Written Off"
    REJECTED = "Rejected", "Rejected"
    CANCELLED = "Cancelled", "Cancelled"


class TakenLoanLifecycleState(models.TextChoices):
    """Minimal lifecycle states for loans taken from a lender."""

    DRAFT = "Draft", "Draft"
    ACTIVE = "Active", "Active"
    SETTLEMENT_PENDING = "SettlementPending", "Settlement Pending"
    CLOSED = "Closed", "Closed"
    CANCELLED = "Cancelled", "Cancelled"


ALL_LOAN_STATUS_CHOICES = tuple(
    dict.fromkeys(
        [*LoanStatus.choices, *LoanLifecycleState.choices, *TakenLoanLifecycleState.choices]
    )
)


class InterestType(models.TextChoices):
    """Interest calculation method"""

    SIMPLE = "Simple", "Simple"
    COMPOUND = "Compound", "Compound"


# ============================================================================
# Base Loan Model
# ============================================================================


class BaseLoan(models.Model):
    """
    Abstract base class for all loan types.
    Contains shared fields and common behavior.

    All redundant calculated fields have been removed and replaced with @property methods.
    """

    # Audit fields (previously inherited from dea.BusinessDoc — decoupled 2026-05-03)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="%(class)s_created_by",
    )
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="%(class)s_updated_by",
    )

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

    # Status. Concrete loan types override choices/defaults with their canonical
    # lifecycle vocabulary; the broad choices remain here for compatibility with
    # abstract BaseLoan usage and legacy helper code.
    status = models.CharField(
        max_length=20,
        choices=ALL_LOAN_STATUS_CHOICES,
        default=LoanLifecycleState.DRAFT,
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
            self.loan_id = LoanIDGenerator.generate(self.series, loan_model=self.__class__)

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

    def _has_persisted_release(self) -> bool:
        """Return whether a real Release row still exists for this loan."""
        if self.pk is None:
            return False

        try:
            release_field = self._meta.get_field("release")
        except FieldDoesNotExist:
            return False

        cached_release = self._state.fields_cache.get("release")
        if cached_release is not None:
            release_pk = getattr(cached_release, "pk", None)
            if not release_pk:
                self._state.fields_cache.pop("release", None)
                return False

            exists = release_field.related_model._default_manager.filter(
                pk=release_pk,
                loan_id=self.pk,
            ).exists()
            if not exists:
                self._state.fields_cache.pop("release", None)
            return exists

        try:
            release = getattr(self, "release")
        except (AttributeError, ObjectDoesNotExist):
            return False

        return getattr(release, "pk", None) is not None

    @property
    def is_released(self) -> bool:
        """Check if loan has been released."""
        return self._has_persisted_release()

    @property
    def is_overdue(self) -> bool:
        """Check if the loan is in any overdue/default servicing bucket."""
        return self.status in [
            LoanStatus.DEFAULTED,
            LoanStatus.AUCTIONED,
            LoanLifecycleState.ACTIVE_OVERDUE,
            LoanLifecycleState.ACTIVE_NPA,
        ]

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
        from apps.tenant_apps.girvi.selectors import loan_interest_due

        return loan_interest_due(self, as_of_date)

    @property
    def total_due(self) -> Decimal:
        """Total amount due including principal and interest."""
        return self.get_loan_amount + self.interest_due()

    @property
    def total_due_with_currency(self):
        """Total due as Money object."""
        return Money(self.total_due, "INR")

    def get_total_payments(self) -> Decimal:
        """Sum of all borrower receipts made on this loan."""
        from apps.tenant_apps.girvi.selectors import loan_total_receipt_payments

        return loan_total_receipt_payments(self)

    def get_total_principal_payments(self) -> Decimal:
        """Sum of principal payments across voucher-backed and legacy flows."""
        from apps.tenant_apps.girvi.selectors import loan_total_principal_payments

        return loan_total_principal_payments(self)

    def get_total_interest_payments(self) -> Decimal:
        """Sum of interest payments across voucher-backed and legacy payment flows."""
        from apps.tenant_apps.girvi.selectors import loan_total_interest_payments

        return loan_total_interest_payments(self)

    def interest_paid_total(self) -> Decimal:
        """Interest cash already collected from the borrower."""
        return round(self.get_total_interest_payments(), 2)

    def interest_accrued_gross(self, as_of_date=None) -> Decimal:
        """Interest that has been accrued/recognized up to the selected date."""
        from apps.tenant_apps.girvi.selectors import loan_interest_accrued_gross

        return loan_interest_accrued_gross(self, as_of_date)

    def interest_outstanding(self, as_of_date=None) -> Decimal:
        """Accrued but not-yet-paid interest balance."""
        outstanding = self.interest_accrued_gross(as_of_date) - self.interest_paid_total()
        return round(max(outstanding, Decimal("0")), 2)

    def interest_receivable_balance(self) -> Decimal:
        """Portion of accrued interest that has already been booked into DEA receivables."""
        from apps.tenant_apps.girvi.selectors import loan_interest_receivable_balance

        return loan_interest_receivable_balance(self)

    @property
    def gross_accrued_interest(self) -> Decimal:
        return self.interest_accrued_gross()

    @property
    def outstanding_interest(self) -> Decimal:
        return self.interest_outstanding()

    @property
    def last_accrual_date(self):
        """Most recent accrued period end date, if any."""
        from apps.tenant_apps.girvi.selectors import loan_last_accrual_date

        return loan_last_accrual_date(self)

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
    status = models.CharField(
        max_length=20,
        choices=LoanLifecycleState.choices,
        default=LoanLifecycleState.DRAFT,
        db_index=True,
    )

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
        """Compatibility wrapper for release receipt voucher creation."""
        from apps.tenant_apps.girvi.service_modules.payment_voucher_creation import (
            create_given_loan_release_payment,
        )

        return create_given_loan_release_payment(
            self,
            principal=principal,
            interest=interest,
            payment_date=payment_date,
            payment_method=payment_method,
            reference_number=reference_number,
            description=description,
            created_by=created_by,
        )

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
    borrower_party = models.ForeignKey(
        "party.Party",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="given_loans",
        verbose_name="Borrower Party",
        help_text="Shadow Party link for the borrower during Customer migration.",
    )
    disbursal_upfront_interest_deduction = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Upfront interest deducted from borrower payout at disbursal.",
    )
    disbursal_document_charge = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Document/processing charge deducted from borrower payout at disbursal.",
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
            models.Index(fields=["borrower_party", "status"]),
            models.Index(fields=["status", "loan_date"]),
        ]

    def save(self, *args, **kwargs):
        if not self.borrower_party_id:
            borrower_party = _party_from_customer(getattr(self, "borrower", None))
            if borrower_party:
                self.borrower_party = borrower_party
                update_fields = kwargs.get("update_fields")
                if update_fields is not None:
                    kwargs["update_fields"] = set(update_fields) | {"borrower_party"}
        super().save(*args, **kwargs)

    # ========================================================================
    # Implement abstract properties
    # ========================================================================

    @property
    def get_loan_amount(self) -> Decimal:
        """Sum of all loan item amounts."""
        from apps.tenant_apps.girvi.selectors import given_loan_amount

        return given_loan_amount(self)

    @property
    def get_loan_amount_with_currency(self):
        return Money(self.get_loan_amount, "INR")

    @property
    def get_interest_amount(self) -> Decimal:
        """Sum of base interest from all items."""
        from apps.tenant_apps.girvi.selectors import given_loan_interest_amount

        return given_loan_interest_amount(self)

    @property
    def get_weight_summary(self) -> dict:
        """Weight breakdown by metal type."""
        from apps.tenant_apps.girvi.selectors import given_loan_weight_summary

        return given_loan_weight_summary(self)

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
        from apps.tenant_apps.girvi.selectors import given_loan_item_description

        return given_loan_item_description(self)

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
        from apps.tenant_apps.girvi.selectors import given_loan_current_value

        return given_loan_current_value(self)

    @property
    def disbursal_total_deductions(self) -> Decimal:
        return (self.disbursal_upfront_interest_deduction or Decimal("0.00")) + (
            self.disbursal_document_charge or Decimal("0.00")
        )

    @property
    def disbursal_net_payout(self) -> Decimal:
        return self.get_loan_amount - self.disbursal_total_deductions

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
        """Compatibility wrapper for disbursal voucher creation."""
        from apps.tenant_apps.girvi.service_modules.payment_voucher_creation import (
            create_given_loan_disbursal_payment,
        )

        return create_given_loan_disbursal_payment(
            self,
            amount=amount,
            payment_date=payment_date,
            payment_method=payment_method,
            reference_number=reference_number,
            description=description,
            created_by=created_by,
        )

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
        """Compatibility wrapper for borrower receipt voucher creation."""
        from apps.tenant_apps.girvi.service_modules.payment_voucher_creation import (
            create_given_loan_receipt_payment,
        )

        return create_given_loan_receipt_payment(
            self,
            amount=amount,
            payment_date=payment_date,
            payment_method=payment_method,
            reference_number=reference_number,
            interest=interest,
            principal=principal,
            description=description,
            is_final=is_final,
            create_release=create_release,
            created_by=created_by,
        )

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
    - Items tracked through LoanItem custody fields and RepledgeHistory

    Key Fields:
    - lender: The customer providing this loan
    - original_loan: The GivenLoan being repledged (optional reference)
    """

    status = models.CharField(
        max_length=20,
        choices=TakenLoanLifecycleState.choices,
        default=TakenLoanLifecycleState.DRAFT,
        db_index=True,
    )

    lender = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="loans_given",
        verbose_name="Lender",
        help_text="Customer providing this loan to us",
    )
    lender_party = models.ForeignKey(
        "party.Party",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="taken_loans",
        verbose_name="Lender Party",
        help_text="Shadow Party link for the lender during Customer migration.",
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
            models.Index(fields=["lender_party", "status"]),
            models.Index(fields=["original_loan"]),
        ]

    def save(self, *args, **kwargs):
        if not self.lender_party_id:
            lender_party = _party_from_customer(getattr(self, "lender", None))
            if lender_party:
                self.lender_party = lender_party
                update_fields = kwargs.get("update_fields")
                if update_fields is not None:
                    kwargs["update_fields"] = set(update_fields) | {"lender_party"}
        super().save(*args, **kwargs)

    # ========================================================================
    # Implement abstract properties
    # ========================================================================

    @property
    def get_loan_amount(self) -> Decimal:
        """Sum of all repledged item amounts from custody history."""
        from apps.tenant_apps.girvi.selectors import taken_loan_amount

        return taken_loan_amount(self)

    @property
    def get_loan_amount_with_currency(self):
        return Money(self.get_loan_amount, "INR")

    @property
    def get_interest_amount(self) -> Decimal:
        """Monthly interest derived from custody history repledged amounts."""
        from apps.tenant_apps.girvi.selectors import taken_loan_interest_amount

        return taken_loan_interest_amount(self)

    @property
    def get_weight_summary(self) -> dict:
        """Weight breakdown from custody history items."""
        from apps.tenant_apps.girvi.selectors import taken_loan_weight_summary

        return taken_loan_weight_summary(self)

    @property
    def get_item_description(self) -> str:
        """Descriptions from custody history items."""
        from apps.tenant_apps.girvi.selectors import taken_loan_item_description

        return taken_loan_item_description(self)

    @property
    def current_value(self) -> Decimal:
        """Current value of custody history items."""
        from apps.tenant_apps.girvi.selectors import taken_loan_current_value

        return taken_loan_current_value(self)

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
        """Compatibility wrapper for lender repayment voucher creation."""
        from apps.tenant_apps.girvi.service_modules.payment_voucher_creation import (
            create_taken_loan_repayment_payment,
        )

        return create_taken_loan_repayment_payment(
            self,
            amount=amount,
            payment_date=payment_date,
            payment_method=payment_method,
            reference_number=reference_number,
            interest=interest,
            principal=principal,
            description=description,
            is_final=is_final,
            created_by=created_by,
        )

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
    from .legacy import Loan as OldLoan

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
