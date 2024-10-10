import datetime

from django.core.cache import cache
from django.db import models
from django.db.models import (
    Case,
    DecimalField,
    ExpressionWrapper,
    F,
    Func,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import (
    Coalesce,
    ExtractDay,
    ExtractMonth,
    ExtractYear,
    Round,
)
from django.utils import timezone

from apps.tenant_apps.rates.models import Rate

"""
    each row shall have
        itemwise weight
        itemwise pure_weight
        itemwise loanamount
        no_of_months
        total_interest
        due
        current_value
        is_overdue
    total weight,pureweight,itemwise_loanamount,loanamount,currentvalue,itemwise currentvalue

"""


class LoanQuerySet(models.QuerySet):
    def released(self):
        return self.filter(release__isnull=False)

    def unreleased(self):
        return self.filter(release__isnull=True)

    # ------------------chatgpt suggestion------------------
    def months_since(self):
        # Annotate each loan with the number of months since its creation
        months_since_annotation = ExpressionWrapper(
            (ExtractYear(timezone.now()) - ExtractYear(F("loan_date"))) * 12
            + (ExtractMonth(timezone.now()) - ExtractMonth(F("loan_date"))),
            output_field=DecimalField(),
        )

        return self.annotate(months_since=months_since_annotation)

    def months_since_or_to_release(self):
        # Calculate months since loan_date or between loan_date and release_date with date precision and rounding
        months_since_annotation = Case(
            # If release_date is not None, calculate months between loan_date and release_date with day precision
            When(
                release__isnull=False,
                then=ExpressionWrapper(
                    (
                        (
                            ExtractYear(F("release__release_date"))
                            - ExtractYear(F("loan_date"))
                        )
                        * 12
                        + (
                            ExtractMonth(F("release__release_date"))
                            - ExtractMonth(F("loan_date"))
                        )
                        + (
                            ExtractDay(F("release__release_date"))
                            - ExtractDay(F("loan_date"))
                        )
                        / 30.0
                    ),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                ),
            ),
            # Default case: Calculate months since loan_date to now with day precision
            default=ExpressionWrapper(
                (
                    (ExtractYear(timezone.now()) - ExtractYear(F("loan_date"))) * 12
                    + (ExtractMonth(timezone.now()) - ExtractMonth(F("loan_date")))
                    + (timezone.now().day - ExtractDay(F("loan_date"))) / 30.0
                ),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
        )
        # Custom annotation to calculate months with date precision, rounding up if 1 month and 1 or more days
        # months_since_annotation = Case(
        #     # If release_date is not None, calculate and round months between loan_date and release_date
        #     When(release_date__isnull=False,
        #         then=ExpressionWrapper(
        #             RawSQL(
        #                 "CEIL(((EXTRACT(YEAR FROM release__release_date) - EXTRACT(YEAR FROM loan_date)) * 12 + "
        #                 "(EXTRACT(MONTH FROM release__release_date) - EXTRACT(MONTH FROM loan_date)) + "
        #                 "(EXTRACT(DAY FROM release__release_date) - EXTRACT(DAY FROM loan_date)) / 30.0))",
        #                 ()
        #             ),
        #             output_field=IntegerField()
        #         )),
        #     # Default case: Calculate and round months since loan_date to now
        #     default=ExpressionWrapper(
        #         RawSQL(
        #             "CEIL(((EXTRACT(YEAR FROM NOW()) - EXTRACT(YEAR FROM loan_date)) * 12 + "
        #             "(EXTRACT(MONTH FROM NOW()) - EXTRACT(MONTH FROM loan_date)) + "
        #             "(EXTRACT(DAY FROM NOW()) - EXTRACT(DAY FROM loan_date)) / 30.0))",
        #             ()
        #         ),
        #         output_field=IntegerField()
        #     )
        # )

        return self.annotate(months_since=months_since_annotation)

    def with_interest_calculated(self):
        # First, ensure each loan is annotated with months_since
        loans_with_months_since = self.months_since_or_to_release()
        # Then, calculate interest due using the annotated months_since
        interest_due = ExpressionWrapper(
            Func(
                (F("months_since") * F("interest")),
                function="ROUND",
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
            output_field=DecimalField(),
        )
        return loans_with_months_since.annotate(total_interest=interest_due)

    def with_due(self):
        with_interest_calculated = self.with_interest_calculated()
        total_due = ExpressionWrapper(
            F("loan_amount") + F("total_interest"), output_field=DecimalField()
        )
        return with_interest_calculated.annotate(total_due=total_due)

    def with_aggregate_weight_by_itemtype(self):
        return self.annotate(
            total_weight_gold=Coalesce(
                Sum(
                    Case(
                        When(loanitems__item_type="Gold", then="loanitems__weight"),
                        default=Value(0),
                        output_field=models.DecimalField(),
                    )
                ),
                Value(0),
            ),
            total_weight_silver=Coalesce(
                Sum(
                    Case(
                        When(loanitems__item_type="Silver", then="loanitems__weight"),
                        default=Value(0),
                        output_field=models.DecimalField(),
                    )
                ),
                Value(0),
            ),
            total_weight_bronze=Coalesce(
                Sum(
                    Case(
                        When(loanitems__item_type="Bronze", then="loanitems__weight"),
                        default=Value(0),
                        output_field=models.DecimalField(),
                    )
                ),
                Value(0),
            ),
        )

    def with_aggregate_pure_weight_by_itemtype(self):
        return self.annotate(
            total_pure_weight_gold=Coalesce(
                Sum(
                    Case(
                        When(
                            loanitems__item_type="Gold",
                            then="loanitems__weight" * "loanitems__purity" / 100,
                        ),
                        default=Value(0),
                        output_field=models.DecimalField(),
                    )
                ),
                Value(0),
            ),
            total_pure_weight_silver=Coalesce(
                Sum(
                    Case(
                        When(
                            loanitems__item_type="Silver",
                            then="loanitems__weight" * "loanitems__purity" / 100,
                        ),
                        default=Value(0),
                        output_field=models.DecimalField(),
                    )
                ),
                Value(0),
            ),
            total_pure_weight_bronze=Coalesce(
                Sum(
                    Case(
                        When(
                            loanitems__item_type="Bronze",
                            then="loanitems__weight" * "loanitems__purity" / 100,
                        ),
                        default=Value(0),
                        output_field=models.DecimalField(),
                    )
                ),
                Value(0),
            ),
        )

    # -------------------------------------------------------
    def with_total_interest(self):
        # today = datetime.date.today()
        # return self.annotate(
        #     no_of_months=ExpressionWrapper(
        #         today.month- F("loan_date__month")
        #         + 12 * (today.year - F("loan_date__year")),
        #         output_field=DecimalField(decimal_places=2),
        #     ),
        #     loan_interest=F("interest") * F("no_of_months"),
        # ).annotate(Sum("loan_interest"))
        # First, ensure each loan is annotated with months_since
        loans_with_months_since = self.months_since_or_to_release()
        # Then, calculate interest due using the annotated months_since
        interest_due = ExpressionWrapper(
            # F('months_since') * F('interest_rate') * F('loan_amount') / 100,
            Func(
                (F("interest") * F("months_since")),
                function="ROUND",
                output_field=models.DecimalField(max_digits=10, decimal_places=2),
            ),
            output_field=DecimalField(),
        )
        # return loans_with_months_since.annotate(interest_due=interest_due)
        return loans_with_months_since.annotate(total_interest=interest_due)

    def with_details(self, grate=None, srate=None):
        current_time = timezone.now()
        grate = cache.get("gold_rate")
        srate = cache.get("silver_rate")

        # If the rates are not in the cache, fetch them from the database
        if not (grate and srate):
            latest_rate = Rate.objects.filter(
                metal__in=[Rate.Metal.GOLD, Rate.Metal.SILVER]
            ).order_by("-timestamp")
            grate = grate or latest_rate.filter(metal=Rate.Metal.GOLD).first()
            srate = srate or latest_rate.filter(metal=Rate.Metal.SILVER).first()

            # Store the rates in the cache for 5 minutes
            cache.set("gold_rate", grate, 300)
            cache.set("silver_rate", srate, 300)
        with_due = self.with_due()
        return with_due.annotate(
            # months_since_created=ExpressionWrapper(
            #     Case(
            #         When(Q(release__isnull=True),
            #                 then=Func(
            #                     (ExtractYear(current_time) - ExtractYear(F("loan_date")))* 12
            #                     + (ExtractMonth(current_time)- ExtractMonth(F("loan_date")))
            #                     + (current_time.day - F("loan_date__day")) / 30,
            #                     function="ROUND",
            #                     output_field=models.DecimalField(
            #                         max_digits=10, decimal_places=2),
            #                     ),),
            #         When(
            #             Q(release__isnull=False),
            #             then=Func(
            #                     (ExtractYear(F("release__release_date"))- ExtractYear(F("loan_date")))* 12
            #                     + (ExtractMonth(F("release__release_date"))- ExtractMonth(F("loan_date")))
            #                     + (F("release__release_date__day") - F("loan_date__day"))/ 30,
            #                     function="ROUND",
            #                     output_field=models.DecimalField(
            #                         max_digits=10, decimal_places=2),
            #                 ),
            #             ),
            #         default=Value(0),
            #         output_field=models.DecimalField(max_digits=10, decimal_places=2),
            #     ),
            #     output_field=models.DecimalField(max_digits=10, decimal_places=2),
            # ),
            total_gold_weight=Sum(
                Case(
                    When(loanitems__itemtype="Gold", then=F("loanitems__weight")),
                    default=Value(0),
                    output_field=models.DecimalField(max_digits=10, decimal_places=2),
                )
            ),
            total_silver_weight=Sum(
                Case(
                    When(loanitems__itemtype="Silver", then=F("loanitems__weight")),
                    default=Value(0),
                    output_field=models.DecimalField(max_digits=10, decimal_places=2),
                )
            ),
            total_bronze_weight=Sum(
                Case(
                    When(loanitems__itemtype="Bronze", then=F("loanitems__weight")),
                    default=Value(0),
                    output_field=models.DecimalField(max_digits=10, decimal_places=2),
                )
            ),
            pure_gold_weight=Sum(
                Coalesce(
                    Case(
                        When(
                            loanitems__itemtype="Gold",
                            then=F("loanitems__weight") * F("loanitems__purity") / 100,
                        )
                    ),
                    Value(0),
                ),
                output_field=models.DecimalField(max_digits=10, decimal_places=2),
            ),
            pure_silver_weight=Sum(
                Coalesce(
                    Case(
                        When(
                            loanitems__itemtype="Silver",
                            then=F("loanitems__weight") * F("loanitems__purity") / 100,
                        )
                    ),
                    Value(0),
                ),
                output_field=models.DecimalField(max_digits=10, decimal_places=2),
            ),
            pure_bronze_weight=Sum(
                Coalesce(
                    Case(
                        When(
                            loanitems__itemtype="Bronze",
                            then=F("loanitems__weight") * F("loanitems__purity") / 100,
                        )
                    ),
                    Value(0),
                ),
                output_field=models.DecimalField(max_digits=10, decimal_places=2),
            ),
            current_value=Round(
                ExpressionWrapper(
                    (F("pure_gold_weight") * grate.buying_rate)
                    + (F("pure_silver_weight") * srate.buying_rate),
                    output_field=DecimalField(max_digits=10, decimal_places=2),
                )
            ),
            is_overdue=Case(
                When(total_due__gt=F("current_value"), then=True),
                default=False,
                output_field=models.BooleanField(),
            ),
            worth=ExpressionWrapper(
                F("current_value") - F("total_due"),
                output_field=DecimalField(decimal_places=2, max_digits=10),
            ),
        )

    def with_itemwise_loanamount(self):
        return self.annotate(
            total_gold_la=Sum(
                Case(
                    When(loanitems__itemtype="Gold", then=F("loanitems__loanamount")),
                    default=Value(0),
                    output_field=models.DecimalField(max_digits=10, decimal_places=2),
                )
            ),
            total_silver_la=Sum(
                Case(
                    When(loanitems__itemtype="Silver", then=F("loanitems__loanamount")),
                    default=Value(0),
                    output_field=models.DecimalField(max_digits=10, decimal_places=2),
                )
            ),
            total_bronze_la=Sum(
                Case(
                    When(loanitems__itemtype="Bronze", then=F("loanitems__loanamount")),
                    default=Value(0),
                    output_field=models.DecimalField(max_digits=10, decimal_places=2),
                )
            ),
            total_la=F("total_gold_la") + F("total_silver_la") + F("total_bronze_la"),
        )

    def total_itemwise_loanamount(self):
        return self.aggregate(
            gold_loanamount=Sum("total_gold_la"),
            silver_loanamount=Sum("total_silver_la"),
            bronze_loanamount=Sum("total_bronze_la"),
        )

    def total_current_value(self):
        return self.aggregate(total=Sum("current_value"))

    def total_weight(self):
        return self.aggregate(
            gold=Sum("total_gold_weight"),
            silver=Sum("total_silver_weight"),
            bronze=Sum("total_bronze_weight"),
        )

    def total_pure_weight(self):
        return self.aggregate(
            gold=Round(Sum("pure_gold_weight"), 2),
            silver=Round(Sum("pure_silver_weight"), 2),
            bronze=Round(Sum("pure_bronze_weight")),
        )

    def itemwise_value(self):
        latest_gold_rate = (
            Rate.objects.filter(metal=Rate.Metal.GOLD).order_by("-timestamp").first()
        )
        latest_silver_rate = (
            Rate.objects.filter(metal=Rate.Metal.SILVER).order_by("-timestamp").first()
        )
        return self.aggregate(
            gold=Round(Sum("pure_gold_weight") * latest_gold_rate.buying_rate, 2),
            silver=Round(Sum("pure_silver_weight") * latest_silver_rate.buying_rate, 2),
        )

    def total_loanamount(self):
        return self.aggregate(total=Sum("loan_amount"))


class LoanManager(models.Manager):
    def get_queryset(self):
        return (
            LoanQuerySet(self.model, using=self._db)
            .select_related("series", "release", "customer")
            .prefetch_related("loanitems")
        )

    def released(self):
        return self.get_queryset().released()

    def unreleased(self):
        return self.get_queryset().unreleased()

    def with_aggregate_weight_by_itemtype(self):
        return self.get_queryset().with_aggregate_weight_by_itemtype()

    def with_aggregate_pure_weight_by_itemtype(self):
        return self.get_queryset().with_aggregate_pure_weight_by_itemtype()

    def with_details(self, grate, srate):
        return self.get_queryset().with_details(grate, srate)

    def with_itemwise_loanamount(self):
        return self.get_queryset().with_itemwise_loanamount()

    def total_itemwise_loanamount(self):
        return self.get_queryset().total_itemwise_loanamount()

    def with_total_value(self):
        return self.get_queryset().aggregate(total_value=Sum("current_value"))

    def total_loanamount(self):
        return self.get_queryset().aggregate(total=Sum("loan_amount"))

    def total_weight(self):
        return self.get_queryset().total_weight()

    def total_pure_weight(self):
        return self.get_queryset().total_pure_weight()


class ReleasedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(release__isnull=False)


class UnReleasedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(release__isnull=True)
