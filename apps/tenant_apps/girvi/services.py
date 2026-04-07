import logging
from decimal import Decimal

from django.apps import apps
from django.db import transaction
from django.db.models import (
    BooleanField,
    Case,
    Count,
    DecimalField,
    DurationField,
    ExpressionWrapper,
    F,
    IntegerField,
    Q,
    Sum,
    Value,
    When,
    Window,
)
from django.db.models.functions import Coalesce, ExtractYear, Round
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.girvi.models.loan_refactored import GivenLoan
from .models import Series
from .service_modules.accrual import (
    InterestAccrualCommand,
    InterestAccrualPreview,
    InterestAccrualResult,
    InterestAccrualService,
)
from .service_modules.bulk_release import BulkReleaseService
from .service_modules.creation import (
    LoanCreateCommand,
    LoanCreatePreview,
    LoanCreateResult,
    LoanCreationService,
    LoanItemCreateInput,
)
from .service_modules.id_generation import LoanIDGenerator, ReleaseIDGenerator
from .service_modules.printing import LoanPrintService
from .service_modules.release_lifecycle import (
    ReleaseCreateCommand,
    ReleaseCreatePreview,
    ReleaseCreateResult,
    ReleaseLifecycleService,
)
from .service_modules.renewal import (
    LoanRenewalCommand,
    LoanRenewalPreview,
    LoanRenewalResult,
    LoanRenewalService,
)
from .service_modules.split_merge import LoanMergeService, LoanSplitService
from .service_modules.transitions import LoanTransitionService

# NOTE: LoanItem, LoanPayment, and License imported locally in methods to avoid circular import
# NOTE: GivenLoan is imported locally in methods to avoid circular import
# See usage in LoanSplitService.split_items() and LoanMergeService.merge()

logger = logging.getLogger(__name__)

__all__ = [
    "InterestAccrualCommand",
    "InterestAccrualPreview",
    "InterestAccrualResult",
    "InterestAccrualService",
    "BulkReleaseService",
    "LoanCreateCommand",
    "LoanCreatePreview",
    "LoanCreateResult",
    "LoanCreationService",
    "LoanItemCreateInput",
    "LoanPrintService",
    "ReleaseLifecycleService",
    "ReleaseCreateCommand",
    "ReleaseCreatePreview",
    "ReleaseCreateResult",
    "LoanIDGenerator",
    "ReleaseIDGenerator",
    "LoanTransitionService",
    "LoanRenewalCommand",
    "LoanRenewalPreview",
    "LoanRenewalResult",
    "LoanRenewalService",
    "LoanSplitService",
    "LoanMergeService",
]


def get_or_create_series(series_id: int = None) -> Series:
    """Helper to get or create default series."""
    from .models import License  # Import here to avoid circular imports

    if series_id:
        return Series.objects.get(id=series_id)
    try:
        return Series.objects.latest("id")
    except Series.DoesNotExist:
        license = License.objects.first()
        if not license:
            raise License.DoesNotExist("No license found.")
        series = Series.objects.create(
            name="A", prefix="A", license=license, is_active=True, max_limit=5
        )
        print(f"Series 'A' created with license '{license}'.")
        return series


def get_loan_cumulative_amount():
    from .selectors import get_loan_cumulative_amount as _selector_impl

    return _selector_impl()


def get_average_loan_instance_per_day():
    from .selectors import get_average_loan_instance_per_day as _selector_impl

    return _selector_impl()


def get_loan_counts_grouped():
    from .selectors import get_loan_counts_grouped as _selector_impl

    return _selector_impl()


def get_loans_by_year():
    from .selectors import get_loans_by_year as _selector_impl

    return _selector_impl()


def get_unreleased_loans_by_year():
    from .selectors import get_unreleased_loans_by_year as _selector_impl

    return _selector_impl()


def get_loanamount_by_itemtype():
    from .selectors import get_loanamount_by_itemtype as _selector_impl

    return _selector_impl()


def get_itemtype_averages():
    from .selectors import get_itemtype_averages as _selector_impl

    return _selector_impl()




def get_interest_paid():
    # DEPRECATED: LoanPayment interest data is no longer collected.
    # New interest data flows through PaymentVoucher/DEA system.
    return []


def notify_customer(customer: Customer):
    pass


def notify_all_customers(customer: list[Customer]):
    pass


# ============================================================================
# NEW: Modular Calculation Services for Complex Queries
# ============================================================================

from datetime import timedelta
from dateutil.relativedelta import relativedelta
from django.utils import timezone
from django.core.cache import cache
from apps.tenant_apps.rates.models import Rate
import logging

logger = logging.getLogger(__name__)


class RateCacheService:
    """Centralized rate caching with consistent keys and TTL."""

    CACHE_TTL = 300  # 5 minutes, configurable
    METAL_KEYS = {
        "Gold": "rate_gold_buying",
        "Silver": "rate_silver_buying",
        "Bronze": "rate_bronze_buying",
    }

    @classmethod
    def get_rate(cls, item_type, rate_type="buying_rate"):
        """
        Get fresh or cached rate for metal type.

        Args:
            item_type: 'Gold', 'Silver', or 'Bronze'
            rate_type: 'buying_rate' or 'selling_rate'

        Returns:
            Decimal: The rate value or Decimal(0) if not found
        """
        key = cls.METAL_KEYS.get(item_type)
        if not key:
            logger.warning(f"Unknown item type: {item_type}")
            return Decimal(0)

        # Try cache
        cached = cache.get(key)
        if cached is not None:
            return cached

        # Fetch from DB
        try:
            rate_obj = Rate.objects.filter(metal=item_type).latest("timestamp")
            rate_value = getattr(rate_obj, rate_type, Decimal(0))
        except Rate.DoesNotExist:
            logger.warning(f"No rate found for {item_type}")
            rate_value = Decimal(0)
        except AttributeError:
            logger.error(f"Invalid rate_type: {rate_type}")
            rate_value = Decimal(0)

        # Cache it
        cache.set(key, rate_value, cls.CACHE_TTL)
        return rate_value

    @classmethod
    def get_all_rates(cls):
        """Get all current rates efficiently."""
        return {
            "Gold": cls.get_rate("Gold"),
            "Silver": cls.get_rate("Silver"),
            "Bronze": cls.get_rate("Bronze"),
        }

    @classmethod
    def invalidate(cls):
        """Clear all cached rates."""
        for key in cls.METAL_KEYS.values():
            cache.delete(key)


class InterestCalculationService:
    """Calculate interest and payment metrics consistently."""

    @staticmethod
    def months_between(start_date, end_date=None):
        """
        Calculate months between dates (consistent across app).
        Uses relativedelta for accuracy across varying month lengths.
        """
        end = end_date or timezone.now()
        delta = relativedelta(end, start_date)
        return delta.years * 12 + delta.months

    @staticmethod
    def get_duration_annotations():
        """
        Get annotations for time-based metrics.

        Returns Case expressions for:
        - days_since_created
        - months_since_created
        """
        now = timezone.now()
        return {
            "days_since_created": Case(
                When(
                    release__release_date__isnull=False,
                    then=ExpressionWrapper(
                        F("release__release_date") - F("loan_date"),
                        output_field=DurationField(),
                    ),
                ),
                default=ExpressionWrapper(
                    now - F("loan_date"),
                    output_field=DurationField(),
                ),
                output_field=DurationField(),
            ),
            "months_since_created": Case(
                When(
                    release__release_date__isnull=False,
                    then=ExpressionWrapper(
                        (F("release__release_date__year") - F("loan_date__year")) * 12
                        + (F("release__release_date__month") - F("loan_date__month")),
                        output_field=DecimalField(max_digits=10, decimal_places=2),
                    ),
                ),
                default=ExpressionWrapper(
                    (now.year - F("loan_date__year")) * 12
                    + (now.month - F("loan_date__month")),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
        }

    @staticmethod
    def get_interest_annotations():
        """
        Calculate total interest accrued based on months and interest rate.

        Returns:
        - total_interest: interest * months_since_created
        - total_due: loan_amount + total_interest
        """
        return {
            "total_interest": ExpressionWrapper(
                F("interest") * F("months_since_created"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            "total_due": ExpressionWrapper(
                F("loan_amount") + F("total_interest"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        }


class LoanMetalWeightService:
    """
    Calculate metal weights and pure weights for display.
    DEPRECATED: Generic methods removed. Using GivenLoan/TakenLoan models only.

    Specialized methods for new models:
    - get_given_loan_weight_annotations()
    - get_given_loan_amount_annotations()
    - get_given_loan_value_annotations()
    - get_taken_loan_weight_annotations()
    - get_taken_loan_amount_annotations()
    - get_taken_loan_value_annotations()
    - get_overdue_annotation()
    """

    # ========================================================================
    # Specialized Methods (for GivenLoan/TakenLoan models only)
    # ========================================================================

    @staticmethod
    def get_given_loan_weight_annotations():
        """Weight annotations for GivenLoan (uses loanitems)."""
        return {
            # Gross weights
            "gold_weight": Coalesce(
                Sum("loanitems__weight", filter=Q(loanitems__itemtype="Gold")),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
            "silver_weight": Coalesce(
                Sum("loanitems__weight", filter=Q(loanitems__itemtype="Silver")),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
            "bronze_weight": Coalesce(
                Sum("loanitems__weight", filter=Q(loanitems__itemtype="Bronze")),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
            # Pure weights (weight * purity / 100)
            "pure_gold_weight": Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("loanitems__weight") * F("loanitems__purity") / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    filter=Q(loanitems__itemtype="Gold"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
            "pure_silver_weight": Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("loanitems__weight") * F("loanitems__purity") / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    filter=Q(loanitems__itemtype="Silver"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
            "pure_bronze_weight": Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("loanitems__weight") * F("loanitems__purity") / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    filter=Q(loanitems__itemtype="Bronze"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
        }

    @staticmethod
    def get_taken_loan_weight_annotations():
        """Weight annotations for TakenLoan (uses repledgedloanitems -> original_loanitem)."""
        return {
            # Gross weights from original items
            "gold_weight": Coalesce(
                Sum(
                    "repledgedloanitems__original_loanitem__weight",
                    filter=Q(repledgedloanitems__original_loanitem__itemtype="Gold"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
            "silver_weight": Coalesce(
                Sum(
                    "repledgedloanitems__original_loanitem__weight",
                    filter=Q(repledgedloanitems__original_loanitem__itemtype="Silver"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
            "bronze_weight": Coalesce(
                Sum(
                    "repledgedloanitems__original_loanitem__weight",
                    filter=Q(repledgedloanitems__original_loanitem__itemtype="Bronze"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
            # Pure weights
            "pure_gold_weight": Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("repledgedloanitems__original_loanitem__weight")
                        * F("repledgedloanitems__original_loanitem__purity")
                        / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    filter=Q(repledgedloanitems__original_loanitem__itemtype="Gold"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
            "pure_silver_weight": Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("repledgedloanitems__original_loanitem__weight")
                        * F("repledgedloanitems__original_loanitem__purity")
                        / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    filter=Q(repledgedloanitems__original_loanitem__itemtype="Silver"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
            "pure_bronze_weight": Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("repledgedloanitems__original_loanitem__weight")
                        * F("repledgedloanitems__original_loanitem__purity")
                        / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    filter=Q(repledgedloanitems__original_loanitem__itemtype="Bronze"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
        }

    @staticmethod
    def get_given_loan_amount_annotations():
        """Loan amount annotations for GivenLoan (from loanitems)."""
        return {
            "gold_loanamount": Coalesce(
                Sum("loanitems__loanamount", filter=Q(loanitems__itemtype="Gold")),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            "silver_loanamount": Coalesce(
                Sum("loanitems__loanamount", filter=Q(loanitems__itemtype="Silver")),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            "bronze_loanamount": Coalesce(
                Sum("loanitems__loanamount", filter=Q(loanitems__itemtype="Bronze")),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        }

    @staticmethod
    def get_taken_loan_amount_annotations():
        """Loan amount annotations for TakenLoan (from repledgedloanitems)."""
        return {
            "gold_loanamount": Coalesce(
                Sum(
                    "repledgedloanitems__repledged_loanamount",
                    filter=Q(repledgedloanitems__original_loanitem__itemtype="Gold"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            "silver_loanamount": Coalesce(
                Sum(
                    "repledgedloanitems__repledged_loanamount",
                    filter=Q(repledgedloanitems__original_loanitem__itemtype="Silver"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            "bronze_loanamount": Coalesce(
                Sum(
                    "repledgedloanitems__repledged_loanamount",
                    filter=Q(repledgedloanitems__original_loanitem__itemtype="Bronze"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        }

    @staticmethod
    def get_given_loan_value_annotations():
        """Value annotations for GivenLoan (calculates pure weights and values inline)."""
        rates = RateCacheService.get_all_rates()

        # Calculate pure weights inline since they depend on LoanItem relationships
        gold_value = ExpressionWrapper(
            Sum(
                ExpressionWrapper(
                    F("loanitems__weight") * F("loanitems__purity") / 100,
                    output_field=DecimalField(max_digits=10, decimal_places=3),
                ),
                filter=Q(loanitems__itemtype="Gold"),
            )
            * Value(rates["Gold"]),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )

        silver_value = ExpressionWrapper(
            Sum(
                ExpressionWrapper(
                    F("loanitems__weight") * F("loanitems__purity") / 100,
                    output_field=DecimalField(max_digits=10, decimal_places=3),
                ),
                filter=Q(loanitems__itemtype="Silver"),
            )
            * Value(rates["Silver"]),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )

        bronze_value = ExpressionWrapper(
            Sum(
                ExpressionWrapper(
                    F("loanitems__weight") * F("loanitems__purity") / 100,
                    output_field=DecimalField(max_digits=10, decimal_places=3),
                ),
                filter=Q(loanitems__itemtype="Bronze"),
            )
            * Value(rates["Bronze"]),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )

        return {
            "gold_value": gold_value,
            "silver_value": silver_value,
            "bronze_value": bronze_value,
            "total_current_value": ExpressionWrapper(
                gold_value + silver_value + bronze_value,
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        }

    @staticmethod
    def get_taken_loan_value_annotations():
        """Value annotations for TakenLoan (calculates pure weights and values inline)."""
        rates = RateCacheService.get_all_rates()

        # Calculate pure weights inline from original items
        gold_value = ExpressionWrapper(
            Sum(
                ExpressionWrapper(
                    F("repledgedloanitems__original_loanitem__weight")
                    * F("repledgedloanitems__original_loanitem__purity")
                    / 100,
                    output_field=DecimalField(max_digits=10, decimal_places=3),
                ),
                filter=Q(repledgedloanitems__original_loanitem__itemtype="Gold"),
            )
            * Value(rates["Gold"]),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )

        silver_value = ExpressionWrapper(
            Sum(
                ExpressionWrapper(
                    F("repledgedloanitems__original_loanitem__weight")
                    * F("repledgedloanitems__original_loanitem__purity")
                    / 100,
                    output_field=DecimalField(max_digits=10, decimal_places=3),
                ),
                filter=Q(repledgedloanitems__original_loanitem__itemtype="Silver"),
            )
            * Value(rates["Silver"]),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )

        bronze_value = ExpressionWrapper(
            Sum(
                ExpressionWrapper(
                    F("repledgedloanitems__original_loanitem__weight")
                    * F("repledgedloanitems__original_loanitem__purity")
                    / 100,
                    output_field=DecimalField(max_digits=10, decimal_places=3),
                ),
                filter=Q(repledgedloanitems__original_loanitem__itemtype="Bronze"),
            )
            * Value(rates["Bronze"]),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )

        return {
            "gold_value": gold_value,
            "silver_value": silver_value,
            "bronze_value": bronze_value,
            "total_current_value": ExpressionWrapper(
                gold_value + silver_value + bronze_value,
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        }

    @staticmethod
    def get_overdue_annotation():
        """
        Determine if loan is overdue (current_value < total_due).
        Works for both old and new models.

        Returns:
        - is_overdue: boolean
        """
        return {
            "is_overdue": Case(
                When(total_current_value__lt=F("total_due"), then=True),
                default=False,
                output_field=BooleanField(),
            ),
        }


class DashboardMetricsService:
    """Complex dashboard aggregations for non-performing and long-dead loans."""

    LONG_DEAD_THRESHOLD_MONTHS = 12

    @staticmethod
    def get_non_performing_loans_stats(queryset=None):
        """
        Dashboard: Get stats for non-performing loans (overdue with value < due).

        Returns dict with:
        {
            'count': number of non-performing loans,
            'total_due': sum of amounts due,
            'gold': {'weight': X, 'pure_weight': Y, 'value': Z},
            'silver': {...},
            'bronze': {...},
            'total_collateral_value': sum across all metals,
            'current_rates': {'Gold': X, 'Silver': Y, 'Bronze': Z},
            'rates_timestamp': timezone.now()
        }
        """
        from django.db.models import Count, DecimalField as DF

        if queryset is None:
            queryset = GivenLoan.objects.all()

        # Filter non-performing: unreleased AND overdue (current value < due)
        non_perf = (
            queryset.filter(release__isnull=True)
            .annotate(
                **{
                    **InterestCalculationService.get_duration_annotations(),
                    **InterestCalculationService.get_interest_annotations(),
                    **LoanMetalWeightService.get_itemwise_weight_annotations(),
                    **LoanMetalWeightService.get_itemwise_value_annotations(),
                }
            )
            .filter(
                # Only loans where current value < due
                total_current_value__lt=F("total_due")
            )
        )

        # Aggregate metrics
        metrics = non_perf.aggregate(
            count=Count("id"),
            total_due=Sum("total_due"),
            gold_weight=Sum("gold_weight"),
            silver_weight=Sum("silver_weight"),
            bronze_weight=Sum("bronze_weight"),
            pure_gold_weight=Sum("pure_gold_weight"),
            pure_silver_weight=Sum("pure_silver_weight"),
            pure_bronze_weight=Sum("pure_bronze_weight"),
            gold_value=Sum("gold_value"),
            silver_value=Sum("silver_value"),
            bronze_value=Sum("bronze_value"),
        )

        # Get current rates
        rates = RateCacheService.get_all_rates()

        return {
            "count": metrics["count"] or 0,
            "total_due": metrics["total_due"] or 0,
            "metals": {
                "Gold": {
                    "weight": metrics["gold_weight"] or 0,
                    "pure_weight": metrics["pure_gold_weight"] or 0,
                    "value": metrics["gold_value"] or 0,
                    "rate": rates["Gold"],
                },
                "Silver": {
                    "weight": metrics["silver_weight"] or 0,
                    "pure_weight": metrics["pure_silver_weight"] or 0,
                    "value": metrics["silver_value"] or 0,
                    "rate": rates["Silver"],
                },
                "Bronze": {
                    "weight": metrics["bronze_weight"] or 0,
                    "pure_weight": metrics["pure_bronze_weight"] or 0,
                    "value": metrics["bronze_value"] or 0,
                    "rate": rates["Bronze"],
                },
            },
            "total_collateral_value": (
                (metrics["gold_value"] or 0)
                + (metrics["silver_value"] or 0)
                + (metrics["bronze_value"] or 0)
            ),
            "current_rates": rates,
            "rates_timestamp": timezone.now(),
        }

    @staticmethod
    def get_long_dead_loans_stats(queryset=None, threshold_months=None):
        """
        Dashboard: Get stats for long-dead loans (unreleased for 12+ months).

        Similar structure to non_performing but filters by tenure.
        """
        from django.db.models import Count

        if queryset is None:
            queryset = GivenLoan.objects.all()

        if threshold_months is None:
            threshold_months = DashboardMetricsService.LONG_DEAD_THRESHOLD_MONTHS

        # Filter long-dead: unreleased AND months > threshold
        long_dead = (
            queryset.filter(release__isnull=True)
            .annotate(
                **{
                    **InterestCalculationService.get_duration_annotations(),
                    **InterestCalculationService.get_interest_annotations(),
                    **LoanMetalWeightService.get_itemwise_weight_annotations(),
                    **LoanMetalWeightService.get_itemwise_value_annotations(),
                }
            )
            .filter(months_since_created__gte=threshold_months)
        )

        # Aggregate metrics (same as non_performing)
        metrics = long_dead.aggregate(
            count=Count("id"),
            total_due=Sum("total_due"),
            gold_weight=Sum("gold_weight"),
            silver_weight=Sum("silver_weight"),
            bronze_weight=Sum("bronze_weight"),
            pure_gold_weight=Sum("pure_gold_weight"),
            pure_silver_weight=Sum("pure_silver_weight"),
            pure_bronze_weight=Sum("pure_bronze_weight"),
            gold_value=Sum("gold_value"),
            silver_value=Sum("silver_value"),
            bronze_value=Sum("bronze_value"),
        )

        # Get current rates
        rates = RateCacheService.get_all_rates()

        return {
            "count": metrics["count"] or 0,
            "total_due": metrics["total_due"] or 0,
            "threshold_months": threshold_months,
            "metals": {
                "Gold": {
                    "weight": metrics["gold_weight"] or 0,
                    "pure_weight": metrics["pure_gold_weight"] or 0,
                    "value": metrics["gold_value"] or 0,
                    "rate": rates["Gold"],
                },
                "Silver": {
                    "weight": metrics["silver_weight"] or 0,
                    "pure_weight": metrics["pure_silver_weight"] or 0,
                    "value": metrics["silver_value"] or 0,
                    "rate": rates["Silver"],
                },
                "Bronze": {
                    "weight": metrics["bronze_weight"] or 0,
                    "pure_weight": metrics["pure_bronze_weight"] or 0,
                    "value": metrics["bronze_value"] or 0,
                    "rate": rates["Bronze"],
                },
            },
            "total_collateral_value": (
                (metrics["gold_value"] or 0)
                + (metrics["silver_value"] or 0)
                + (metrics["bronze_value"] or 0)
            ),
            "current_rates": rates,
            "rates_timestamp": timezone.now(),
        }