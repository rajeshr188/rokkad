from django.db import models


class BankAccount(models.Model):
    name = models.CharField(max_length=200)
    account_number = models.CharField(max_length=50, blank=True)
    bank_name = models.CharField(max_length=200, blank=True)
    ledger = models.ForeignKey(
        "dea.Ledger",
        on_delete=models.PROTECT,
        related_name="bank_accounts",
    )
    currency = models.CharField(max_length=3, default="INR")

    class Meta:
        app_label = "dea"
        ordering = ["name", "id"]

    def __str__(self):
        return f"{self.name} ({self.bank_name or self.account_number})"


class BankStatementLine(models.Model):
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name="statement_lines",
    )
    statement_date = models.DateField()
    description = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=14, decimal_places=3)
    amount_currency = models.CharField(max_length=3, default="INR")
    running_balance = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    running_balance_currency = models.CharField(max_length=3, default="INR")
    is_reconciled = models.BooleanField(default=False)

    class Meta:
        app_label = "dea"
        ordering = ["statement_date", "id"]
        indexes = [
            models.Index(fields=["bank_account", "statement_date"]),
            models.Index(fields=["is_reconciled"]),
        ]

    def __str__(self):
        return f"{self.statement_date} - {self.description} - {self.amount}"


class ReconciliationMatch(models.Model):
    bank_statement_line = models.ForeignKey(
        BankStatementLine,
        on_delete=models.CASCADE,
        related_name="reconciliation_matches",
    )
    ledger_transaction = models.ForeignKey(
        "dea.LedgerTransaction",
        on_delete=models.CASCADE,
        related_name="reconciliation_matches",
    )
    matched_at = models.DateTimeField(auto_now_add=True)
    matched_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bank_reconciliation_matches",
    )
    is_manual = models.BooleanField(default=False)

    class Meta:
        app_label = "dea"
        constraints = [
            models.UniqueConstraint(
                fields=["bank_statement_line", "ledger_transaction"],
                name="unique_bank_ledger_reconciliation_match",
            )
        ]

    def __str__(self):
        return f"{self.bank_statement_line_id} -> {self.ledger_transaction_id}"
