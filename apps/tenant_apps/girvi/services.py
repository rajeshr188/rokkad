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
from .service_modules.bulk_operations import (
    BulkLoanOperationError,
    LoanBulkDeleteCommand,
    LoanBulkDeleteResult,
    LoanBulkOperationService,
    LoanMergeCommand,
    LoanMergeResult,
)
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
    "BulkLoanOperationError",
    "LoanBulkDeleteCommand",
    "LoanBulkDeleteResult",
    "LoanBulkOperationService",
    "LoanMergeCommand",
    "LoanMergeResult",
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
        logger.info("Created default Girvi series", extra={"license_id": license.pk})
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
        rate_value = cls.get_rate_or_none(item_type, rate_type)
        return rate_value if rate_value is not None else Decimal(0)

    @classmethod
    def get_rate_or_none(cls, item_type, rate_type="buying_rate"):
        """Return the current rate value, or None when rates are not configured."""
        key = cls.METAL_KEYS.get(item_type)
        if not key:
            logger.warning(f"Unknown item type: {item_type}")
            return None

        # Try cache
        cached = cache.get(key)
        if cached is not None:
            return cached if cached > 0 else None

        # Fetch from DB
        try:
            rate_obj = Rate.objects.filter(metal=item_type).latest("timestamp")
            rate_value = getattr(rate_obj, rate_type, Decimal(0))
            if rate_value <= 0:
                logger.warning(f"Non-positive rate found for {item_type}")
                return None
        except Rate.DoesNotExist:
            logger.warning(f"No rate found for {item_type}")
            return None
        except AttributeError:
            logger.error(f"Invalid rate_type: {rate_type}")
            return None

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

    POLICY_MINIMUM_MONTH_PARTIAL_FULL_WITH_GRACE = (
        "MINIMUM_MONTH_PARTIAL_FULL_WITH_3_DAY_GRACE"
    )
    GRACE_DAYS_IN_NEW_MONTH = 3
    POLICY_DESCRIPTION = (
        "Interest has a minimum first-month charge. Partial months count as a full "
        "month, except an additional partial month is not charged when the as-of date "
        "falls in the first 3 calendar days of a month."
    )

    @staticmethod
    def months_between(start_date, end_date=None):
        """
        Calculate chargeable monthly periods between two dates.

        This is the canonical Girvi MVP interest policy:
        - any positive duration has a minimum one-month charge
        - partial months count as a full month
        - the first 3 calendar days of a month are a grace period for adding
          another partial-month charge
        - month boundaries are calculated with relativedelta from the loan date
        """
        end = end_date or timezone.now()
        start_value = start_date.date() if hasattr(start_date, "date") else start_date
        end_value = end.date() if hasattr(end, "date") else end
        if end_value <= start_value:
            return 0

        delta = relativedelta(end_value, start_value)
        completed_months = delta.years * 12 + delta.months
        boundary = start_value + relativedelta(months=completed_months)
        has_partial_month = end_value > boundary

        chargeable_months = completed_months
        if has_partial_month:
            if completed_months == 0:
                chargeable_months = 1
            elif getattr(end_value, "day", 0) <= InterestCalculationService.GRACE_DAYS_IN_NEW_MONTH:
                chargeable_months = completed_months
            else:
                chargeable_months = completed_months + 1

        return max(chargeable_months, 1)

    @classmethod
    def policy(cls):
        return {
            "code": cls.POLICY_MINIMUM_MONTH_PARTIAL_FULL_WITH_GRACE,
            "description": cls.POLICY_DESCRIPTION,
            "grace_days_in_new_month": cls.GRACE_DAYS_IN_NEW_MONTH,
        }

    @classmethod
    def interest_due(cls, principal_interest_amount, start_date, end_date=None):
        months = cls.months_between(start_date, end_date)
        return round(Decimal(str(principal_interest_amount or 0)) * months, 2)

    @staticmethod
    def get_duration_annotations(loan_kind="legacy"):
        """
        Get annotations for time-based metrics.

        Returns Case expressions for:
        - days_since_created
        - months_since_created
        """
        now = timezone.now()
        current_duration = ExpressionWrapper(
            now - F("loan_date"),
            output_field=DurationField(),
        )
        current_months = ExpressionWrapper(
            (now.year - F("loan_date__year")) * 12
            + (now.month - F("loan_date__month")),
            output_field=DecimalField(max_digits=10, decimal_places=2),
        )

        if loan_kind == "taken":
            return {
                "days_since_created": current_duration,
                "months_since_created": current_months,
            }

        return {
            "days_since_created": Case(
                When(
                    release__release_date__isnull=False,
                    then=ExpressionWrapper(
                        F("release__release_date") - F("loan_date"),
                        output_field=DurationField(),
                    ),
                ),
                default=current_duration,
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
                default=current_months,
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
        }

    @staticmethod
    def get_interest_base_annotations(loan_kind="legacy"):
        """
        Principal and monthly interest annotations.

        ``legacy`` preserves the old Loan shape. Refactored loans must pass
        ``given`` or ``taken`` so amounts come from their item tables.
        """
        if loan_kind == "given":
            return {
                "calculated_loan_amount": Coalesce(
                    Sum("loanitems__loanamount"),
                    Value(0),
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                ),
                "calculated_interest_amount": Coalesce(
                    Sum("loanitems__interest"),
                    Value(0),
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                ),
            }

        if loan_kind == "taken":
            interest_expression = ExpressionWrapper(
                F("repledge_history_items__repledged_amount")
                * F("repledge_history_items__loan_item__interestrate")
                / Value(100),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            )
            return {
                "calculated_loan_amount": Coalesce(
                    Sum("repledge_history_items__repledged_amount"),
                    Value(0),
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                ),
                "calculated_interest_amount": Coalesce(
                    Sum(interest_expression),
                    Value(0),
                    output_field=DecimalField(max_digits=15, decimal_places=2),
                ),
            }

        return {}

    @staticmethod
    def get_interest_total_annotations(loan_kind="legacy"):
        """
        Calculate total interest accrued based on months and interest rate.

        Returns:
        - total_interest / total_due for legacy Loan querysets
        - calculated_total_interest / calculated_total_due for refactored querysets
        """
        principal_field = "loan_amount" if loan_kind == "legacy" else "calculated_loan_amount"
        interest_field = (
            "interest" if loan_kind == "legacy" else "calculated_interest_amount"
        )
        total_interest_field = (
            "total_interest" if loan_kind == "legacy" else "calculated_total_interest"
        )
        due_field = "total_due" if loan_kind == "legacy" else "calculated_total_due"
        return {
            total_interest_field: ExpressionWrapper(
                F(interest_field) * F("months_since_created"),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            due_field: ExpressionWrapper(
                F(principal_field) + F(total_interest_field),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        }

    @staticmethod
    def get_interest_annotations(loan_kind="legacy"):
        """Backward-compatible combined interest annotations."""
        return {
            **InterestCalculationService.get_interest_base_annotations(loan_kind),
            **InterestCalculationService.get_interest_total_annotations(loan_kind),
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
        """Weight annotations for TakenLoan from custody repledge history."""
        return {
            # Gross weights from original items
            "gold_weight": Coalesce(
                Sum(
                    "repledge_history_items__loan_item__weight",
                    filter=Q(repledge_history_items__loan_item__itemtype="Gold"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
            "silver_weight": Coalesce(
                Sum(
                    "repledge_history_items__loan_item__weight",
                    filter=Q(repledge_history_items__loan_item__itemtype="Silver"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
            "bronze_weight": Coalesce(
                Sum(
                    "repledge_history_items__loan_item__weight",
                    filter=Q(repledge_history_items__loan_item__itemtype="Bronze"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
            # Pure weights
            "pure_gold_weight": Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("repledge_history_items__loan_item__weight")
                        * F("repledge_history_items__loan_item__purity")
                        / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    filter=Q(repledge_history_items__loan_item__itemtype="Gold"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
            "pure_silver_weight": Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("repledge_history_items__loan_item__weight")
                        * F("repledge_history_items__loan_item__purity")
                        / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    filter=Q(repledge_history_items__loan_item__itemtype="Silver"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            ),
            "pure_bronze_weight": Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("repledge_history_items__loan_item__weight")
                        * F("repledge_history_items__loan_item__purity")
                        / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    filter=Q(repledge_history_items__loan_item__itemtype="Bronze"),
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
        """Loan amount annotations for TakenLoan from custody repledge history."""
        return {
            "gold_loanamount": Coalesce(
                Sum(
                    "repledge_history_items__repledged_amount",
                    filter=Q(repledge_history_items__loan_item__itemtype="Gold"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            "silver_loanamount": Coalesce(
                Sum(
                    "repledge_history_items__repledged_amount",
                    filter=Q(repledge_history_items__loan_item__itemtype="Silver"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            "bronze_loanamount": Coalesce(
                Sum(
                    "repledge_history_items__repledged_amount",
                    filter=Q(repledge_history_items__loan_item__itemtype="Bronze"),
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
            Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("loanitems__weight") * F("loanitems__purity") / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    filter=Q(loanitems__itemtype="Gold"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            )
            * Value(rates["Gold"]),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )

        silver_value = ExpressionWrapper(
            Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("loanitems__weight") * F("loanitems__purity") / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    filter=Q(loanitems__itemtype="Silver"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            )
            * Value(rates["Silver"]),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )

        bronze_value = ExpressionWrapper(
            Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("loanitems__weight") * F("loanitems__purity") / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    filter=Q(loanitems__itemtype="Bronze"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
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
            Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("repledge_history_items__loan_item__weight")
                        * F("repledge_history_items__loan_item__purity")
                        / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    filter=Q(repledge_history_items__loan_item__itemtype="Gold"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            )
            * Value(rates["Gold"]),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )

        silver_value = ExpressionWrapper(
            Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("repledge_history_items__loan_item__weight")
                        * F("repledge_history_items__loan_item__purity")
                        / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    filter=Q(repledge_history_items__loan_item__itemtype="Silver"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
            )
            * Value(rates["Silver"]),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )

        bronze_value = ExpressionWrapper(
            Coalesce(
                Sum(
                    ExpressionWrapper(
                        F("repledge_history_items__loan_item__weight")
                        * F("repledge_history_items__loan_item__purity")
                        / 100,
                        output_field=DecimalField(max_digits=10, decimal_places=3),
                    ),
                    filter=Q(repledge_history_items__loan_item__itemtype="Bronze"),
                ),
                Value(0),
                output_field=DecimalField(max_digits=10, decimal_places=3),
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
    def _loan_kind_for_queryset(queryset):
        model_name = queryset.model.__name__
        if model_name == "GivenLoan":
            return "given"
        if model_name == "TakenLoan":
            return "taken"
        raise TypeError("Dashboard metrics require a GivenLoan or TakenLoan queryset.")

    @staticmethod
    def _dashboard_queryset(queryset):
        loan_kind = DashboardMetricsService._loan_kind_for_queryset(queryset)
        return (
            queryset.unreleased()
            .with_duration_metrics()
            .annotate(
                **InterestCalculationService.get_interest_base_annotations(loan_kind)
            )
            .annotate(
                **InterestCalculationService.get_interest_total_annotations(loan_kind)
            )
            .with_metal_weights()
            .with_current_value()
        )

    @staticmethod
    def _stats_payload(metrics, rates, extra=None):
        payload = {
            "count": metrics["count"] or 0,
            "total_due": metrics["calculated_total_due"] or 0,
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
        if extra:
            payload.update(extra)
        return payload

    @staticmethod
    def _aggregate_dashboard_metrics(queryset):
        fields = [
            "id",
            "calculated_total_due",
            "gold_weight",
            "silver_weight",
            "bronze_weight",
            "pure_gold_weight",
            "pure_silver_weight",
            "pure_bronze_weight",
            "gold_value",
            "silver_value",
            "bronze_value",
        ]
        metrics = {"count": 0, **{field: 0 for field in fields if field != "id"}}

        for row in queryset.values(*fields).iterator():
            metrics["count"] += 1
            for field in fields:
                if field != "id":
                    metrics[field] += row[field] or 0

        return metrics

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
        if queryset is None:
            queryset = GivenLoan.objects.all()

        non_perf = DashboardMetricsService._dashboard_queryset(queryset).filter(
            total_current_value__lt=F("calculated_total_due")
        )

        metrics = DashboardMetricsService._aggregate_dashboard_metrics(non_perf)
        rates = RateCacheService.get_all_rates()
        return DashboardMetricsService._stats_payload(metrics, rates)

    @staticmethod
    def get_long_dead_loans_stats(queryset=None, threshold_months=None):
        """
        Dashboard: Get stats for long-dead loans (unreleased for 12+ months).

        Similar structure to non_performing but filters by tenure.
        """
        if queryset is None:
            queryset = GivenLoan.objects.all()

        if threshold_months is None:
            threshold_months = DashboardMetricsService.LONG_DEAD_THRESHOLD_MONTHS

        long_dead = DashboardMetricsService._dashboard_queryset(queryset).filter(
            months_since_created__gte=threshold_months
        )

        metrics = DashboardMetricsService._aggregate_dashboard_metrics(long_dead)
        rates = RateCacheService.get_all_rates()
        return DashboardMetricsService._stats_payload(
            metrics, rates, {"threshold_months": threshold_months}
        )
