"""
PaymentVoucher Model - Unified Payment/Receipt Tracking

PAYMENT-CENTRIC ARCHITECTURE:
- Created only when CASH ACTUALLY MOVES (not at contract creation)
- Separate from GivenLoan/TakenLoan which are just business agreements
- Each PaymentVoucher = ONE economic event = ONE accounting entry
- IFRS 9 compliant (recognizes assets at cash transfer, not contract time)

Supports multi-currency transactions for international operations.
Routes to appropriate posting rules based on source type + direction.
"""

from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.utils import timezone
from djmoney.models.fields import MoneyField
from moneyed import Money, get_currency

from .doc import BusinessDoc


class CashFlowDirection(models.TextChoices):
    """Direction of cash movement"""

    RECEIPT = "RECEIPT", "Receipt (Cash In)"
    PAYMENT = "PAYMENT", "Payment (Cash Out)"


class PaymentType(models.TextChoices):
    """Type of payment - distinguishes different payment scenarios"""

    DISBURSAL = "DISBURSAL", "Loan Disbursal/Advance"
    RECEIPT = "RECEIPT", "Payment Receipt/Repayment"
    REFUND = "REFUND", "Refund/Reversal"
    OTHER = "OTHER", "Other Payment"


class PaymentMethod(models.TextChoices):
    """Payment instrument type"""

    CASH = "CASH", "Cash"
    BANK = "BANK", "Bank Transfer"
    CHEQUE = "CHEQUE", "Cheque"
    UPI = "UPI", "UPI"
    CARD = "CARD", "Card"
    OTHER = "OTHER", "Other"


class PaymentVoucher(BusinessDoc):
    """
    Unified payment/receipt tracking for all source documents.

    PAYMENT-CENTRIC ARCHITECTURE:
    - Created only when CASH ACTUALLY MOVES (not at contract creation)
    - Separate from GivenLoan/TakenLoan which are just business agreements
    - Each PaymentVoucher = ONE economic event = ONE accounting entry
    - IFRS 9 compliant (recognizes assets at cash transfer, not contract time)

    Supports multi-currency transactions for international operations.
    Routes to appropriate posting rules based on source type + direction.

    Examples:
    - GivenLoan disbursal → DISBURSAL + PAYMENT (money goes out)
    - GivenLoan repayment → RECEIPT + RECEIPT (money comes in)
    - TakenLoan receipt → DISBURSAL + RECEIPT (we receive money)
    - TakenLoan repayment → RECEIPT + PAYMENT (we pay back)
    - Sales payment → RECEIPT + RECEIPT (customer pays)
    - Purchase payment → RECEIPT + PAYMENT (we pay supplier)
    """

    # === Core Identity ===
    payment_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique payment reference (auto-generated)",
    )

    payment_date = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When cash actually moved (not contract date)",
    )

    # === Payment Type & Direction ===
    payment_type = models.CharField(
        max_length=20,
        choices=PaymentType.choices,
        default=PaymentType.OTHER,
        help_text="Type of payment: DISBURSAL (outflow/advance), RECEIPT (inflow/repayment)",
    )

    direction = models.CharField(
        max_length=10,
        choices=CashFlowDirection.choices,
        help_text="RECEIPT=money coming in, PAYMENT=money going out",
    )

    # === Generic Reference to Source Document ===
    source_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="paymentvoucher_source",
        help_text="Type of source document (GivenLoan, TakenLoan, SalesInvoice, etc)",
    )

    source_object_id = models.PositiveIntegerField(
        null=True, blank=True, help_text="ID of the source document instance"
    )

    source_document = GenericForeignKey("source_content_type", "source_object_id")

    # === Amount Fields ===
    # Primary amount in original currency
    total_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        help_text="Payment amount in original currency",
    )

    # Components (optional, for complex payments)
    principal_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        null=True,
        blank=True,
        help_text="Principal portion of payment",
    )

    interest_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        null=True,
        blank=True,
        help_text="Interest portion of payment",
    )

    fee_amount = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        null=True,
        blank=True,
        help_text="Fee/charge portion of payment",
    )

    # === Multi-Currency Support ===
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=1.0000,
        help_text="Exchange rate to base currency (INR) at payment date",
    )

    amount_in_base_currency = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        help_text="Amount converted to base currency using exchange rate",
    )

    is_multicurrency = models.BooleanField(
        default=False, help_text="True if payment currency differs from base currency"
    )

    # === Payment Details ===
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        help_text="How the payment was made",
    )

    reference_number = models.CharField(
        max_length=100,
        blank=True,
        db_index=True,
        help_text="Bank reference, cheque number, transaction ID, etc",
    )

    description = models.TextField(
        blank=True, help_text="Additional notes about this payment"
    )

    # === Loan-Specific Flags ===
    is_final_payment = models.BooleanField(
        default=False, help_text="Mark if this payment closes the loan"
    )

    create_release = models.BooleanField(
        default=False,
        help_text="If True and GivenLoan, creates Release record after posting",
    )

    # === Accounting Status ===
    posted = models.BooleanField(
        default=False, help_text="True if this payment has been posted to accounting"
    )

    reversal_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reversals",
        help_text="If set, this payment is a reversal of another payment",
    )

    # Metadata
    class Meta:
        db_table = "dea_paymentvoucher"
        ordering = ["-payment_date", "-created_at"]
        indexes = [
            models.Index(fields=["source_content_type", "source_object_id"]),
            models.Index(fields=["payment_id"]),
            models.Index(fields=["payment_date"]),
            models.Index(fields=["direction"]),
        ]
        verbose_name = "Payment Voucher"
        verbose_name_plural = "Payment Vouchers"

    def __str__(self):
        return f"{self.payment_id}: {self.total_amount} ({self.direction})"

    # ===== INSTANCE METHODS =====

    def clean(self):
        """Validate payment before saving"""
        super().clean()

        # DISBURSAL can be either cash out or cash in depending on the source doc.
        # Examples:
        # - GivenLoan disbursal  -> DISBURSAL + PAYMENT
        # - TakenLoan disbursal  -> DISBURSAL + RECEIPT
        # Direction-specific accounting is handled by posting rules.

        # Validate amount is positive
        if self.total_amount and self.total_amount.amount <= 0:
            raise ValidationError("Payment amount must be positive")

        # Validate component sum equals total (if components provided)
        self._validate_component_sum()

        # Validate source document is provided
        if not self.source_content_type_id or not self.source_object_id:
            raise ValidationError(
                "Source document (loan, sales, purchase, etc) is required"
            )

    def save(self, *args, **kwargs):
        """Generate payment_id and convert to base currency if needed"""
        # Generate payment_id on first save
        if not self.payment_id:
            self.payment_id = self._generate_payment_id()

        # Calculate base currency amount if multicurrency
        if self.is_multicurrency and self.total_amount and self.exchange_rate:
            base_amount = self.total_amount.amount * self.exchange_rate
            self.amount_in_base_currency = Money(base_amount, "INR")
        else:
            self.amount_in_base_currency = self.total_amount
            self.exchange_rate = 1.0000

        # Disable auto-posting for now (will be called explicitly from PaymentVoucherService)
        self.auto_post_to_accounting = False

        super().save(*args, **kwargs)

    def get_voucher_type(self) -> str:
        """
        Determine the posting rule key based on source type and direction.

        Returns strings like:
        - GIVENLOAN_RECEIPT
        - GIVENLOAN_PAYMENT
        - TAKENLOAN_RECEIPT
        - TAKENLOAN_PAYMENT
        - SALESINVOICE_RECEIPT
        - PURCHASEINVOICE_PAYMENT

        Raises ValueError if source_content_type is not set (misconfigured voucher).
        """
        if not self.source_content_type_id:
            raise ValueError(
                f"PaymentVoucher(pk={self.pk}).get_voucher_type(): "
                "source_content_type is null \u2014 cannot determine voucher type."
            )

        source_type = self.source_content_type.model.upper()
        return f"{source_type}_{self.direction}"

    def get_economic_payload(self) -> dict:
        """Return economic fields for idempotency fingerprinting"""
        return {
            "source_doc_id": self.source_object_id,
            "source_doc_type": self.source_content_type.model
            if self.source_content_type
            else None,
            "payment_id": self.payment_id,
            "payment_date": self.payment_date.isoformat(),
            "total_amount": str(self.total_amount.amount),
            "amount_currency": str(self.total_amount.currency),
            "direction": self.direction,
            "payment_type": self.payment_type,
            "reference_number": self.reference_number,
        }

    def _generate_payment_id(self) -> str:
        """Generate unique payment ID based on direction and date"""
        from datetime import datetime

        direction_prefix = (
            "DIS" if self.direction == CashFlowDirection.PAYMENT else "RCP"
        )
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        import random

        random_suffix = random.randint(1000, 9999)

        return f"{direction_prefix}-{timestamp}-{random_suffix}"

    def _validate_component_sum(self):
        """If components are provided, ensure they sum to total"""
        if not any([self.principal_amount, self.interest_amount, self.fee_amount]):
            return  # Components not provided

        component_sum = Money(0, self.total_amount.currency)

        if self.principal_amount:
            component_sum += self.principal_amount
        if self.interest_amount:
            component_sum += self.interest_amount
        if self.fee_amount:
            component_sum += self.fee_amount

        if component_sum != self.total_amount:
            raise ValidationError(
                f"Component sum ({component_sum}) does not equal total ({self.total_amount})"
            )

    # ===== QUERY HELPERS =====

    @property
    def is_receipt(self):
        """Convenience property"""
        return self.direction == CashFlowDirection.RECEIPT

    @property
    def is_payment(self):
        """Convenience property"""
        return self.direction == CashFlowDirection.PAYMENT

    @property
    def source_model_name(self):
        """Get the model name of the source document"""
        if self.source_content_type:
            return self.source_content_type.model
        return None

    @property
    def is_loan_payment(self):
        """Check if this is a loan-related payment"""
        source_name = self.source_model_name
        return source_name and source_name.lower() in ["givenloan", "takenloan"]

    @property
    def source_loan(self):
        """Get the source loan if this is a loan payment.

        Uses the existing source_document GenericForeignKey — no girvi import needed.
        Django resolves the concrete object via source_content_type + source_object_id.
        """
        if self.is_loan_payment:
            return self.source_document
        return None
