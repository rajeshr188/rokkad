"""
⚠️  DEPRECATED: This module is archived. Use managers_refactored.py instead.

Historical reference only. Kept for backward compatibility during transition.
Remove by: September 30, 2026

Old Improved Loan QuerySet and Manager classes for efficient database queries.
This was the new, refactored version replacing the massive with_details() method.

Provides chainable methods for:
- Table display: per-row metrics (weights, amounts, interest, value, overdue status)
- Dashboard: aggregated metrics for non-performing and long-dead loans
- Flexibility: compose only the annotations you need

❌ DO NOT USE for new code. Use GivenLoanManager/TakenLoanManager instead.

For migration details, see: docs/MIGRATION_TO_GIVENLOAN_TAKENLOAN.md
"""

import datetime
import logging

from django.core.cache import cache
from django.db import models
from django.db.models import (
    Case,
    DecimalField,
    ExpressionWrapper,
    F,
    Func,
    Sum,
    Value,
    When,
    Window,
    Q,
    Count,
)
from django.db.models.functions import Ceil, Coalesce, ExtractDay, Round
from django.utils import timezone

from apps.tenant_apps.rates.models import Rate
from .services import (
    RateCacheService,
    InterestCalculationService,
    LoanMetalWeightService,
    DashboardMetricsService,
)

logger = logging.getLogger(__name__)


class ImprovedLoanQuerySet(models.QuerySet):
    """
    Improved QuerySet with modular, chainable annotation methods.

    Usage:
        # For table display (all metrics)
        loans = Loan.objects.unreleased().for_table_display()

        # For dashboard
        stats = Loan.objects.non_performing_loans_stats()

        # For custom queries
        loans = (
            Loan.objects.unreleased()
            .with_duration_metrics()
            .with_metal_weights()
            .filter(gold_weight__gt=100)
        )
    """

    def released(self):
        """Filter for released loans."""
        return self.filter(release__isnull=False)

    def unreleased(self):
        """Filter for unreleased loans."""
        return self.filter(release__isnull=True)

    def with_cumsum(self):
        """Add cumulative sum window function."""
        return (
            self.annotate(
                cumsum=Window(Sum("loan_amount"), order_by=F("loan_date").asc())
            )
            .values("loan_date", "cumsum")
            .order_by("loan_date")
        )

    # ========================================================================
    # NEW: Modular, Chainable Annotation Methods
    # ========================================================================

    def with_duration_metrics(self):
        """
        Add time-based metrics for measuring loan age.

        Annotations:
        - days_since_created: number of days since loan creation (or release)
        - months_since_created: number of months (more accurate than days/30)

        Example:
            loans = Loan.objects.with_duration_metrics().filter(months_since_created__gt=12)
        """
        annotations = InterestCalculationService.get_duration_annotations()
        return self.annotate(**annotations)

    def with_interest_metrics(self):
        """
        Add interest and payment-related metrics.
        REQUIRES: with_duration_metrics() to be called first!

        Annotations:
        - total_interest: interest * months_since_created
        - total_due: loan_amount + total_interest

        Example:
            loans = Loan.objects.with_duration_metrics().with_interest_metrics()
        """
        return self.annotate(**InterestCalculationService.get_interest_annotations())

    def with_metal_weights(self):
        """
        Add itemwise weight metrics (gross and pure by metal type).

        Annotations:
        - gold_weight, silver_weight, bronze_weight: gross weights
        - pure_gold_weight, pure_silver_weight, pure_bronze_weight: purity-adjusted

        Example:
            loans = Loan.objects.with_metal_weights().filter(gold_weight__gt=100)
        """
        annotations = LoanMetalWeightService.get_itemwise_weight_annotations()
        return self.annotate(**annotations)

    def with_itemwise_amounts(self):
        """
        Add itemwise loan amount by metal type.

        Annotations:
        - gold_loanamount, silver_loanamount, bronze_loanamount

        Example:
            loans = Loan.objects.with_itemwise_amounts()
        """
        annotations = LoanMetalWeightService.get_itemwise_amount_annotations()
        return self.annotate(**annotations)

    def with_current_value(self):
        """
        Calculate current collateral value based on live market rates.
        REQUIRES: with_metal_weights() to be called first!

        Annotations:
        - gold_value, silver_value, bronze_value: value by metal type
        - total_current_value: sum of all metal values

        Uses RateCacheService which caches rates for 5 minutes.

        Example:
            loans = Loan.objects.with_metal_weights().with_current_value()
        """
        annotations = LoanMetalWeightService.get_itemwise_value_annotations()
        return self.annotate(**annotations)

    def with_overdue_status(self):
        """
        Determine if loan is overdue (current_value < total_due).
        REQUIRES: with_interest_metrics() and with_current_value() !

        Annotations:
        - is_overdue: boolean True if collateral value insufficient

        Example:
            loans = (
                Loan.objects
                .with_duration_metrics()
                .with_interest_metrics()
                .with_metal_weights()
                .with_current_value()
                .with_overdue_status()
                .filter(is_overdue=True)
            )
        """
        annotations = LoanMetalWeightService.get_overdue_annotation()
        return self.annotate(**annotations)

    def for_table_display(self):
        """
        Convenience method: Get all annotations needed for loan table display.

        Returns annotations for:
        - duration: days_since_created, months_since_created
        - interest: total_interest, total_due
        - weights: gold_weight, pure_gold_weight, ... (all metals)
        - amounts: gold_loanamount, ... (all metals)
        - values: gold_value, ..., total_current_value
        - status: is_overdue

        This is the kitchen sink—use individual methods if you don't need everything.

        Example (table view):
            loans = Loan.objects.unreleased().for_table_display().select_related(...)
            for loan in loans:
                context['rows'].append({
                    'id': loan.id,
                    'gold_weight': loan.gold_weight,
                    'pure_gold_weight': loan.pure_gold_weight,
                    'gold_loanamount': loan.gold_loanamount,
                    'months': loan.months_since_created,
                    'total_interest': loan.total_interest,
                    'total_due': loan.total_due,
                    'current_value': loan.total_current_value,
                    'is_overdue': loan.is_overdue,
                })
        """
        return (
            self.with_duration_metrics()
            .with_metal_weights()
            .with_itemwise_amounts()
            .with_interest_metrics()
            .with_current_value()
            .with_overdue_status()
        )

    def for_dashboard_metrics(self):
        """
        Get annotations optimized for dashboard summary cards.

        More lightweight than for_table_display() - use for aggregations.

        Example (dashboard):
            non_perf_metrics = (
                Loan.objects
                .unreleased()
                .for_dashboard_metrics()
                .filter(is_overdue=True)
                .aggregate(
                    count=Count('id'),
                    total_due=Sum('total_due'),
                    total_value=Sum('total_current_value'),
                )
            )
        """
        return (
            self.with_duration_metrics()
            .with_metal_weights()
            .with_interest_metrics()
            .with_current_value()
            .with_overdue_status()
        )

    def overdue(self):
        """Get only overdue loans (convenience method)."""
        return self.for_dashboard_metrics().filter(is_overdue=True)

    def good_standing(self):
        """Get only loans in good standing (convenience method)."""
        return self.for_dashboard_metrics().filter(is_overdue=False)

    def long_dead(self, months=12):
        """Get loans unreleased for specified months (convenience method)."""
        return (
            self.unreleased()
            .with_duration_metrics()
            .filter(months_since_created__gte=months)
        )


class ImprovedLoanManager(models.Manager):
    """
    Improved manager providing convenient access to ImprovedLoanQuerySet methods.
    """

    def get_queryset(self):
        return ImprovedLoanQuerySet(self.model, using=self._db).select_related(
            "series", "release", "customer"
        )

    def released(self):
        """Get released loans."""
        return self.get_queryset().released()

    def unreleased(self):
        """Get unreleased loans."""
        return self.get_queryset().unreleased()

    def overdue(self):
        """Get overdue loans."""
        return self.get_queryset().overdue()

    def good_standing(self):
        """Get loans in good standing."""
        return self.get_queryset().good_standing()

    def long_dead(self, months=12):
        """Get long-dead loans."""
        return self.get_queryset().long_dead(months)

    # ========================================================================
    # Dashboard Metrics Methods
    # ========================================================================

    def non_performing_loans_stats(self):
        """
        Get aggregated stats for non-performing loans.

        Returns dict:
        {
            'count': number of loans,
            'total_due': sum of amounts due,
            'metals': {
                'Gold': {'weight': X, 'pure_weight': Y, 'value': Z, 'rate': R},
                'Silver': {...},
                'Bronze': {...},
            },
            'total_collateral_value': sum of all values,
            'current_rates': {'Gold': X, 'Silver': Y, 'Bronze': Z},
            'rates_timestamp': datetime,
        }

        Example:
            stats = Loan.objects.non_performing_loans_stats()
            context['non_perf'] = stats
            # Use in template: {{ non_perf.count }}, {{ non_perf.total_due }}, etc.
        """
        return DashboardMetricsService.get_non_performing_loans_stats(
            queryset=self.get_queryset()
        )

    def long_dead_loans_stats(self, threshold_months=None):
        """
        Get aggregated stats for long-dead loans (unreleased for 12+ months).

        Args:
            threshold_months: override default 12 month threshold

        Returns: Same structure as non_performing_loans_stats()

        Example:
            stats = Loan.objects.long_dead_loans_stats()
            context['long_dead'] = stats
        """
        return DashboardMetricsService.get_long_dead_loans_stats(
            queryset=self.get_queryset(), threshold_months=threshold_months
        )


class ImprovedReleasedManager(models.Manager):
    """Manager for released loans only."""

    def get_queryset(self):
        return (
            ImprovedLoanQuerySet(self.model, using=self._db)
            .filter(release__isnull=False)
            .select_related("series", "release", "customer")
        )


class ImprovedUnReleasedManager(models.Manager):
    """Manager for unreleased loans only."""

    def get_queryset(self):
        return (
            ImprovedLoanQuerySet(self.model, using=self._db)
            .filter(release__isnull=True)
            .select_related("series", "customer")
        )


class ImprovedLoanQuerySetOld(models.QuerySet):
    """
    DEPRECATED: Old methods kept for backwards compatibility.
    These will be removed - migrate to new methods instead.
    """

    def with_total_interest(self):
        """DEPRECATED: Use with_interest_metrics() instead."""
        today = datetime.date.today()

        return self.annotate(
            no_of_months=ExpressionWrapper(
                today.month
                - F("loan_date__month")
                + 12 * (today.year - F("loan_date__year")),
                output_field=DecimalField(decimal_places=2),
            ),
            loan_interest=F("interest") * F("no_of_months"),
        ).annotate(Sum("loan_interest"))

    def _get_rates(self):
        """DEPRECATED: Use RateCacheService instead."""
        grate = cache.get("gold_rate")
        srate = cache.get("silver_rate")
        brate = cache.get("bronze_rate")

        if not (grate and srate and brate):
            latest_rate = Rate.objects.filter(
                metal__in=[Rate.Metal.GOLD, Rate.Metal.SILVER, Rate.Metal.BRONZE]
            ).order_by("-timestamp")
            grate = grate or latest_rate.filter(metal=Rate.Metal.GOLD).first()
            srate = srate or latest_rate.filter(metal=Rate.Metal.SILVER).first()
            brate = brate or latest_rate.filter(metal=Rate.Metal.BRONZE).first()
            cache.set("gold_rate", grate, 300)
            cache.set("silver_rate", srate, 300)
            cache.set("bronze_rate", brate, 300)

        return grate, srate, brate

    def months_since_or_to_release(self):
        """DEPRECATED: Use with_duration_metrics() instead."""
        now = timezone.now()
        return self.annotate(
            months_since=ExpressionWrapper(
                Case(
                    When(
                        release__release_date__isnull=False,
                        then=Func(
                            F("release__release_date") - F("loan_date"),
                            function="EXTRACT",
                            template="EXTRACT(MONTH FROM %(expressions)s)",
                            output_field=DecimalField(),
                        ),
                    ),
                    default=Func(
                        now - F("loan_date"),
                        function="EXTRACT",
                        template="EXTRACT(MONTH FROM %(expressions)s)",
                        output_field=DecimalField(),
                    ),
                ),
                output_field=DecimalField(),
            )
        )

    def with_details(self, grate=None, srate=None, brate=None):
        """
        DEPRECATED: Old massive method combining all annotations.

        Use for_table_display() instead - it's cleaner and handles rate caching automatically.

        This method is kept for backwards compatibility but should be migrated away from.
        """
        return self.for_table_display()

    def with_itemwise_loanamount(self):
        """DEPRECATED: Use with_itemwise_amounts() instead."""
        return self.with_itemwise_amounts()

    def total_itemwise_loanamount(self):
        """DEPRECATED: Use with_itemwise_amounts() + aggregate instead."""
        return self.with_itemwise_amounts().aggregate(
            gold_loanamount=Sum("gold_loanamount"),
            silver_loanamount=Sum("silver_loanamount"),
            bronze_loanamount=Sum("bronze_loanamount"),
        )

    def total_current_value(self):
        """DEPRECATED: Use with_current_value() + aggregate instead."""
        return self.with_current_value().aggregate(total=Sum("total_current_value"))

    def total_weight(self):
        """DEPRECATED: Use with_metal_weights() + aggregate instead."""
        return self.with_metal_weights().aggregate(
            gold=Sum("gold_weight"),
            silver=Sum("silver_weight"),
            bronze=Sum("bronze_weight"),
        )

    def total_pure_weight(self):
        """DEPRECATED: Use with_metal_weights() + aggregate instead."""
        return self.with_metal_weights().aggregate(
            gold=Round(Sum("pure_gold_weight"), 2),
            silver=Round(Sum("pure_silver_weight"), 2),
            bronze=Round(Sum("pure_bronze_weight")),
        )

    def itemwise_value(self):
        """DEPRECATED: Use with_metal_weights() + with_current_value() instead."""
        return self.with_current_value().aggregate(
            gold=Round(Sum("gold_value"), 2),
            silver=Round(Sum("silver_value"), 2),
            bronze=Round(Sum("bronze_value"), 2),
        )

    def total_loanamount(self):
        """DEPRECATED: Use aggregate(total=Sum('loan_amount')) instead."""
        return self.aggregate(total=Sum("loan_amount"))


# ============================================================================
# MIGRATION GUIDE
# ============================================================================
#
# If you're still using the old managers.py, here's how to migrate:
#
# OLD CODE:
#   from girvi.managers import LoanManager, LoanQuerySet
#   loans = Loan.objects.with_details(grate, srate, brate)
#
# NEW CODE:
#   from girvi.manager_improved import ImprovedLoanManager as LoanManager
#   loans = Loan.objects.for_table_display()
#
# GRADUAL MIGRATION:
# Step 1: Import both (keep old manager as fallback)
# Step 2: Replace problem queries one by one
# Step 3: Remove old manager references
# Step 4: Delete old managers.py when confident
#
# ============================================================================
