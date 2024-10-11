import datetime

from django.core.cache import cache
from django.db import models
from django.db.models import (Case, DecimalField, ExpressionWrapper, F, Func,
                              OuterRef, Q, Subquery, Sum, Value, When)
from django.db.models.functions import (Cast, Ceil, Coalesce, ExtractDay,
                                        ExtractMonth, ExtractYear, Round)
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
        current_time = timezone.now()
        grate, srate, brate = self._get_rates()
        now = timezone.now()
        return self.annotate(
            days_since_created=ExpressionWrapper(
                Case(
                    When(
                        release__release_date__isnull=False,
                        then=ExtractDay(F("release__release_date") - F("loan_date")),
                    ),
                    default=ExtractDay(now - F("loan_date")),
                ),
                output_field=DecimalField(),
            ),
            months_since_created=Ceil(
                ExpressionWrapper(
                    F("days_since_created") / Value(30.44),
                    output_field=DecimalField(),
                )
            ),
            total_interest=ExpressionWrapper(
                Func(
                    (F("interest") * (F("months_since_created") - 1)),
                    function="ROUND",
                    output_field=models.DecimalField(max_digits=10, decimal_places=2),
                ),
                output_field=models.DecimalField(max_digits=10, decimal_places=2),
            ),
            total_due=F("loan_amount") + F("total_interest"),
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
                    + (F("pure_silver_weight") * srate.buying_rate)
                    + (F("pure_bronze_weight") * brate.buying_rate),
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
        current_time = timezone.now()
        grate, srate, brate = self._get_rates()

        return self.aggregate(
            gold=Round(Sum("pure_gold_weight") * grate.buying_rate, 2),
            silver=Round(Sum("pure_silver_weight") * srate.buying_rate, 2),
            bronze=Round(Sum("pure_bronze_weight") * brate.buying_rate, 2),
        )

    def total_loanamount(self):
        return self.aggregate(total=Sum("loan_amount"))


class LoanManager(models.Manager):
    def get_queryset(self):
        return LoanQuerySet(self.model, using=self._db).select_related(
            "series", "release", "customer"
        )

    def released(self):
        return self.get_queryset().released()

    def unreleased(self):
        return self.get_queryset().unreleased()

    def with_details(self, grate, srate, brate):
        return self.get_queryset().with_details(grate, srate, brate)

    def with_itemwise_loanamount(self):
        return self.get_queryset().with_itemwise_loanamount()

    def total_itemwise_loanamount(self):
        return self.get_queryset().total_itemwise_loanamount()

    def with_total_value(self):
        return self.get_queryset().aggregate(total_value=Sum("current_value"))

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


class ReleasedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(release__isnull=False)


class UnReleasedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(release__isnull=True)
