from decimal import Decimal
from django.db import models
from django.core.exceptions import ValidationError
from django.shortcuts import reverse
from django.utils import timezone
from .custody_tracking import LoanItemWithCustody
from apps.tenant_apps.dea.models import JournalEntry
from django.contrib.contenttypes.fields import GenericRelation
import logging

logger = logging.getLogger(__name__)


class ItemType(models.TextChoices):
    """Collateral item types"""

    GOLD = "Gold", "Gold"
    SILVER = "Silver", "Silver"
    BRONZE = "Bronze", "Bronze"


class LoanItem(LoanItemWithCustody):
    loan = models.ForeignKey(
        "girvi.GivenLoan", on_delete=models.CASCADE, related_name="loanitems"
    )
    item = models.ForeignKey(
        "product.ProductVariant", on_delete=models.SET_NULL, null=True, blank=True
    )
    pic = models.ImageField(upload_to="loan_pics/", null=True, blank=True)
    itemtype = models.CharField(
        max_length=30, choices=ItemType.choices, default=ItemType.GOLD
    )
    quantity = models.PositiveIntegerField(default=1)
    weight = models.DecimalField(max_digits=10, decimal_places=3)
    purity = models.DecimalField(
        max_digits=10, decimal_places=2, default=75, blank=True, null=True
    )
    loanamount = models.DecimalField(max_digits=10, decimal_places=2)
    interestrate = models.DecimalField(max_digits=10, decimal_places=2)
    interest = models.DecimalField(
        max_digits=10, decimal_places=2, default=0, blank=True, null=True
    )
    itemdesc = models.TextField(
        max_length=100, blank=True, null=True, verbose_name="Item"
    )
    journal_entries = GenericRelation(JournalEntry, related_query_name="loanitem_doc")

    class Meta:
        ordering = (
            "id",
            "loan",
        )
        get_latest_by = "id"
        indexes = [
            # Most common: filter by loan and itemtype together
            models.Index(fields=["loan", "itemtype"], name="loanitem_loan_type_idx"),
            # Filter by itemtype alone (for aggregations across all loans)
            models.Index(fields=["itemtype"], name="loanitem_type_idx"),
            # Filter by custody status (for available items queries)
            models.Index(fields=["custody_status"], name="loanitem_custody_idx"),
            # Combined custody and itemtype lookups
            models.Index(
                fields=["custody_status", "itemtype"], name="loanitem_custody_type_idx"
            ),
        ]

    def __str__(self):
        return (
            f"{self.loan.loan_id}:₹{self.loanamount}({self.itemdesc} - {self.quantity})"
        )

    def get_absolute_url(self):
        # return self.loan.get_absolute_url()
        return reverse("girvi:girvi_loanitem_detail", args=(self.pk,))

    def get_hx_edit_url(self):
        kwargs = {"parent_id": self.loan.id, "id": self.id}
        return reverse("girvi:loanitem_create_update", kwargs=kwargs)

    def get_delete_url(self):
        return reverse(
            "girvi:girvi_loanitem_delete",
            kwargs={"id": self.id, "parent_id": self.loan.id},
        )

    def current_value(self):
        from ..services import RateCacheService

        rate = RateCacheService.get_rate(self.itemtype)
        return round(self.weight * self.purity * Decimal(0.01) * rate, 2)

    @property
    def pure_weight(self):
        return (self.weight * self.purity / 100).quantize(Decimal("0.001"))

    def save(self, *args, **kwargs):
        # if self.loan.is_released:
        #     raise ValidationError(
        #         "Cannot modify LoanItem because related Loan has a Release."
        #     )
        self.interest = (self.interestrate / 100) * self.loanamount
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.loan.is_released:
            raise ValidationError(
                "Cannot delete LoanItem because related Loan has a Release."
            )
        # loan = self.loan
        super().delete(*args, **kwargs)
        # loan.update()

    def get_item_pic(self):
        return self.pic.url if self.pic and self.pic else None

    @property
    def is_available_for_repledge(self):
        return self.custody_status == "in_vault" and not self.loan.is_released


class RepledgedLoanItem(models.Model):
    original_loanitem = models.ForeignKey(
        "LoanItem", on_delete=models.CASCADE, related_name="repledged_items"
    )
    loan = models.ForeignKey(
        "girvi.TakenLoan", on_delete=models.CASCADE, related_name="repledgedloanitems"
    )
    repledged_loanamount = models.DecimalField(max_digits=10, decimal_places=2)
    interest_rate = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    interest = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    repledged_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Repledged {self.original_loanitem} to {self.loan}"

    def get_absolute_url(self):
        # return self.loan.get_absolute_url()
        return reverse("girvi:repledgedloanitem_detail", args=(self.pk,))

    def get_hx_edit_url(self):
        kwargs = {"parent_id": self.loan.id, "id": self.id}
        return reverse("girvi:loanitem_create_update", kwargs=kwargs)

    def get_delete_url(self):
        return reverse(
            "girvi:girvi_loanitem_delete",
            kwargs={"id": self.id, "parent_id": self.loan.id},
        )

    def save(self, *args, **kwargs):
        # if self.loan.is_released:
        #     raise ValidationError(
        #         "Cannot modify LoanItem because related Loan has a Release."
        #     )
        self.interest = (self.interest_rate / 100) * self.repledged_loanamount
        super().save(*args, **kwargs)


class LoanItemPic(models.Model):
    loan = models.ForeignKey(
        "girvi.GivenLoan", on_delete=models.CASCADE, related_name="loanitem_pics"
    )
    pic = models.ImageField(upload_to="loan_item_pics/", null=True, blank=True)
    description = models.TextField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Picture for {self.loan.loan_id}"

    def get_absolute_url(self):
        return reverse("loanitempic_detail", args=[str(self.id)])

    def get_update_url(self):
        return reverse("loanitempic_update", args=[str(self.id)])

    def get_delete_url(self):
        return reverse("loanitempic_delete", args=[str(self.id)])


class LoanItemStorageBox(models.Model):
    """
    Storage box for organizing loan items by ranges.
    Uses ForeignKeys for referential integrity and type safety.
    """

    name = models.CharField(max_length=50)
    location = models.CharField(max_length=50)
    start_item = models.ForeignKey(
        LoanItem, on_delete=models.SET_NULL, null=True, related_name="as_box_start"
    )
    end_item = models.ForeignKey(
        LoanItem, on_delete=models.SET_NULL, null=True, related_name="as_box_end"
    )
    item_type = models.CharField(
        max_length=6, choices=ItemType.choices, default=ItemType.GOLD
    )

    def __str__(self):
        return f"{self.name} at {self.location} (Items {self.start_item_id} to {self.end_item_id})"

    def clean(self):
        """
        Robust validation for storage box ranges.
        Validates: null checks, ordering, item type consistency, and overlap detection.
        """
        errors = {}

        # 1. Validate that both start and end items are provided
        if not self.start_item_id:
            errors["start_item"] = "Start item is required for a storage box."
        if not self.end_item_id:
            errors["end_item"] = "End item is required for a storage box."

        # Return early if required fields are missing
        if errors:
            raise ValidationError(errors)

        # 2. Validate ordering: start must come before or equal to end
        if self.start_item_id > self.end_item_id:
            raise ValidationError(
                {
                    "start_item": f"Start item ID ({self.start_item_id}) must be <= end item ID ({self.end_item_id}).",
                    "end_item": f"End item ID ({self.end_item_id}) must be >= start item ID ({self.start_item_id}).",
                }
            )

        # 3. Verify item type consistency (items must match box's item_type)
        try:
            # Check start item
            if self.start_item and self.start_item.itemtype != self.item_type:
                errors["start_item"] = (
                    f"Start item has type '{self.start_item.itemtype}' "
                    f"but box is configured for '{self.item_type}'."
                )

            # Check end item
            if self.end_item and self.end_item.itemtype != self.item_type:
                errors["end_item"] = (
                    f"End item has type '{self.end_item.itemtype}' "
                    f"but box is configured for '{self.item_type}'."
                )

            if errors:
                raise ValidationError(errors)

        except LoanItem.DoesNotExist as e:
            logger.error(f"LoanItem lookup failed during StorageBox validation: {e}")
            raise ValidationError("Referenced loan items do not exist.")

        # 4. Check for overlapping ranges with other boxes of same item type
        overlapping_boxes = LoanItemStorageBox.objects.filter(
            item_type=self.item_type,
            start_item_id__lte=self.end_item_id,
            end_item_id__gte=self.start_item_id,
        ).exclude(pk=self.pk)

        if overlapping_boxes.exists():
            overlapping = overlapping_boxes.first()
            logger.warning(
                f"Storage box '{self.name}' ({self.start_item_id}-{self.end_item_id}) "
                f"overlaps with '{overlapping.name}' ({overlapping.start_item_id}-{overlapping.end_item_id})"
            )
            raise ValidationError(
                {
                    "__all__": (
                        f"Range {self.start_item_id}-{self.end_item_id} overlaps with "
                        f"box '{overlapping.name}' at {overlapping.location} "
                        f"(items {overlapping.start_item_id}-{overlapping.end_item_id})."
                    )
                }
            )

    def save(self, *args, **kwargs):
        """
        Override save to ensure validation is always performed.
        Calls full_clean() which triggers clean() and field validation.
        """
        # Skip validation if explicitly requested (useful for data migrations)
        if not kwargs.pop("skip_validation", False):
            self.full_clean()
        super().save(*args, **kwargs)

    def position_for_item(self, item_id):
        items_in_box = self.items().order_by("loan_id")
        item_ids = list(items_in_box.values_list("loan_id", flat=True))
        try:
            position = item_ids.index(item_id) + 1
        except ValueError:
            position = None
        return position

    def items(self):
        from django.apps import apps

        GivenLoan = apps.get_model("girvi", "GivenLoan")
        return GivenLoan.objects.unreleased().filter(
            loan_id__gte=self.start_item_id,
            loan_id__lte=self.end_item_id,
            loanitems__itemtype=self.item_type,
        )

    def items_count(self):
        return self.items().count()

    def get_absolute_url(self):
        return reverse("girvi:storagebox_detail", args=(self.pk,))
