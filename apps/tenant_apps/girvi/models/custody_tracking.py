"""
Enhanced LoanItem model with Custody Tracking for Repledge Management.

This replaces the old RepledgedLoanItem approach with direct custody tracking on LoanItem.

Key Features:
- Clear custody status (IN_VAULT, WITH_LENDER, WITH_CUSTOMER)
- Prevents invalid releases when items are with lenders
- Full history tracking
- Supports multi-item collateral bundles
- Workflow for return-then-release

Migration Notes:
- Add new fields to LoanItem
- Migrate existing RepledgedLoanItem data
- Keep RepledgedLoanItem for backward compatibility (read-only)
"""

from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.urls import reverse


class ItemCustodyStatus(models.TextChoices):
    """Physical custody status of loan items"""

    IN_VAULT = "in_vault", "In Our Vault"
    WITH_LENDER = "with_lender", "Pledged to Lender"
    WITH_CUSTOMER = "with_customer", "Released to Customer"


# ============================================================================
# Enhanced LoanItem with Custody Tracking
# ============================================================================


class LoanItemWithCustody(models.Model):
    """
    Extended LoanItem with custody tracking fields.

    Add these fields to existing LoanItem model via migration.
    """

    class Meta:
        abstract = True

    # === NEW FIELDS FOR CUSTODY TRACKING ===

    custody_status = models.CharField(
        max_length=20,
        choices=ItemCustodyStatus.choices,
        default=ItemCustodyStatus.IN_VAULT,
        db_index=True,
        help_text="Current physical location of item",
    )

    # Repledge tracking (if currently repledged)
    repledged_to = models.ForeignKey(
        "girvi.Loan",  # Will be TakenLoan in refactored version
        null=True,
        blank=True,
        on_delete=models.PROTECT,  # Can't delete loan if items still pledged
        related_name="collateral_items",
        help_text="Active repledge - item is currently with this lender",
    )

    repledged_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount borrowed using this item as collateral",
    )

    repledged_at = models.DateTimeField(
        null=True, blank=True, help_text="When item was most recently repledged"
    )

    # === BACKWARD COMPATIBILITY ===

    @property
    def is_repledged(self):
        """Backward compatibility with old boolean field"""
        return self.repledged_to is not None

    # === CUSTODY PROPERTIES ===

    @property
    def is_in_vault(self):
        """Item is in our possession"""
        return self.custody_status == ItemCustodyStatus.IN_VAULT

    @property
    def is_available_for_release(self):
        """Can customer get this item back right now?"""
        return (
            self.custody_status == ItemCustodyStatus.IN_VAULT
            and not self.loan.is_released
        )

    @property
    def is_available_for_repledge(self):
        """Can we repledge this item to a lender?"""
        return (
            not self.loan.is_released
            and self.custody_status == ItemCustodyStatus.IN_VAULT
            and self.repledged_to is None
        )

    @property
    def can_be_returned_from_lender(self):
        """Is item currently with lender and can be returned?"""
        return (
            self.custody_status == ItemCustodyStatus.WITH_LENDER
            and self.repledged_to is not None
        )

    # === CUSTODY OPERATIONS ===

    def repledge_to(self, taken_loan, amount: Decimal, user, notes=""):
        """
        Repledge this item to a TakenLoan.

        Args:
            taken_loan: TakenLoan instance to repledge to
            amount: Amount being borrowed using this item
            user: User performing the repledge
            notes: Optional notes

        Raises:
            ValidationError: If item cannot be repledged
        """
        if not self.is_available_for_repledge:
            reasons = []
            if self.loan.is_released:
                reasons.append("loan is already released")
            if self.custody_status != ItemCustodyStatus.IN_VAULT:
                reasons.append(f"custody status is {self.get_custody_status_display()}")
            if self.repledged_to:
                reasons.append(f"already repledged to {self.repledged_to}")

            raise ValidationError(f"Cannot repledge item {self}: {', '.join(reasons)}")

        # Update custody
        self.custody_status = ItemCustodyStatus.WITH_LENDER
        self.repledged_to = taken_loan
        self.repledged_amount = amount
        self.repledged_at = timezone.now()
        self.save()

        # Create history record
        RepledgeHistory.objects.create(
            loan_item=self,
            taken_loan=taken_loan,
            repledged_amount=amount,
            item_value_at_repledge=self.current_value(),
            repledged_by=user,
            notes=notes,
        )

        return self

    def return_from_lender(self, user, notes=""):
        """
        Return item from lender to our vault.

        This happens when:
        - TakenLoan is being released/closed
        - Customer wants to release their GivenLoan (we get item back first)

        Args:
            user: User performing the return
            notes: Optional notes

        Raises:
            ValidationError: If item is not currently with lender
        """
        if not self.can_be_returned_from_lender:
            raise ValidationError(
                f"Cannot return item {self}: not currently with lender "
                f"(status: {self.get_custody_status_display()})"
            )

        taken_loan = self.repledged_to

        # Close history record
        history = RepledgeHistory.objects.filter(
            loan_item=self, taken_loan=taken_loan, returned_at__isnull=True
        ).first()

        if history:
            history.returned_at = timezone.now()
            history.returned_by = user
            history.return_notes = notes
            history.save()

        # Reset custody to vault
        self.custody_status = ItemCustodyStatus.IN_VAULT
        self.repledged_to = None
        self.repledged_amount = None
        self.repledged_at = None
        self.save()

        return self

    def release_to_customer(self, user):
        """
        Release item to customer (after GivenLoan release).

        Args:
            user: User performing the release

        Raises:
            ValidationError: If item cannot be released
        """
        if not self.is_available_for_release:
            if self.custody_status == ItemCustodyStatus.WITH_LENDER:
                raise ValidationError(
                    f"Cannot release item {self} to customer: "
                    f"item is currently with lender {self.repledged_to.lender.name}. "
                    f"Return from lender first."
                )
            elif self.custody_status == ItemCustodyStatus.WITH_CUSTOMER:
                raise ValidationError(f"Item {self} already released to customer")
            else:
                raise ValidationError(
                    f"Item {self} cannot be released (status: {self.get_custody_status_display()})"
                )

        self.custody_status = ItemCustodyStatus.WITH_CUSTOMER
        self.save()

        return self

    # === VALIDATION ===

    def clean(self):
        """Validate custody state consistency"""
        super().clean()

        # Custody status must match repledge state
        if self.repledged_to and self.custody_status != ItemCustodyStatus.WITH_LENDER:
            raise ValidationError(
                "Item has repledged_to loan but custody status is not WITH_LENDER"
            )

        if (
            not self.repledged_to
            and self.custody_status == ItemCustodyStatus.WITH_LENDER
        ):
            raise ValidationError(
                "Custody status is WITH_LENDER but repledged_to is not set"
            )

        # If repledged, amount must be set
        if self.repledged_to and not self.repledged_amount:
            raise ValidationError("Item is repledged but repledged_amount is not set")


# ============================================================================
# Repledge History Model
# ============================================================================


class RepledgeHistory(models.Model):
    """
    Complete history of all repledge events for an item.

    Tracks:
    - When item was repledged to lender
    - How much was borrowed
    - When item was returned to vault
    - Who performed each action
    """

    loan_item = models.ForeignKey(
        "girvi.LoanItem",
        on_delete=models.CASCADE,
        related_name="repledge_history",
        help_text="The item that was repledged",
    )

    taken_loan = models.ForeignKey(
        "girvi.Loan",  # Will be TakenLoan in refactored version
        on_delete=models.CASCADE,
        related_name="repledge_history_items",
        help_text="The TakenLoan where this item was used as collateral",
    )

    # === AMOUNTS ===

    repledged_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount borrowed using this item as collateral",
    )

    item_value_at_repledge = models.DecimalField(
        max_digits=10, decimal_places=2, help_text="Market value of item when repledged"
    )

    # === TIMELINE ===

    repledged_at = models.DateTimeField(
        auto_now_add=True, help_text="When item was given to lender"
    )

    returned_at = models.DateTimeField(
        null=True, blank=True, help_text="When item was returned to our vault"
    )

    # === AUDIT ===

    repledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="repledges_created",
        help_text="User who repledged the item",
    )

    returned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="repledges_returned",
        help_text="User who returned the item",
    )

    notes = models.TextField(blank=True, help_text="Notes when repledging")

    return_notes = models.TextField(blank=True, help_text="Notes when returning")

    class Meta:
        ordering = ["-repledged_at"]
        verbose_name = "Repledge History"
        verbose_name_plural = "Repledge Histories"
        indexes = [
            models.Index(fields=["loan_item", "repledged_at"]),
            models.Index(fields=["taken_loan", "repledged_at"]),
            models.Index(fields=["returned_at"]),
        ]

    def __str__(self):
        status = "Active" if self.is_active else "Returned"
        lender_name = getattr(self.taken_loan, "lender", {}).get("name", "Unknown")
        return f"{self.loan_item.itemdesc} → {lender_name} ({status})"

    # === PROPERTIES ===

    @property
    def is_active(self):
        """Is this repledge currently active?"""
        return self.returned_at is None

    @property
    def duration_days(self):
        """How many days has/was item with lender"""
        end = self.returned_at or timezone.now()
        return (end - self.repledged_at).days

    @property
    def ltv_ratio(self):
        """Loan-to-value ratio at time of repledge"""
        if self.item_value_at_repledge == 0:
            return 0
        return (self.repledged_amount / self.item_value_at_repledge) * 100


# ============================================================================
# Enhanced TakenLoan Methods
# ============================================================================


class TakenLoanCollateralMixin:
    """
    Mixin for TakenLoan to manage collateral items.
    Add these methods to TakenLoan model.
    """

    @property
    def collateral_items(self):
        """Get all items currently pledged as collateral"""
        from apps.tenant_apps.girvi.models.loan import LoanItem

        return LoanItem.objects.filter(
            repledged_to=self, custody_status=ItemCustodyStatus.WITH_LENDER
        )

    @property
    def collateral_value(self):
        """Current market value of all collateral"""
        return sum(item.current_value() for item in self.collateral_items)

    @property
    def loan_to_value_ratio(self):
        """LTV ratio - important for risk assessment"""
        collateral = self.collateral_value
        if collateral == 0:
            return 0
        return (self.get_loan_amount / collateral) * 100

    @property
    def collateral_summary(self):
        """Summary of collateral by customer"""
        from collections import defaultdict

        summary = defaultdict(lambda: {"count": 0, "value": 0})

        for item in self.collateral_items:
            customer = item.loan.customer
            summary[customer]["count"] += 1
            summary[customer]["value"] += item.current_value()

        return dict(summary)

    def add_collateral(self, loan_items: list, user, notes=""):
        """
        Add multiple items as collateral for this TakenLoan.

        Distributes loan amount proportionally based on item values.

        Args:
            loan_items: List of LoanItem instances
            user: User performing the operation
            notes: Optional notes

        Raises:
            ValidationError: If any item cannot be repledged
        """
        if not loan_items:
            raise ValidationError("No items provided")

        # Validate all items first
        for item in loan_items:
            if not item.is_available_for_repledge:
                raise ValidationError(
                    f"Item {item} not available for repledge "
                    f"(status: {item.get_custody_status_display()})"
                )

        # Calculate proportional amounts
        total_value = sum(item.current_value() for item in loan_items)
        if total_value == 0:
            raise ValidationError("Total collateral value is zero")

        loan_amount = self.get_loan_amount

        with transaction.atomic():
            for item in loan_items:
                # Proportional allocation
                item_value = item.current_value()
                item_amount = (item_value / total_value) * loan_amount

                item.repledge_to(
                    taken_loan=self, amount=item_amount, user=user, notes=notes
                )

    def return_all_collateral(self, user, notes=""):
        """
        Return all collateral items to vault.

        Call this when TakenLoan is being released/closed.

        Args:
            user: User performing the operation
            notes: Optional notes
        """
        with transaction.atomic():
            for item in self.collateral_items:
                item.return_from_lender(user, notes)

    def can_close(self):
        """Check if TakenLoan can be closed"""
        if self.collateral_items.exists():
            return False, "Cannot close - collateral items must be returned first"
        return True, "Can close"


# ============================================================================
# Enhanced GivenLoan Methods
# ============================================================================


class GivenLoanReleaseMixin:
    """
    Mixin for GivenLoan to handle releases with custody checks.
    Add these methods to GivenLoan model.
    """

    def get_items_by_custody(self):
        """Group items by custody status"""
        from collections import defaultdict

        by_status = defaultdict(list)

        for item in self.loanitems.all():
            by_status[item.custody_status].append(item)

        return dict(by_status)

    def can_release(self):
        """
        Check if loan can be released.

        Returns:
            (bool, str): (can_release, message)
        """
        items_by_custody = self.get_items_by_custody()

        # Check for items with lender
        with_lender = items_by_custody.get(ItemCustodyStatus.WITH_LENDER, [])
        if with_lender:
            lenders = set(
                item.repledged_to.lender.name
                for item in with_lender
                if item.repledged_to
            )
            return False, (
                f"Cannot release: {len(with_lender)} item(s) currently with lender(s): "
                f"{', '.join(lenders)}. Return items from lenders first."
            )

        # Check for items already with customer
        with_customer = items_by_custody.get(ItemCustodyStatus.WITH_CUSTOMER, [])
        if with_customer:
            return False, f"Items already released to customer"

        return True, "All items in vault - can release"

    def release_with_return_workflow(self, release_date, released_by, created_by):
        """
        Release loan with automatic return from lenders if needed.

        Workflow:
        1. Check if any items are with lenders
        2. If yes, return them first
        3. Then release to customer

        Args:
            release_date: Date of release
            released_by: Person releasing
            created_by: User creating the release

        Returns:
            Release object

        Raises:
            ValidationError: If release cannot be completed
        """
        items_by_custody = self.get_items_by_custody()

        with transaction.atomic():
            # Step 1: Return items from lenders
            with_lender = items_by_custody.get(ItemCustodyStatus.WITH_LENDER, [])
            if with_lender:
                for item in with_lender:
                    item.return_from_lender(
                        user=created_by,
                        notes=f"Returned for GivenLoan {self.loan_id} release",
                    )

            # Step 2: Release items to customer
            in_vault = items_by_custody.get(ItemCustodyStatus.IN_VAULT, [])
            for item in in_vault:
                item.release_to_customer(user=created_by)

            # Step 3: Create release document
            release = self.create_release(
                release_date=release_date,
                released_by=released_by,
                created_by=created_by,
            )

            return release


# ============================================================================
# Migration Helpers
# ============================================================================


def migrate_repledged_loan_items():
    """
    Migrate existing RepledgedLoanItem records to new custody system.

    Call this in a data migration after adding new fields to LoanItem.
    """
    from apps.tenant_apps.girvi.models.loan import LoanItem, RepledgedLoanItem

    migrated_count = 0

    for repledge in RepledgedLoanItem.objects.all():
        item = repledge.original_loanitem

        # Update custody status
        item.custody_status = ItemCustodyStatus.WITH_LENDER
        item.repledged_to = repledge.loan
        item.repledged_amount = repledge.repledged_loanamount
        item.repledged_at = repledge.repledged_date
        item.save()

        # Create history record
        RepledgeHistory.objects.create(
            loan_item=item,
            taken_loan=repledge.loan,
            repledged_amount=repledge.repledged_loanamount,
            item_value_at_repledge=item.current_value(),
            repledged_at=repledge.repledged_date,
            notes="Migrated from RepledgedLoanItem",
        )

        migrated_count += 1

    return migrated_count


# ============================================================================
# QuerySet Helpers
# ============================================================================


class ItemCustodyQuerySet(models.QuerySet):
    """Custom QuerySet for filtering items by custody status"""

    def in_vault(self):
        """Items currently in our vault"""
        return self.filter(custody_status=ItemCustodyStatus.IN_VAULT)

    def with_lenders(self):
        """Items currently repledged to lenders"""
        return self.filter(custody_status=ItemCustodyStatus.WITH_LENDER)

    def with_customers(self):
        """Items released to customers"""
        return self.filter(custody_status=ItemCustodyStatus.WITH_CUSTOMER)

    def available_for_repledge(self):
        """Items that can be repledged right now"""
        return self.filter(
            custody_status=ItemCustodyStatus.IN_VAULT,
            repledged_to__isnull=True,
            loan__release__isnull=True,
        )

    def repledged_to_loan(self, taken_loan):
        """Items used as collateral for specific TakenLoan"""
        return self.filter(
            repledged_to=taken_loan, custody_status=ItemCustodyStatus.WITH_LENDER
        )

    def by_customer(self, customer):
        """Items from specific customer's loans"""
        return self.filter(loan__customer=customer)
