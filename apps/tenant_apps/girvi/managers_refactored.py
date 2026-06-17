"""
Refactored Manager and QuerySet for new loan structure.

Key Changes from Original Managers:
1. Separate QuerySets for GivenLoan and TakenLoan (no more loan_type filtering)
2. Removed loan_type conditional logic
3. Cleaner, more focused query methods
4. Maintained all performance optimizations from improved managers
"""

import datetime
import logging

from django.core.cache import cache
from django.db import models
from django.db.models import (
    BooleanField,
    Case,
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Func,
    Sum,
    Value,
    When,
    Window,
    Q,
)
from django.db.models.functions import Ceil, Coalesce, ExtractDay, Round
from django.utils import timezone


logger = logging.getLogger(__name__)


# ============================================================================
# Base QuerySet - Shared by Both Loan Types
# ============================================================================


class BaseLoanQuerySet(models.QuerySet):
    """
    Shared QuerySet methods for all loan types.
    Contains annotation chains that work identically for GivenLoan and TakenLoan.
    """

    def _supports_release_relation(self):
        """Return True when the model exposes a release relation usable in filters."""
        return any(
            field.name == "release" for field in self.model._meta.get_fields()
        )

    def released(self):
        """Filter to loans that have been released."""
        from .lifecycle import RELEASED_COMPAT_STATUSES

        if self._supports_release_relation():
            return self.filter(release__isnull=False)
        return self.filter(status__in=RELEASED_COMPAT_STATUSES)

    def unreleased(self):
        """Filter to loans that have NOT been released."""
        from .lifecycle import UNRELEASED_EXCLUDED_STATUSES

        if self._supports_release_relation():
            return self.filter(release__isnull=True)
        return self.exclude(status__in=UNRELEASED_EXCLUDED_STATUSES)

    def active(self):
        """Filter to loans in active or pre-closure lifecycle status."""
        from .lifecycle import ACTIVE_LOAN_STATUSES

        return self.filter(status__in=ACTIVE_LOAN_STATUSES).unreleased()

    def overdue(self):
        """Loans in non-performing states."""
        return self.with_overdue_status().filter(is_overdue=True)

    def by_status(self, status):
        """Filter by specific status."""
        return self.filter(status=status)

    # ========================================================================
    # Time-based queries
    # ========================================================================

    def created_in_range(self, start_date, end_date=None):
        """Loans created within date range."""
        end_date = end_date or timezone.now()
        return self.filter(loan_date__gte=start_date, loan_date__lte=end_date)

    def older_than_months(self, months):
        """Loans older than N months."""
        cutoff = timezone.now() - datetime.timedelta(days=months * 30)
        return self.filter(loan_date__lt=cutoff)

    # ========================================================================
    # Annotation Chains (same as improved managers)
    # ========================================================================

    def with_duration_metrics(self):
        """
        Add time-based metrics.

        Annotations:
        - days_since_created
        - months_since_created
        """
        from .services import InterestCalculationService

        loan_kind = {
            "GivenLoan": "given",
            "TakenLoan": "taken",
        }.get(self.model.__name__, "legacy")
        annotations = InterestCalculationService.get_duration_annotations(loan_kind)
        return self.annotate(**annotations)

    def with_interest_metrics(self):
        """
        Add interest calculations.
        REQUIRES: with_duration_metrics() first!

        Annotations:
        - loan_amount
        - interest_amount
        - total_interest
        - total_due
        """
        from .services import InterestCalculationService

        loan_kind = {
            "GivenLoan": "given",
            "TakenLoan": "taken",
        }.get(self.model.__name__)

        if loan_kind is None:
            raise TypeError("Interest metrics require GivenLoan or TakenLoan querysets.")

        return self.annotate(
            **InterestCalculationService.get_interest_base_annotations(loan_kind)
        ).annotate(
            **InterestCalculationService.get_interest_total_annotations(loan_kind)
        )

    def with_payment_metrics(self):
        """
        Add payment-related metrics.

        Annotations:
        - total_payments
        - principal_paid
        - interest_paid
        - outstanding_balance
        """
        return self.annotate(
            total_payments=Coalesce(
                Sum("loan_payments__payment_amount"),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            principal_paid=Coalesce(
                Sum("loan_payments__principal_payment"),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            interest_paid=Coalesce(
                Sum("loan_payments__interest_payment"),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )

    def for_table_display(self):
        """
        Complete annotation chain for table views.

        Includes:
        - Duration metrics
        - Metal weights (gross & pure)
        - Loan amounts by metal type
        - Current values
        - Payment info

        Note: For GivenLoan/TakenLoan, skips interest_metrics which requires
        fields not available on these models (interest, loan_amount exist on
        LoanItems, not the Loan itself).
        """
        return (
            self.with_duration_metrics()
            .with_metal_weights()
            .with_itemwise_amounts()
            .with_current_value()
            .with_payment_metrics()
        )

    def for_dashboard_metrics(self):
        """
        Lightweight annotations for dashboard aggregations.
        """
        return (
            self.with_duration_metrics()
            .with_interest_metrics()
            .with_current_value()
            .with_overdue_status()
        )

    # ========================================================================
    # Aggregation methods
    # ========================================================================

    def total_loan_amount(self):
        """Total principal across all loans in queryset."""
        # Use database aggregation on related items
        # For GivenLoan: sum loanitems.loanamount
        # For TakenLoan: sum repledgedloanitems.repledged_loanamount
        # This is handled by subclass-specific implementations
        raise NotImplementedError("Subclass must implement")

    def total_weight_by_metal(self):
        """Aggregate weight by metal type."""
        return self.with_metal_weights().aggregate(
            gold=Round(Sum("gold_weight"), 3),
            silver=Round(Sum("silver_weight"), 3),
            bronze=Round(Sum("bronze_weight"), 3),
        )

    def total_pure_weight_by_metal(self):
        """Aggregate pure weight by metal type."""
        return self.with_metal_weights().aggregate(
            gold=Round(Sum("pure_gold_weight"), 3),
            silver=Round(Sum("pure_silver_weight"), 3),
            bronze=Round(Sum("pure_bronze_weight"), 3),
        )

    def total_current_value(self):
        """Total market value of collateral."""
        return self.with_current_value().aggregate(total=Sum("total_current_value"))[
            "total"
        ]


# ============================================================================
# GivenLoan QuerySet
# ============================================================================


class GivenLoanQuerySet(BaseLoanQuerySet):
    """
    QuerySet specific to loans given TO customers (pawns).
    """

    def by_borrower(self, customer):
        """Filter by borrower."""
        return self.filter(borrower=customer)

    def with_metal_weights(self):
        """
        Add weight metrics from LoanItem.

        Annotations:
        - gold_weight, silver_weight, bronze_weight
        - pure_gold_weight, pure_silver_weight, pure_bronze_weight
        """
        from .services import LoanMetalWeightService

        annotations = LoanMetalWeightService.get_given_loan_weight_annotations()
        return self.annotate(**annotations)

    def with_itemwise_amounts(self):
        """
        Add loan amounts by metal type from LoanItem.

        Annotations:
        - gold_loanamount, silver_loanamount, bronze_loanamount
        """
        from .services import LoanMetalWeightService

        annotations = LoanMetalWeightService.get_given_loan_amount_annotations()
        return self.annotate(**annotations)

    def with_current_value(self):
        """
        Calculate current collateral value based on market rates.
        REQUIRES: with_metal_weights() first!

        Annotations:
        - gold_value, silver_value, bronze_value
        - total_current_value
        """
        from .services import LoanMetalWeightService

        annotations = LoanMetalWeightService.get_given_loan_value_annotations()
        return self.annotate(**annotations)

    def with_overdue_status(self):
        """
        Determine if loan is overdue using lifecycle status.

        In the refactored models, overdue/non-performing state is represented
        by status rather than collateral-vs-due annotations.
        """
        from .lifecycle import OVERDUE_LOAN_STATUSES

        return self.annotate(
            is_overdue=Case(
                When(status__in=OVERDUE_LOAN_STATUSES, then=True),
                default=False,
                output_field=BooleanField(),
            )
        )

    def total_loan_amount(self):
        """Total principal from all LoanItems."""
        return self.aggregate(
            total=Coalesce(
                Sum("loanitems__loanamount"),
                Value(0),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            )
        )["total"]

    def total_weight(self):
        """Total gross weight from all LoanItems."""
        return (
            self.with_metal_weights().aggregate(
                total=Round(
                    Sum("gold_weight") + Sum("silver_weight") + Sum("bronze_weight"), 3
                )
            )["total"]
            or 0
        )

    def total_pure_weight(self):
        """Total pure weight from all LoanItems."""
        return (
            self.with_metal_weights().aggregate(
                total=Round(
                    Sum("pure_gold_weight")
                    + Sum("pure_silver_weight")
                    + Sum("pure_bronze_weight"),
                    3,
                )
            )["total"]
            or 0
        )

    def total_current_value(self):
        """Total current collateral value from all LoanItems."""
        return (
            self.with_metal_weights()
            .with_current_value()
            .aggregate(total=Round(Sum("total_current_value"), 2))
        )

    def total_loanamount(self):
        """Alias for total_loan_amount for backward compatibility."""
        return self.total_loan_amount()

    def itemwise_value(self):
        """Itemwise value breakdown by metal type."""
        return (
            self.with_itemwise_amounts()
            .with_current_value()
            .aggregate(
                gold=Round(Sum("gold_value"), 2),
                silver=Round(Sum("silver_value"), 2),
                bronze=Round(Sum("bronze_value"), 2),
            )
        )

    def total_itemwise_loanamount(self):
        """Total itemwise loan amounts by metal type."""
        return self.with_itemwise_amounts().aggregate(
            gold=Round(Sum("gold_loanamount"), 2),
            silver=Round(Sum("silver_loanamount"), 2),
            bronze=Round(Sum("bronze_loanamount"), 2),
        )

    def splittable(self):
        """Loans with more than one item (can be split)."""
        return self.annotate(item_count=Count("loanitems")).filter(item_count__gt=1)

    def available_for_repledge(self):
        """Loans with items that can be repledged."""
        return self.unreleased().filter(loanitems__custody_status="in_vault").distinct()


class GivenLoanManager(models.Manager):
    """Manager for GivenLoan with efficient query defaults."""

    def get_queryset(self):
        return GivenLoanQuerySet(self.model, using=self._db)

    def released(self):
        return self.get_queryset().released()

    def unreleased(self):
        return self.get_queryset().unreleased()

    def active(self):
        return self.get_queryset().active()

    def overdue(self):
        return self.get_queryset().overdue()

    def for_table_display(self):
        """
        Return queryset optimized for table display.
        For GivenLoan (with LoanItems), returns base queryset.
        """
        return self.get_queryset()

    def non_performing_loans_stats(self):
        """
        Get statistics for non-performing loans (is_overdue=True).

        Returns QuerySet with overdue status annotation.

        Usage:
            stats = GivenLoan.objects.non_performing_loans_stats()
            count = stats.count()
        """
        return self.get_queryset().with_overdue_status().filter(is_overdue=True)

    def long_dead_loans_stats(self, threshold_months=12):
        """
        Get statistics for long-dead loans (unreleased for N+ months).

        Args:
            threshold_months: Minimum months unreleased (default: 12)

        Returns QuerySet of old unreleased loans.

        Usage:
            stats = GivenLoan.objects.long_dead_loans_stats(threshold_months=12)
            count = stats.count()
        """
        from datetime import timedelta
        from django.utils import timezone

        cutoff_date = timezone.now() - timedelta(days=threshold_months * 30)
        return self.get_queryset().unreleased().filter(loan_date__lt=cutoff_date)


# ============================================================================
# TakenLoan QuerySet
# ============================================================================


class TakenLoanQuerySet(BaseLoanQuerySet):
    """
    QuerySet specific to loans taken FROM customers (repledges).
    """

    def by_lender(self, customer):
        """Filter by lender."""
        return self.filter(lender=customer)

    def from_original_loan(self, given_loan):
        """Filter by original GivenLoan."""
        return self.filter(original_loan=given_loan)

    def with_metal_weights(self):
        """
        Add weight metrics from RepledgedLoanItem -> original LoanItem.

        Annotations:
        - gold_weight, silver_weight, bronze_weight
        - pure_gold_weight, pure_silver_weight, pure_bronze_weight
        """
        from .services import LoanMetalWeightService

        annotations = LoanMetalWeightService.get_taken_loan_weight_annotations()
        return self.annotate(**annotations)

    def with_itemwise_amounts(self):
        """
        Add loan amounts by metal type from RepledgedLoanItem.

        Annotations:
        - gold_loanamount, silver_loanamount, bronze_loanamount
        """
        from .services import LoanMetalWeightService

        annotations = LoanMetalWeightService.get_taken_loan_amount_annotations()
        return self.annotate(**annotations)

    def with_current_value(self):
        """
        Calculate current value from original items.
        REQUIRES: with_metal_weights() first!
        """
        from .services import LoanMetalWeightService

        annotations = LoanMetalWeightService.get_taken_loan_value_annotations()
        return self.annotate(**annotations)

    def with_overdue_status(self):
        """Determine if loan is overdue using lifecycle status."""
        from .lifecycle import OVERDUE_LOAN_STATUSES

        return self.annotate(
            is_overdue=Case(
                When(status__in=OVERDUE_LOAN_STATUSES, then=True),
                default=False,
                output_field=BooleanField(),
            )
        )

    def total_loan_amount(self):
        """Total principal from all RepledgedLoanItems."""
        return self.aggregate(
            total=Coalesce(
                Sum("repledgedloanitems__repledged_loanamount"),
                Value(0),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            )
        )["total"]

    def total_weight(self):
        """Total gross weight from all RepledgedLoanItems."""
        return (
            self.with_metal_weights().aggregate(
                total=Round(
                    Sum("gold_weight") + Sum("silver_weight") + Sum("bronze_weight"), 3
                )
            )["total"]
            or 0
        )

    def total_pure_weight(self):
        """Total pure weight from all RepledgedLoanItems."""
        return (
            self.with_metal_weights().aggregate(
                total=Round(
                    Sum("pure_gold_weight")
                    + Sum("pure_silver_weight")
                    + Sum("pure_bronze_weight"),
                    3,
                )
            )["total"]
            or 0
        )

    def total_current_value(self):
        """Total current collateral value from all RepledgedLoanItems."""
        return (
            self.with_metal_weights()
            .with_current_value()
            .aggregate(total=Round(Sum("total_current_value"), 2))
        )

    def total_loanamount(self):
        """Alias for total_loan_amount for backward compatibility."""
        return self.total_loan_amount()

    def itemwise_value(self):
        """Itemwise value breakdown by metal type."""
        return (
            self.with_itemwise_amounts()
            .with_current_value()
            .aggregate(
                gold=Round(Sum("gold_value"), 2),
                silver=Round(Sum("silver_value"), 2),
                bronze=Round(Sum("bronze_value"), 2),
            )
        )

    def total_itemwise_loanamount(self):
        """Total itemwise loan amounts by metal type."""
        return self.with_itemwise_amounts().aggregate(
            gold=Round(Sum("gold_loanamount"), 2),
            silver=Round(Sum("silver_loanamount"), 2),
            bronze=Round(Sum("bronze_loanamount"), 2),
        )


class TakenLoanManager(models.Manager):
    """Manager for TakenLoan with efficient query defaults."""

    def get_queryset(self):
        return TakenLoanQuerySet(self.model, using=self._db)

    def released(self):
        return self.get_queryset().released()

    def unreleased(self):
        return self.get_queryset().unreleased()

    def active(self):
        return self.get_queryset().active()

    def overdue(self):
        return self.get_queryset().overdue()

    def for_table_display(self):
        """
        Return queryset optimized for table display.
        For TakenLoan (with RepledgedLoanItems), returns base queryset.
        """
        return self.get_queryset()

    def non_performing_loans_stats(self):
        """
        Get statistics for non-performing repledge loans (is_overdue=True).

        Returns QuerySet with overdue status annotation.

        Usage:
            stats = TakenLoan.objects.non_performing_loans_stats()
            count = stats.count()
        """
        return self.get_queryset().with_overdue_status().filter(is_overdue=True)

    def long_dead_loans_stats(self, threshold_months=12):
        """
        Get statistics for long-dead repledge loans (unreleased for N+ months).

        Args:
            threshold_months: Minimum months unreleased (default: 12)

        Returns QuerySet of old unreleased repledge loans.

        Usage:
            stats = TakenLoan.objects.long_dead_loans_stats(threshold_months=12)
            count = stats.count()
        """
        from datetime import timedelta
        from django.utils import timezone

        cutoff_date = timezone.now() - timedelta(days=threshold_months * 30)
        return self.get_queryset().unreleased().filter(loan_date__lt=cutoff_date)
