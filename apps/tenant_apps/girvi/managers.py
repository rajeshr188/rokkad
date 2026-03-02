"""
⚠️  DEPRECATED: This module is archived. Use managers_refactored.py instead.

Historical reference only. Kept for backward compatibility during transition.
Remove by: September 30, 2026

Old QuerySet and Manager classes for efficient database queries.
Provides chainable methods for:
- Table display: per-row metrics (weights, amounts, interest, value, overdue status)
- Dashboard: aggregated metrics for non-performing and long-dead loans
- Flexibility: compose only the annotations you need

❌ DO NOT USE for new code. Use GivenLoanManager/TakenLoanManager instead.
"""

import datetime
import logging
from functools import lru_cache
from typing import TYPE_CHECKING

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
)
from django.db.models.functions import Ceil, Coalesce, ExtractDay, Round
from django.utils import timezone

from apps.tenant_apps.rates.models import Rate

if TYPE_CHECKING:  # pragma: no cover
    from .services import (
        InterestCalculationService as _InterestCalculationService,
        LoanMetalWeightService as _LoanMetalWeightService,
        DashboardMetricsService as _DashboardMetricsService,
    )

logger = logging.getLogger(__name__)


@lru_cache()
def _get_interest_service():
    from .services import InterestCalculationService

    return InterestCalculationService


@lru_cache()
def _get_weight_service():
    from .services import LoanMetalWeightService

    return LoanMetalWeightService


@lru_cache()
def _get_dashboard_service():
    from .services import DashboardMetricsService

    return DashboardMetricsService


class LoanQuerySet(models.QuerySet):
    def released(self):
        return self.filter(release__isnull=False)

    def unreleased(self):
        return self.filter(release__isnull=True)

    def with_cumsum(self):
        return (
            self.annotate(
                cumsum=Window(Sum("loan_amount"), order_by=F("loan_date").asc())
            )
            .values("loan_date", "cumsum")
            .order_by("loan_date")
        )

    def with_total_interest(self):
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
        """DEPRECATED: Use for_table_display() instead."""
        return self.for_table_display()

    def with_itemwise_loanamount(self):
        return self.with_itemwise_amounts()

    def total_itemwise_loanamount(self):
        return self.with_itemwise_amounts().aggregate(
            gold_loanamount=Sum("gold_loanamount"),
            silver_loanamount=Sum("silver_loanamount"),
            bronze_loanamount=Sum("bronze_loanamount"),
        )

    def total_current_value(self):
        return self.with_current_value().aggregate(total=Sum("total_current_value"))

    def total_weight(self):
        return self.with_metal_weights().aggregate(
            gold=Sum("gold_weight"),
            silver=Sum("silver_weight"),
            bronze=Sum("bronze_weight"),
        )

    def total_pure_weight(self):
        return self.with_metal_weights().aggregate(
            gold=Round(Sum("pure_gold_weight"), 2),
            silver=Round(Sum("pure_silver_weight"), 2),
            bronze=Round(Sum("pure_bronze_weight")),
        )

    def itemwise_value(self):
        return self.with_current_value().aggregate(
            gold=Round(Sum("gold_value"), 2),
            silver=Round(Sum("silver_value"), 2),
            bronze=Round(Sum("bronze_value"), 2),
        )

    def total_loanamount(self):
        return self.aggregate(total=Sum("loan_amount"))

    # ========================================================================
    # NEW: Modular, Chainable Annotation Methods
    # ========================================================================
    # These methods replace the massive with_details() method
    # Use them to build exactly the annotations you need by chaining methods

    def with_duration_metrics(self):
        """
        Add time-based metrics for measuring loan age.

        Annotations:
        - days_since_created: number of days since loan creation (or release)
        - months_since_created: number of months (more accurate than days/30)

        Example:
            loans = Loan.objects.with_duration_metrics().filter(months_since_created__gt=12)
        """
        service = _get_interest_service()
        annotations = service.get_duration_annotations()
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
        service = _get_interest_service()
        return self.annotate(**service.get_interest_annotations())

    def with_metal_weights(self):
        """
        Add itemwise weight metrics (gross and pure by metal type).

        Annotations:
        - gold_weight, silver_weight, bronze_weight: gross weights
        - pure_gold_weight, pure_silver_weight, pure_bronze_weight: purity-adjusted

        Example:
            loans = Loan.objects.with_metal_weights().filter(gold_weight__gt=100)
        """
        service = _get_weight_service()
        annotations = service.get_itemwise_weight_annotations()
        return self.annotate(**annotations)

    def with_itemwise_amounts(self):
        """
        Add itemwise loan amount by metal type.

        Annotations:
        - gold_loanamount, silver_loanamount, bronze_loanamount

        Example:
            loans = Loan.objects.with_itemwise_amounts()
        """
        service = _get_weight_service()
        annotations = service.get_itemwise_amount_annotations()
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
        service = _get_weight_service()
        annotations = service.get_itemwise_value_annotations()
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
        service = _get_weight_service()
        annotations = service.get_overdue_annotation()
        return self.annotate(**annotations)

    def for_table_display(self):
        """
        Convenience method: Get all annotations needed for loan table display.

        Returns:
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


class LoanManager(models.Manager):
    def get_queryset(self):
        return LoanQuerySet(self.model, using=self._db).select_related(
            "series", "release", "customer"
        )

    def released(self):
        return self.get_queryset().released()

    def unreleased(self):
        return self.get_queryset().unreleased()

    def with_duration_metrics(self):
        return self.get_queryset().with_duration_metrics()

    def with_interest_metrics(self):
        return self.get_queryset().with_interest_metrics()

    def with_metal_weights(self):
        return self.get_queryset().with_metal_weights()

    def with_itemwise_amounts(self):
        return self.get_queryset().with_itemwise_amounts()

    def with_current_value(self):
        return self.get_queryset().with_current_value()

    def with_overdue_status(self):
        return self.get_queryset().with_overdue_status()

    def for_table_display(self):
        return self.get_queryset().for_table_display()

    def for_dashboard_metrics(self):
        return self.get_queryset().for_dashboard_metrics()

    def overdue(self):
        return self.get_queryset().overdue()

    def good_standing(self):
        return self.get_queryset().good_standing()

    def long_dead(self, months=12):
        return self.get_queryset().long_dead(months)

    def with_details(self, grate, srate, brate):
        return self.get_queryset().with_details(grate, srate, brate)

    def with_itemwise_loanamount(self):
        return self.get_queryset().with_itemwise_loanamount()

    def total_itemwise_loanamount(self):
        return self.get_queryset().total_itemwise_loanamount()

    def with_total_value(self):
        return self.get_queryset().aggregate(total_value=Sum("total_current_value"))

    def total_loanamount(self):
        return self.get_queryset().aggregate(total=Sum("loan_amount"))

    def total_interest(self):
        return self.get_queryset().aggregate(total=Sum("total_interest"))

    def total_due(self):
        return self.get_queryset().aggregate(total=Sum("total_due"))

    def total_weight(self):
        return self.get_queryset().total_weight()

    def total_pure_weight(self):
        return self.get_queryset().total_pure_weight()

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
        service = _get_dashboard_service()
        return service.get_non_performing_loans_stats(queryset=self.get_queryset())

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
        service = _get_dashboard_service()
        return service.get_long_dead_loans_stats(
            queryset=self.get_queryset(), threshold_months=threshold_months
        )


class ReleasedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(release__isnull=False)


class UnReleasedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(release__isnull=True)
