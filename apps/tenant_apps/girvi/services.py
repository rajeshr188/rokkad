import logging
from collections import Counter
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
from .service_modules.creation import (
    LoanCreateCommand,
    LoanCreatePreview,
    LoanCreateResult,
    LoanCreationService,
    LoanItemCreateInput,
)
from .service_modules.id_generation import LoanIDGenerator, ReleaseIDGenerator
from .service_modules.release_lifecycle import ReleaseLifecycleService
from .service_modules.renewal import (
    LoanRenewalCommand,
    LoanRenewalPreview,
    LoanRenewalResult,
    LoanRenewalService,
)
from .service_modules.transitions import LoanTransitionService

# NOTE: LoanItem, LoanPayment, and License imported locally in methods to avoid circular import
# NOTE: GivenLoan is imported locally in methods to avoid circular import
# See usage in LoanSplitService.split_items() and LoanMergeService.merge()

logger = logging.getLogger(__name__)

__all__ = [
    "LoanCreateCommand",
    "LoanCreatePreview",
    "LoanCreateResult",
    "LoanCreationService",
    "LoanItemCreateInput",
    "ReleaseLifecycleService",
    "LoanIDGenerator",
    "ReleaseIDGenerator",
    "LoanTransitionService",
    "LoanRenewalCommand",
    "LoanRenewalPreview",
    "LoanRenewalResult",
    "LoanRenewalService",
]


class BulkReleaseService:
    COMMIT_POLICY_STRICT = "strict"
    COMMIT_POLICY_PARTIAL = "partial"
    DEFAULT_COMMIT_POLICY = COMMIT_POLICY_STRICT

    @staticmethod
    def parse_selected_ids(raw_ids):
        cleaned = []
        for value in raw_ids:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                cleaned.append(parsed)
        return list(dict.fromkeys(cleaned))

    @staticmethod
    def build_summary(loans):
        return {
            "total_loans": len(loans),
            "total_principal": sum(loan.get_loan_amount for loan in loans),
            "total_interest": sum(loan.interest_due() for loan in loans),
            "total_amount": sum(loan.total_due for loan in loans),
        }

    @classmethod
    def build_bulk_form(cls, raw_selected_ids=None):
        from .forms import BulkReleaseForm

        selected_ids = cls.parse_selected_ids(raw_selected_ids or [])
        initial = {"date": timezone.now().strftime("%Y-%m-%dT%H:%M")}
        if selected_ids:
            initial["loans"] = GivenLoan.objects.filter(
                release__isnull=True, id__in=selected_ids
            ).values_list("id", flat=True)
        return BulkReleaseForm(initial=initial)

    @classmethod
    def build_preview_context(cls, loans, release_date):
        from .forms import build_release_formset

        Release = apps.get_model("girvi", "Release")

        loans = list(loans)
        formset_initial_data = [
            {
                "loan": loan,
                "release_date": release_date,
                "released_by": loan.borrower,
                "release_amount": loan.total_due,
            }
            for loan in loans
        ]
        preview_formset_class = build_release_formset(extra=len(formset_initial_data))
        formset = preview_formset_class(
            queryset=Release.objects.none(), initial=formset_initial_data
        )
        return cls.build_review_context(
            formset,
            cls.build_summary(loans),
            commit_policy=cls.DEFAULT_COMMIT_POLICY,
        )

    @classmethod
    def bind_submit_formset(cls, post_data):
        from .forms import ReleaseFormSet

        Release = apps.get_model("girvi", "Release")
        return ReleaseFormSet(post_data, queryset=Release.objects.none())

    @classmethod
    def extract_formset_loan_ids(cls, post_data):
        try:
            total_forms = int(post_data.get("form-TOTAL_FORMS", 0))
        except (TypeError, ValueError):
            return []

        loan_ids = []
        for index in range(total_forms):
            value = post_data.get(f"form-{index}-loan")
            if value:
                loan_ids.append(value)

        return cls.parse_selected_ids(loan_ids)

    @staticmethod
    def has_row_errors(formset):
        for form in formset.forms:
            delete_key = form.add_prefix("DELETE")
            if form.data.get(delete_key) in {True, "True", "true", "on", "1"}:
                continue
            if getattr(form, "cleaned_data", None) and form.cleaned_data.get("DELETE"):
                continue
            if form.errors:
                return True
        return False

    @classmethod
    def build_review_context(
        cls,
        formset,
        summary,
        has_blocking_errors=False,
        commit_policy=None,
    ):
        resolved_policy = cls._normalize_commit_policy(commit_policy)
        return {
            "formset": formset,
            "summary": summary,
            "has_row_errors": cls.has_row_errors(formset),
            "has_blocking_errors": has_blocking_errors,
            "commit_policy": resolved_policy,
        }

    @classmethod
    def get_summary_for_post(cls, post_data):
        selected_loan_ids = cls.extract_formset_loan_ids(post_data)
        loans = list(
            GivenLoan.objects.filter(id__in=selected_loan_ids).select_related("borrower")
        )
        summary = cls.build_summary(loans) if loans else None
        return selected_loan_ids, summary

    @classmethod
    def commit_formset(cls, formset, user):
        return cls.commit_formset_with_policy(
            formset, user, commit_policy=cls.DEFAULT_COMMIT_POLICY
        )

    @classmethod
    def _normalize_commit_policy(cls, commit_policy):
        if commit_policy in {cls.COMMIT_POLICY_STRICT, cls.COMMIT_POLICY_PARTIAL}:
            return commit_policy
        return cls.DEFAULT_COMMIT_POLICY

    @classmethod
    def commit_formset_with_policy(cls, formset, user, commit_policy=None):
        commit_policy = cls._normalize_commit_policy(commit_policy)
        selected_loan_ids, summary = cls.get_summary_for_post(formset.data)

        if not formset.is_valid():
            return {
                "success": False,
                "commit_policy": commit_policy,
                **cls.build_review_context(
                    formset,
                    summary,
                    has_blocking_errors=bool(formset.non_form_errors()),
                    commit_policy=commit_policy,
                ),
            }

        with transaction.atomic():
            locked_loans = GivenLoan.objects.select_for_update().filter(
                id__in=selected_loan_ids
            )
            released_ids = set(
                locked_loans.filter(release__isnull=False).values_list("id", flat=True)
            )

            if released_ids and commit_policy == cls.COMMIT_POLICY_STRICT:
                formset._non_form_errors = formset.error_class(
                    [
                        "Some selected loans were released by another process. "
                        "Please refresh and try again."
                    ]
                )
                return {
                    "success": False,
                    "commit_policy": commit_policy,
                    **cls.build_review_context(
                        formset,
                        summary,
                        has_blocking_errors=True,
                        commit_policy=commit_policy,
                    ),
                }

            instances = []
            skipped_released_count = 0
            for form in formset.forms:
                if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                    continue

                loan = form.cleaned_data.get("loan")
                if (
                    loan
                    and loan.id in released_ids
                    and commit_policy == cls.COMMIT_POLICY_PARTIAL
                ):
                    skipped_released_count += 1
                    form.add_error(
                        "loan", "This loan was already released. Skipped in partial mode."
                    )
                    continue

                instances.append(
                    ReleaseLifecycleService.create_release(
                        loan=form.cleaned_data["loan"],
                        created_by=user,
                        release_date=form.cleaned_data["release_date"],
                        released_by=form.cleaned_data.get("released_by"),
                    )
                )

        if commit_policy == cls.COMMIT_POLICY_PARTIAL and skipped_released_count:
            if not instances:
                formset._non_form_errors = formset.error_class(
                    [
                        "All selected loans were stale at submit time. "
                        "No releases were created."
                    ]
                )
                return {
                    "success": False,
                    "commit_policy": commit_policy,
                    **cls.build_review_context(
                        formset,
                        summary,
                        has_blocking_errors=True,
                        commit_policy=commit_policy,
                    ),
                }

            return {
                "success": True,
                "instances": instances,
                "commit_policy": commit_policy,
                "skipped_released_count": skipped_released_count,
            }

        return {
            "success": True,
            "instances": instances,
            "commit_policy": commit_policy,
            "skipped_released_count": 0,
        }

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
    """
    Get cumulative loan amounts over time.
    Note: For GivenLoan, we need to aggregate through LoanItem.
    """
    from django.db.models import OuterRef, Subquery
    from .models import LoanItem

    # Subquery to get total loan amount for each GivenLoan
    loan_amount_subquery = (
        LoanItem.objects.filter(loan=OuterRef("pk"))
        .values("loan")
        .annotate(total=Sum("loanamount"))
        .values("total")
    )

    loans = (
        GivenLoan.objects.unreleased()
        .annotate(loan_amount=Subquery(loan_amount_subquery))
        .annotate(cumsum=Window(Sum("loan_amount"), order_by=F("loan_date").asc()))
        .values("loan_date__date", "cumsum")
        .order_by("loan_date")
    )
    return loans


# def get_average_loan_instance_per_day():
#     # Get the total number of distinct Loan instances
#     total_loans = Loan.objects.filter(series__is_active=True).count()

#     # Get the earliest and latest Loan instance
#     earliest_loan = (
#         Loan.objects.filter(series__is_active=True).order_by("loan_date").first()
#     )
#     latest_loan = (
#         Loan.objects.filter(series__is_active=True).order_by("-loan_date").first()
#     )

#     # If there are no Loan instances, return 0
#     if earliest_loan is None or latest_loan is None:
#         return 0

#     # Calculate the number of days between the earliest and latest Loan instance
#     num_days = (latest_loan.loan_date - earliest_loan.loan_date).days + 1

#     # Calculate the average number of Loan instances per day
#     average_loan_instance_per_day = total_loans / num_days

#     return round(average_loan_instance_per_day, 0)

from django.db.models import Count
from django.db.models.functions import TruncDate


def get_average_loan_instance_per_day():
    # Get the count of loans per day
    loans_per_day = (
        GivenLoan.objects.annotate(day=TruncDate("loan_date"))
        .values("day")
        .annotate(count=Count("id"))
        .aggregate(total_loans=Sum("count"), total_days=Count("day", distinct=True))
    )

    # If there are no loans, return 0
    if not loans_per_day["total_loans"]:
        return 0

    # Calculate average only for days that actually had loans
    average = loans_per_day["total_loans"] / loans_per_day["total_days"]

    return round(average, 0)


def get_loan_counts_grouped():
    # Query to get the loan counts for each customer
    loan_counts = (
        GivenLoan.objects.unreleased()
        .values(
            "customer__id", "customer__firstname", "customer__lastname"
        )  # Group by customer
        .annotate(loan_count=Count("id"))
        .order_by("loan_count")  # Count the number of loans
    )

    # Use Counter to group customers by loan count
    grouped_loan_counts = Counter(
        loan_count for loan_count in loan_counts.values_list("loan_count", flat=True)
    )
    # Convert the Counter to a list of tuples for easier iteration in the template
    grouped_loan_counts_list = list(grouped_loan_counts.items())

    return grouped_loan_counts_list


def get_loans_by_year():
    loans_by_year = (
        GivenLoan.objects.annotate(
            year=ExtractYear("loan_date"),
            has_release=Case(
                When(release__isnull=False, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
        )  # Extract year from loan start_date and check if there is a release
        .values("year")
        .annotate(
            loans_count=Count("id"),  # Count all loans
            unreleased_count=Count(
                "id", filter=Q(has_release=0)
            ),  # Count loans without a release
        )
        .order_by("year")
    )
    return loans_by_year


def get_unreleased_loans_by_year():
    data = (
        GivenLoan.objects.unreleased()
        .annotate(year=ExtractYear("loan_date"))  # Extract year from start_date
        .values("year")  # Group by year
        .annotate(release_count=Count("id"))  # Count the number of loans
        .order_by("year")
    )
    return data


def get_loanamount_by_itemtype():
    from .models import LoanItem  # Import here to avoid circular imports

    query = (
        LoanItem.objects.filter(loan__release__isnull=True)
        .values("itemtype")
        .annotate(total_loan_amount=Sum("loanamount"))  # Group by loan type
    )
    return query


from django.db.models import DecimalField, ExpressionWrapper


def get_itemtype_averages():
    from .models import LoanItem  # Import here to avoid circular imports

    """Calculate average loan amount per gram for each item type."""
    try:
        stats = (
            LoanItem.objects.filter(loan__release__isnull=True, loan__loan_type="Given")
            .values("itemtype")
            .annotate(
                total_weight=Coalesce(Sum("weight"), Decimal("0.00")),
                total_amount=Coalesce(Sum("loanamount"), Decimal("0.00")),
            )
            .annotate(
                avg_per_gram=Case(
                    When(
                        Q(total_weight__gt=0),  # Compare annotated field instead of Sum
                        then=ExpressionWrapper(
                            F("total_amount") / F("total_weight"),
                            output_field=DecimalField(max_digits=10, decimal_places=2),
                        ),
                    ),
                    default=Value(Decimal("0.00")),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
                count=Count("id"),
            )
            .order_by("itemtype")
        )

        return {
            item["itemtype"]: {
                "avg_per_gram": item["avg_per_gram"],
                "total_weight": item["total_weight"],
                "total_amount": item["total_amount"],
                "count": item["count"],
            }
            for item in stats
        }
    except Exception as e:
        print(f"Error calculating averages: {e}")
        return {}


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
        from .models import GivenLoan

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
        # First item always stays
        first_item = self.loan.loanitems.earliest("id")

        if item_ids:
            # Split specific items only
            items = self.loan.loanitems.filter(id__in=item_ids).exclude(
                id=first_item.id
            )
        else:
            # Split everything except first
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
        from .models import GivenLoan, LoanChangeLog

        new_loans = []

        with transaction.atomic():
            for item in items_to_split:
                # Create new loan with same parameters
                new_loan = GivenLoan.objects.create(
                    borrower=self.loan.borrower,
                    loan_date=self.loan.loan_date,
                    series=self.loan.series,
                    tenure=self.loan.tenure,
                    status=self.loan.status,
                    interest_type=self.loan.interest_type,
                    created_by=self.created_by,
                )

                # Move item to new loan
                item.loan = new_loan
                item.save(update_fields=["loan"])

                # Log the split
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
        from .models import GivenLoan

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

        Args:
            source_loans: List of loans to validate

        Raises:
            ValidationError: If validation fails
        """
        from django.core.exceptions import ValidationError
        from .models import GivenLoan

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
        """
        Move all items from source loans to target.

        Args:
            source_loans: Loans whose items to move
        """
        from .models import LoanChangeLog

        with transaction.atomic():
            for loan in source_loans:
                # Move all items in one query
                item_count = loan.loanitems.count()
                loan.loanitems.update(loan=self.target_loan)

                # Log merge
                LoanChangeLog.objects.create(
                    loan=self.target_loan,
                    source=f"Merged loan {loan.loan_id}",
                    target=f"Into {self.target_loan.loan_id}",
                    author=self.merged_by,
                    diff=f"Merged {item_count} items",
                )

    def _delete_sources(self, source_loans):
        """
        Delete source loans after items moved.

        Args:
            source_loans: Loans to delete
        """
        with transaction.atomic():
            for loan in source_loans:
                loan.delete()


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