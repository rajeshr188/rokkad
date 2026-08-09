import uuid
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class PeriodStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    ADJUSTMENT_ONLY = "ADJUSTMENT_ONLY", "Adjustment Only"
    CLOSED = "CLOSED", "Closed"
    LOCKED = "LOCKED", "Locked"


class ReportingClass(models.TextChoices):
    ASSET = "ASSET", "Asset"
    LIABILITY = "LIABILITY", "Liability"
    EQUITY = "EQUITY", "Equity"
    REVENUE = "REVENUE", "Revenue"
    EXPENSE = "EXPENSE", "Expense"
    GAIN = "GAIN", "Gain"
    LOSS = "LOSS", "Loss"


class LedgerSide(models.TextChoices):
    DEBIT = "DEBIT", "Debit"
    CREDIT = "CREDIT", "Credit"


class LedgerNodeKind(models.TextChoices):
    INTERMEDIATE = "INTERMEDIATE", "Intermediate"
    POSTING = "POSTING", "Posting"


class ExternalAccountPurpose(models.TextChoices):
    CUSTOMER_RECEIVABLE = "CUSTOMER_RECEIVABLE", "Customer Receivable"
    SUPPLIER_PAYABLE = "SUPPLIER_PAYABLE", "Supplier Payable"
    BORROWER_LOAN_RECEIVABLE = (
        "BORROWER_LOAN_RECEIVABLE",
        "Borrower Loan Receivable",
    )
    LENDER_LOAN_PAYABLE = "LENDER_LOAN_PAYABLE", "Lender Loan Payable"
    CUSTOMER_ADVANCE = "CUSTOMER_ADVANCE", "Customer Advance"
    SUPPLIER_ADVANCE = "SUPPLIER_ADVANCE", "Supplier Advance"


class PersistedVoucherState(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    AUTHORIZED = "AUTHORIZED", "Authorized"
    POSTED = "POSTED", "Posted"
    CANCELLED = "CANCELLED", "Cancelled"


class VoucherPurpose(models.TextChoices):
    ORDINARY = "ORDINARY", "Ordinary"
    ADJUSTMENT = "ADJUSTMENT", "Adjustment"


class TransactionDiscriminator(models.TextChoices):
    LEDGER = "LEDGER", "Ledger To Ledger"
    ACCOUNT = "ACCOUNT", "Ledger To External Account"


class AccountingOrganization(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization_key = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    external_tenant_key = models.CharField(max_length=128, blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("organization_key",)
        constraints = [
            models.UniqueConstraint(
                fields=("external_tenant_key",),
                condition=Q(external_tenant_key__isnull=False),
                name="acct_org_external_tenant_uniq",
            ),
        ]

    def __str__(self):
        return f"{self.organization_key} - {self.name}"


class AccountingBook(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        AccountingOrganization,
        on_delete=models.PROTECT,
        related_name="accounting_books",
    )
    book_key = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    base_currency = models.CharField(max_length=3)
    decimal_places = models.PositiveSmallIntegerField(default=2)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("organization_id", "book_key")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "book_key"),
                name="acct_book_org_key_uniq",
            ),
            models.CheckConstraint(
                condition=Q(decimal_places__gte=0, decimal_places__lte=8),
                name="acct_book_decimal_places_range",
            ),
        ]

    def clean(self):
        super().clean()
        currency = (self.base_currency or "").strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValidationError(
                {"base_currency": "Use a three-letter monetary currency code."}
            )
        self.base_currency = currency

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.organization.organization_key}/{self.book_key}"


class AccountingPeriod(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    book = models.ForeignKey(
        AccountingBook,
        on_delete=models.PROTECT,
        related_name="periods",
    )
    period_key = models.CharField(max_length=64)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=24,
        choices=PeriodStatus.choices,
        default=PeriodStatus.OPEN,
        db_index=True,
    )
    closed_at = models.DateTimeField(blank=True, null=True)
    closed_by_id = models.PositiveBigIntegerField(blank=True, null=True)
    locked_at = models.DateTimeField(blank=True, null=True)
    locked_by_id = models.PositiveBigIntegerField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("book_id", "start_date", "period_key")
        constraints = [
            models.UniqueConstraint(
                fields=("book", "period_key"),
                name="acct_period_book_key_uniq",
            ),
            models.CheckConstraint(
                condition=Q(end_date__gte=F("start_date")),
                name="acct_period_dates_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status=PeriodStatus.CLOSED, closed_at__isnull=False)
                    | ~Q(status=PeriodStatus.CLOSED)
                ),
                name="acct_period_closed_evidence",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status=PeriodStatus.LOCKED, locked_at__isnull=False)
                    | ~Q(status=PeriodStatus.LOCKED)
                ),
                name="acct_period_locked_evidence",
            ),
        ]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError({"end_date": "End date must not precede start date."})
        if self.status == PeriodStatus.CLOSED and self.closed_at is None:
            raise ValidationError({"closed_at": "Closed periods require close evidence."})
        if self.status == PeriodStatus.LOCKED and self.locked_at is None:
            raise ValidationError({"locked_at": "Locked periods require lock evidence."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.book.book_key}/{self.period_key}"


class AccountingPeriodTransition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    period = models.ForeignKey(
        AccountingPeriod, on_delete=models.PROTECT, related_name="transitions"
    )
    from_status = models.CharField(max_length=24, choices=PeriodStatus.choices)
    to_status = models.CharField(max_length=24, choices=PeriodStatus.choices)
    actor_id = models.PositiveBigIntegerField()
    actor_identity = models.CharField(max_length=512)
    occurred_at = models.DateTimeField()
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("period_id", "occurred_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=~Q(from_status=F("to_status")),
                name="acct_period_transition_changes_status",
            ),
            models.UniqueConstraint(
                fields=("period", "occurred_at"),
                name="acct_period_transition_time_uniq",
            ),
        ]


class Ledger(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    book = models.ForeignKey(
        AccountingBook,
        on_delete=models.PROTECT,
        related_name="ledgers",
    )
    ledger_key = models.CharField(max_length=64)
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=255)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="children",
        blank=True,
        null=True,
    )
    reporting_class = models.CharField(max_length=16, choices=ReportingClass.choices)
    normal_side = models.CharField(max_length=8, choices=LedgerSide.choices)
    node_kind = models.CharField(max_length=16, choices=LedgerNodeKind.choices)
    can_debit = models.BooleanField(default=True)
    can_credit = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("book_id", "code", "ledger_key")
        constraints = [
            models.UniqueConstraint(
                fields=("book", "ledger_key"),
                name="acct_ledger_book_key_uniq",
            ),
            models.UniqueConstraint(
                fields=("book", "code"),
                name="acct_ledger_book_code_uniq",
            ),
            models.CheckConstraint(
                condition=~Q(id=F("parent_id")),
                name="acct_ledger_not_own_parent",
            ),
            models.CheckConstraint(
                condition=Q(can_debit=True) | Q(can_credit=True),
                name="acct_ledger_has_allowed_side",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.parent_id:
            if self.parent_id == self.id:
                errors["parent"] = "A ledger cannot be its own parent."
            elif self.parent.book_id != self.book_id:
                errors["parent"] = "Parent ledger must belong to the same book."
            elif self.parent.node_kind != LedgerNodeKind.INTERMEDIATE:
                errors["parent"] = "Only an intermediate ledger may have children."
            else:
                ancestor = self.parent
                visited = {self.id}
                while ancestor is not None:
                    if ancestor.id in visited:
                        errors["parent"] = "Ledger hierarchy must not contain a cycle."
                        break
                    visited.add(ancestor.id)
                    ancestor = ancestor.parent
        if self.pk and self.node_kind == LedgerNodeKind.POSTING and self.children.exists():
            errors["node_kind"] = "A posting ledger cannot have children."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.book.book_key}/{self.code} {self.name}"


class ExternalAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    book = models.ForeignKey(
        AccountingBook,
        on_delete=models.PROTECT,
        related_name="external_accounts",
    )
    account_key = models.CharField(max_length=128)
    party_key = models.CharField(max_length=128)
    party = models.ForeignKey(
        "party.Party",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="accounting_external_accounts",
    )
    purpose = models.CharField(max_length=40, choices=ExternalAccountPurpose.choices)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("book_id", "account_key")
        constraints = [
            models.UniqueConstraint(
                fields=("book", "account_key"),
                name="acct_ext_account_book_key_uniq",
            ),
            models.UniqueConstraint(
                fields=("book", "party", "purpose"),
                condition=models.Q(party__isnull=False),
                name="acct_ext_book_party_purpose_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=("book", "party_key", "purpose", "is_active"),
                name="acct_ext_party_purpose_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.account_key = (self.account_key or "").strip()
        self.party_key = (self.party_key or "").strip()
        if not self.account_key:
            errors["account_key"] = "Account key is required."
        if not self.party_key:
            errors["party_key"] = "Party adapter key is required."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.book.book_key}/{self.account_key}"


class ExternalAccountClassification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    external_account = models.ForeignKey(
        ExternalAccount,
        on_delete=models.PROTECT,
        related_name="classification_versions",
    )
    version_key = models.CharField(max_length=64)
    effective_from = models.DateField()
    effective_to = models.DateField(blank=True, null=True)
    reporting_ledger = models.ForeignKey(
        Ledger,
        on_delete=models.PROTECT,
        related_name="external_account_classifications",
    )
    reporting_class = models.CharField(max_length=16, choices=ReportingClass.choices)
    normal_side = models.CharField(max_length=8, choices=LedgerSide.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("external_account_id", "effective_from", "version_key")
        constraints = [
            models.UniqueConstraint(
                fields=("external_account", "version_key"),
                name="acct_ext_class_account_version_uniq",
            ),
            models.CheckConstraint(
                condition=Q(effective_to__isnull=True)
                | Q(effective_to__gte=F("effective_from")),
                name="acct_ext_class_dates_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=("external_account", "effective_from", "effective_to"),
                name="acct_ext_class_dates_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if (
            self.effective_from
            and self.effective_to
            and self.effective_to < self.effective_from
        ):
            errors["effective_to"] = "Effective end date must not precede start date."
        if self.external_account_id and self.reporting_ledger_id:
            if self.external_account.book_id != self.reporting_ledger.book_id:
                errors["reporting_ledger"] = (
                    "Reporting ledger must belong to the external account book."
                )
            if self.reporting_ledger.node_kind != LedgerNodeKind.POSTING:
                errors["reporting_ledger"] = "Reporting ledger must be a posting ledger."
            if self.reporting_class != self.reporting_ledger.reporting_class:
                errors["reporting_class"] = (
                    "Reporting class must match the reporting ledger."
                )
            if self.normal_side != self.reporting_ledger.normal_side:
                errors["normal_side"] = "Normal side must match the reporting ledger."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.external_account.account_key}/{self.version_key}"


class Voucher(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    book = models.ForeignKey(
        AccountingBook,
        on_delete=models.PROTECT,
        related_name="vouchers",
    )
    voucher_key = models.CharField(max_length=128)
    voucher_number = models.CharField(max_length=128, blank=True)
    effective_date = models.DateField(db_index=True)
    purpose = models.CharField(
        max_length=16,
        choices=VoucherPurpose.choices,
        default=VoucherPurpose.ORDINARY,
    )
    state = models.CharField(
        max_length=16,
        choices=PersistedVoucherState.choices,
        default=PersistedVoucherState.DRAFT,
        db_index=True,
    )
    idempotency_key = models.CharField(max_length=255)
    source_system = models.CharField(max_length=64)
    source_type = models.CharField(max_length=64)
    source_id = models.CharField(max_length=128)
    source_version = models.CharField(max_length=64)
    rule_key = models.CharField(max_length=128)
    rule_version = models.CharField(max_length=64)
    fingerprint = models.CharField(max_length=64, blank=True, null=True)
    created_by_id = models.PositiveBigIntegerField(blank=True, null=True)
    created_by_identity = models.CharField(max_length=512, blank=True)
    authorized_by_id = models.PositiveBigIntegerField(blank=True, null=True)
    authorized_by_identity = models.CharField(max_length=512, blank=True)
    authorized_at = models.DateTimeField(blank=True, null=True)
    narration = models.TextField(blank=True)
    correction_group_key = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("book_id", "effective_date", "voucher_key")
        constraints = [
            models.UniqueConstraint(
                fields=("book", "voucher_key"),
                name="acct_voucher_book_key_uniq",
            ),
            models.UniqueConstraint(
                fields=("book", "idempotency_key"),
                name="acct_voucher_book_idempotency_uniq",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        state__in=(
                            PersistedVoucherState.AUTHORIZED,
                            PersistedVoucherState.POSTED,
                        ),
                        authorized_by_id__isnull=False,
                        authorized_at__isnull=False,
                    )
                    | ~Q(
                        state__in=(
                            PersistedVoucherState.AUTHORIZED,
                            PersistedVoucherState.POSTED,
                        )
                    )
                ),
                name="acct_voucher_authorized_evidence",
            ),
            models.CheckConstraint(
                condition=(
                    Q(state=PersistedVoucherState.POSTED, fingerprint__isnull=False)
                    | Q(fingerprint__isnull=True)
                    & ~Q(state=PersistedVoucherState.POSTED)
                ),
                name="acct_voucher_fingerprint_by_state",
            ),
            models.CheckConstraint(
                condition=~Q(created_by_identity=""),
                name="acct_voucher_creator_identity_required",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        state__in=(PersistedVoucherState.AUTHORIZED, PersistedVoucherState.POSTED),
                    )
                    & ~Q(authorized_by_identity="")
                    | ~Q(state__in=(PersistedVoucherState.AUTHORIZED, PersistedVoucherState.POSTED))
                ),
                name="acct_voucher_authorizer_identity_required",
            ),
        ]
        indexes = [
            models.Index(
                fields=("book", "source_system", "source_type", "source_id"),
                name="acct_voucher_source_idx",
            ),
            models.Index(
                fields=("book", "state", "effective_date"),
                name="acct_voucher_state_date_idx",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        required = (
            "voucher_key",
            "idempotency_key",
            "source_system",
            "source_type",
            "source_id",
            "source_version",
            "rule_key",
            "rule_version",
        )
        for field_name in required:
            value = (getattr(self, field_name) or "").strip()
            setattr(self, field_name, value)
            if not value:
                errors[field_name] = "This accounting identity field is required."
        if self.state in (
            PersistedVoucherState.AUTHORIZED,
            PersistedVoucherState.POSTED,
        ):
            if self.authorized_by_id is None:
                errors["authorized_by_id"] = "Authorized voucher requires an actor."
            if self.authorized_at is None:
                errors["authorized_at"] = "Authorized voucher requires a timestamp."
        elif self.authorized_by_id is not None or self.authorized_at is not None:
            errors["state"] = "Authorization evidence is valid only when authorized."
        if self.state == PersistedVoucherState.POSTED:
            if not self.fingerprint:
                errors["fingerprint"] = "Posted voucher requires a fingerprint."
        elif self.fingerprint is not None:
            errors["fingerprint"] = "Fingerprint is assigned only during posting."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.book.book_key}/{self.voucher_key}"


class AccountingTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    voucher = models.ForeignKey(
        Voucher,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    sequence = models.PositiveIntegerField()
    discriminator = models.CharField(
        max_length=8,
        choices=TransactionDiscriminator.choices,
    )
    amount = models.DecimalField(max_digits=24, decimal_places=8)
    currency = models.CharField(max_length=3)
    base_amount = models.DecimalField(max_digits=24, decimal_places=8)
    base_currency = models.CharField(max_length=3)
    exchange_rate = models.DecimalField(max_digits=24, decimal_places=12)
    rate_source = models.CharField(max_length=128)
    narration = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("voucher_id", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("voucher", "sequence"),
                name="acct_tx_voucher_sequence_uniq",
            ),
            models.CheckConstraint(
                condition=Q(sequence__gt=0),
                name="acct_tx_sequence_positive",
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="acct_tx_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(base_amount__gt=0),
                name="acct_tx_base_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(exchange_rate__gt=0),
                name="acct_tx_exchange_rate_positive",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        for field_name in ("currency", "base_currency"):
            value = (getattr(self, field_name) or "").strip().upper()
            setattr(self, field_name, value)
            if len(value) != 3 or not value.isalpha():
                errors[field_name] = "Use a three-letter monetary currency code."
        self.rate_source = (self.rate_source or "").strip()
        if not self.rate_source:
            errors["rate_source"] = "Rate source is required."
        if self.voucher_id:
            if self.voucher.state != PersistedVoucherState.DRAFT:
                errors["voucher"] = "Transactions may change only on a draft voucher."
            if self.base_currency and self.base_currency != self.voucher.book.base_currency:
                errors["base_currency"] = "Base currency must match the accounting book."
            if self.amount and self.exchange_rate and self.base_amount:
                quantum = Decimal("1").scaleb(-self.voucher.book.decimal_places)
                expected = (self.amount * self.exchange_rate).quantize(
                    quantum, rounding=ROUND_HALF_UP
                )
                if self.base_amount != expected:
                    errors["base_amount"] = (
                        "Base amount must equal transaction amount times exchange rate."
                    )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.voucher.voucher_key}/{self.sequence}"


class LedgerTransaction(models.Model):
    transaction = models.OneToOneField(
        AccountingTransaction,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="ledger_detail",
    )
    debit_ledger = models.ForeignKey(
        Ledger,
        on_delete=models.PROTECT,
        related_name="draft_debit_transactions",
    )
    credit_ledger = models.ForeignKey(
        Ledger,
        on_delete=models.PROTECT,
        related_name="draft_credit_transactions",
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=~Q(debit_ledger=F("credit_ledger")),
                name="acct_ledger_tx_distinct_ledgers",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.transaction_id:
            if self.transaction.discriminator != TransactionDiscriminator.LEDGER:
                errors["transaction"] = "Base transaction discriminator must be LEDGER."
            book_id = self.transaction.voucher.book_id
            if self.debit_ledger_id and self.debit_ledger.book_id != book_id:
                errors["debit_ledger"] = "Debit ledger must belong to the voucher book."
            if self.credit_ledger_id and self.credit_ledger.book_id != book_id:
                errors["credit_ledger"] = "Credit ledger must belong to the voucher book."
        for field_name in ("debit_ledger", "credit_ledger"):
            ledger = getattr(self, field_name, None)
            if ledger and ledger.node_kind != LedgerNodeKind.POSTING:
                errors[field_name] = "Transactions require posting ledgers."
        if self.debit_ledger_id and not self.debit_ledger.can_debit:
            errors["debit_ledger"] = "Ledger does not permit debit transactions."
        if self.credit_ledger_id and not self.credit_ledger.can_credit:
            errors["credit_ledger"] = "Ledger does not permit credit transactions."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class AccountTransaction(models.Model):
    transaction = models.OneToOneField(
        AccountingTransaction,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="account_detail",
    )
    ledger = models.ForeignKey(
        Ledger,
        on_delete=models.PROTECT,
        related_name="draft_external_transactions",
    )
    external_account = models.ForeignKey(
        ExternalAccount,
        on_delete=models.PROTECT,
        related_name="draft_transactions",
    )
    ledger_side = models.CharField(max_length=8, choices=LedgerSide.choices)
    classification = models.ForeignKey(
        ExternalAccountClassification,
        on_delete=models.PROTECT,
        related_name="draft_transactions",
    )

    def clean(self):
        super().clean()
        errors = {}
        if self.transaction_id:
            if self.transaction.discriminator != TransactionDiscriminator.ACCOUNT:
                errors["transaction"] = "Base transaction discriminator must be ACCOUNT."
            book_id = self.transaction.voucher.book_id
            if self.ledger_id and self.ledger.book_id != book_id:
                errors["ledger"] = "Internal ledger must belong to the voucher book."
            if self.external_account_id and self.external_account.book_id != book_id:
                errors["external_account"] = (
                    "External account must belong to the voucher book."
                )
            if (
                self.classification_id
                and self.classification.external_account_id != self.external_account_id
            ):
                errors["classification"] = (
                    "Classification must belong to the selected external account."
                )
            if self.classification_id:
                effective_date = self.transaction.voucher.effective_date
                is_reversal = self.transaction.voucher.source_type == "REVERSAL"
                if not is_reversal and (
                    self.classification.effective_from > effective_date
                    or (
                        self.classification.effective_to is not None
                        and self.classification.effective_to < effective_date
                    )
                ):
                    errors["classification"] = (
                        "Classification must be effective on the voucher date."
                    )
        if self.ledger_id and self.ledger.node_kind != LedgerNodeKind.POSTING:
            errors["ledger"] = "Transactions require a posting ledger."
        if self.ledger_side == LedgerSide.DEBIT and self.ledger_id and not self.ledger.can_debit:
            errors["ledger"] = "Ledger does not permit debit transactions."
        if self.ledger_side == LedgerSide.CREDIT and self.ledger_id and not self.ledger.can_credit:
            errors["ledger"] = "Ledger does not permit credit transactions."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class TransactionBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    voucher = models.OneToOneField(
        Voucher,
        on_delete=models.PROTECT,
        related_name="posting_batch",
    )
    book = models.ForeignKey(
        AccountingBook,
        on_delete=models.PROTECT,
        related_name="transaction_batches",
    )
    period = models.ForeignKey(
        AccountingPeriod,
        on_delete=models.PROTECT,
        related_name="transaction_batches",
    )
    posted_at = models.DateTimeField()
    posted_by_id = models.PositiveBigIntegerField()
    posted_by_identity = models.CharField(max_length=512, blank=True)
    fingerprint = models.CharField(max_length=64)
    verification_digest = models.CharField(max_length=64)
    reversal_of = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="reversal_batches",
        blank=True,
        null=True,
    )
    reversal_reason = models.TextField(blank=True)
    correction_group_key = models.CharField(max_length=128, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("book_id", "posted_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("book", "fingerprint"),
                name="acct_batch_book_fingerprint_uniq",
            ),
            models.UniqueConstraint(
                fields=("reversal_of",),
                condition=Q(reversal_of__isnull=False),
                name="acct_batch_one_reversal_per_original",
            ),
            models.CheckConstraint(
                condition=~Q(id=F("reversal_of_id")),
                name="acct_batch_not_own_reversal",
            ),
            models.CheckConstraint(
                condition=(
                    Q(reversal_of__isnull=True, reversal_reason="")
                    | Q(reversal_of__isnull=False) & ~Q(reversal_reason="")
                ),
                name="acct_batch_reversal_reason_evidence",
            ),
            models.CheckConstraint(
                condition=~Q(posted_by_identity=""),
                name="acct_batch_poster_identity_required",
            ),
        ]


    def clean(self):
        super().clean()
        errors = {}
        if self.voucher_id:
            if self.voucher.book_id != self.book_id:
                errors["book"] = "Batch book must match the voucher book."
            if self.voucher.state != PersistedVoucherState.POSTED:
                errors["voucher"] = "A posting batch requires a posted voucher."
            if self.voucher.fingerprint != self.fingerprint:
                errors["fingerprint"] = "Batch fingerprint must match its voucher."
        if self.period_id:
            if self.period.book_id != self.book_id:
                errors["period"] = "Posting period must belong to the batch book."
            if self.voucher_id and not (
                self.period.start_date
                <= self.voucher.effective_date
                <= self.period.end_date
            ):
                errors["period"] = "Voucher date must fall inside the posting period."
        for field_name in ("fingerprint", "verification_digest"):
            value = (getattr(self, field_name) or "").strip().lower()
            setattr(self, field_name, value)
            if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
                errors[field_name] = "Use a 64-character hexadecimal SHA-256 digest."
        if self.reversal_of_id:
            if self.reversal_of.book_id != self.book_id:
                errors["reversal_of"] = "Reversal must belong to the same book."
            if self.reversal_of.reversal_of_id is not None:
                errors["reversal_of"] = "A reversal batch cannot itself be reversed."
            self.reversal_reason = (self.reversal_reason or "").strip()
            if not self.reversal_reason:
                errors["reversal_reason"] = "Reversal reason is required."
        elif self.reversal_reason:
            errors["reversal_reason"] = "Only reversal batches may carry a reason."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class VoucherNumberSequence(models.Model):
    book = models.ForeignKey(
        AccountingBook, on_delete=models.PROTECT, related_name="voucher_number_sequences"
    )
    sequence_year = models.PositiveSmallIntegerField()
    next_number = models.PositiveBigIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("book", "sequence_year"),
                name="acct_voucher_seq_book_year_uniq",
            ),
            models.CheckConstraint(
                condition=Q(next_number__gt=0), name="acct_voucher_seq_next_positive"
            ),
        ]


class SourceDeliveryStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    POSTED = "POSTED", "Posted"
    FAILED = "FAILED", "Failed"


class AccountingSourceDelivery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    book = models.ForeignKey(
        AccountingBook, on_delete=models.PROTECT, related_name="source_deliveries"
    )
    source_system = models.CharField(max_length=64)
    source_type = models.CharField(max_length=64)
    source_id = models.CharField(max_length=128)
    source_version = models.CharField(max_length=64)
    schema_version = models.CharField(max_length=16)
    payload_hash = models.CharField(max_length=64)
    status = models.CharField(
        max_length=16, choices=SourceDeliveryStatus.choices, default=SourceDeliveryStatus.PENDING
    )
    voucher = models.OneToOneField(
        Voucher, on_delete=models.PROTECT, related_name="source_delivery", null=True, blank=True
    )
    attempt_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("book", "source_system", "source_type", "source_id", "source_version"),
                name="acct_delivery_source_version_uniq",
            ),
            models.CheckConstraint(
                condition=Q(payload_hash__regex=r"^[0-9a-f]{64}$"),
                name="acct_delivery_payload_hash_valid",
            ),
        ]


class OpenItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    book = models.ForeignKey(
        AccountingBook, on_delete=models.PROTECT, related_name="open_items"
    )
    open_item_key = models.CharField(max_length=128)
    origin_transaction = models.OneToOneField(
        AccountTransaction,
        on_delete=models.PROTECT,
        related_name="open_item",
    )
    external_account = models.ForeignKey(
        ExternalAccount, on_delete=models.PROTECT, related_name="open_items"
    )
    due_date = models.DateField(blank=True, null=True)
    original_amount = models.DecimalField(max_digits=24, decimal_places=8)
    currency = models.CharField(max_length=3)
    original_base_amount = models.DecimalField(max_digits=24, decimal_places=8)
    base_currency = models.CharField(max_length=3)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by_id = models.PositiveBigIntegerField()

    class Meta:
        ordering = ("book_id", "open_item_key")
        constraints = [
            models.UniqueConstraint(
                fields=("book", "open_item_key"), name="acct_open_item_book_key_uniq"
            ),
            models.CheckConstraint(
                condition=Q(original_amount__gt=0), name="acct_open_item_amount_positive"
            ),
            models.CheckConstraint(
                condition=Q(original_base_amount__gt=0),
                name="acct_open_item_base_amount_positive",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.origin_transaction_id:
            base = self.origin_transaction.transaction
            if base.voucher.state != PersistedVoucherState.POSTED:
                errors["origin_transaction"] = "Open item origin must be posted."
            if base.voucher.book_id != self.book_id:
                errors["book"] = "Open item book must match its origin voucher."
            if self.origin_transaction.external_account_id != self.external_account_id:
                errors["external_account"] = "Open item account must match its origin."
            expected = (
                (base.amount, base.currency, base.base_amount, base.base_currency)
            )
            actual = (
                self.original_amount,
                self.currency,
                self.original_base_amount,
                self.base_currency,
            )
            if actual != expected:
                errors["original_amount"] = "Open item must freeze the exact origin money."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class OpenItemAllocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    settlement_transaction = models.ForeignKey(
        AccountTransaction,
        on_delete=models.PROTECT,
        related_name="open_item_allocations",
    )
    open_item = models.ForeignKey(
        OpenItem, on_delete=models.PROTECT, related_name="allocations"
    )
    sequence = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=24, decimal_places=8)
    currency = models.CharField(max_length=3)
    base_amount = models.DecimalField(max_digits=24, decimal_places=8)
    base_currency = models.CharField(max_length=3)
    reversal_of = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        related_name="compensating_allocation",
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by_id = models.PositiveBigIntegerField()

    class Meta:
        ordering = ("settlement_transaction_id", "sequence")
        constraints = [
            models.UniqueConstraint(
                fields=("settlement_transaction", "sequence"),
                name="acct_allocation_settlement_sequence_uniq",
            ),
            models.UniqueConstraint(
                fields=("settlement_transaction", "open_item"),
                name="acct_allocation_settlement_item_uniq",
            ),
            models.CheckConstraint(
                condition=Q(sequence__gt=0), name="acct_allocation_sequence_positive"
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="acct_allocation_amount_positive"
            ),
            models.CheckConstraint(
                condition=Q(base_amount__gt=0),
                name="acct_allocation_base_amount_positive",
            ),
            models.CheckConstraint(
                condition=~Q(id=F("reversal_of_id")),
                name="acct_allocation_not_own_reversal",
            ),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.settlement_transaction_id and self.open_item_id:
            settlement = self.settlement_transaction
            base = settlement.transaction
            if base.voucher.state != PersistedVoucherState.POSTED:
                errors["settlement_transaction"] = "Settlement transaction must be posted."
            if settlement.external_account_id != self.open_item.external_account_id:
                errors["open_item"] = "Allocation cannot cross external accounts."
            if base.voucher.book_id != self.open_item.book_id:
                errors["open_item"] = "Allocation cannot cross accounting books."
            if (
                not self.reversal_of_id
                and settlement.ledger_side
                == self.open_item.origin_transaction.ledger_side
            ):
                errors["settlement_transaction"] = (
                    "Settlement must oppose the open-item transaction side."
                )
            if (self.currency, self.base_currency) != (
                self.open_item.currency,
                self.open_item.base_currency,
            ):
                errors["currency"] = "Allocation currencies must match the open item."
        if self.reversal_of_id:
            original = self.reversal_of
            if original.reversal_of_id is not None:
                errors["reversal_of"] = "An allocation reversal cannot be reversed."
            if original.open_item_id != self.open_item_id:
                errors["open_item"] = "Allocation reversal must use the original item."
            if (
                self.amount,
                self.currency,
                self.base_amount,
                self.base_currency,
            ) != (
                original.amount,
                original.currency,
                original.base_amount,
                original.base_currency,
            ):
                errors["reversal_of"] = "Allocation reversal must copy the exact money."
            if self.settlement_transaction_id:
                reversal_batch = self.settlement_transaction.transaction.voucher.posting_batch
                original_batch = original.settlement_transaction.transaction.voucher.posting_batch
                if reversal_batch.reversal_of_id != original_batch.id:
                    errors["settlement_transaction"] = (
                        "Compensation must use the financial reversal transaction."
                    )
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
