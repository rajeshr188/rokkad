from django.db import models
from django.db.models import Sum
from django.shortcuts import reverse
from django.utils.translation import gettext_lazy as _


class License(models.Model):
    # Fields
    name = models.CharField(max_length=255, verbose_name=_("Name"))
    created = models.DateTimeField(auto_now_add=True, editable=False)
    updated = models.DateTimeField(auto_now=True, editable=False)
    lt = (("PBL", "Pawn Brokers License"), ("GST", "Goods & Service Tax"))
    type = models.CharField(
        max_length=30, choices=lt, default="PBL", verbose_name=_("Type")
    )
    shopname = models.CharField(max_length=30, verbose_name=_("Shop Name"))
    address = models.TextField(max_length=100, verbose_name=_("Address"))
    phonenumber = models.CharField(max_length=30)
    propreitor = models.CharField(max_length=30, verbose_name=_("Propreitor"))
    renewal_date = models.DateField()

    class Meta:
        ordering = ("-created",)

    def __str__(self):
        return "%s" % self.name

    def get_absolute_url(self):
        return reverse("girvi:girvi_license_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("girvi:girvi_license_update", args=(self.pk,))

    def get_series_count(self):
        return self.series_set.count()


class Series(models.Model):
    name = models.CharField(
        max_length=30,
        default="",
        blank=True,
        verbose_name=_("Series Name/prefix"),
    )
    created = models.DateTimeField(auto_now_add=True, editable=False)
    last_updated = models.DateTimeField(auto_now=True)
    max_limit = models.PositiveIntegerField(default=5, verbose_name=_("Max Limit"))
    license = models.ForeignKey(
        License, on_delete=models.CASCADE, verbose_name=_("License")
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))

    class Meta:
        ordering = ("created",)
        unique_together = ["license", "name"]

    def __str__(self):
        return f"Series {self.name}"

    def get_absolute_url(self):
        return reverse("girvi:girvi_license_series_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("girvi:girvi_license_series_update", args=(self.pk,))

    def get_earliest_date(self):
        earliest_loan_date = self.loan_set.aggregate(models.Min("loan_date"))[
            "loan_date__min"
        ]
        return earliest_loan_date

    def get_latest_date(self):
        latest_loan_date = self.loan_set.aggregate(models.Max("loan_date"))[
            "loan_date__max"
        ]
        return latest_loan_date

    def activate(self):
        self.is_active = not self.is_active
        self.save(update_fields=["is_active"])

    def loan_count(self):
        return self.loan_set.unreleased().count()

    def total_loan_amount(self):
        return self.loan_set.unreleased().aggregate(t=Sum("loan_amount"))

    def get_itemwise_loanamount(self):
        return (
            self.loan_set.unreleased()
            .with_details(None, None)
            .with_itemwise_loanamount()
            .total_itemwise_loanamount()
        )

    def get_itemwise_pure_weight(self):
        return self.loan_set.unreleased().with_details(None, None).total_pure_weight()
