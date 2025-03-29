from django.db import models
from django.db.models import Case, DecimalField, F, Q, Sum, When

from ..models.ledger import LedgerStatement


class BaseLedgerManager(models.Manager):
    def get_queryset(self, *args, **kwargs):
        return (
            super()
            .get_queryset(*args, **kwargs)
            .select_related("AccountType", "ledgertransactions")
            .prefetch_related("ledgerstatements", "credit_txns", "debit_txns")
        )

    def with_balances(self):
        """Get ledgers with their latest statements and transaction totals prefetched"""
        latest_statements = (
            LedgerStatement.objects.filter(ledgerno=models.OuterRef("pk"))
            .order_by("ClosingBalance_currency", "-created")
            .distinct("ClosingBalance_currency")
        )

        return (
            self.get_queryset()
            .prefetch_related(
                models.Prefetch(
                    "ledgerstatements",
                    queryset=LedgerStatement.objects.order_by(
                        "ClosingBalance_currency", "-created"
                    ).distinct("ClosingBalance_currency"),
                )
            )
            .annotate(
                latest_statement_date=models.Subquery(
                    latest_statements.values("created")[:1]
                )
            )
            .annotate(
                credit_sum=Sum(
                    Case(
                        When(
                            Q(latest_statement_date__isnull=True)
                            | Q(credit_txns__created__gt=F("latest_statement_date")),
                            then="credit_txns__amount",
                        ),
                        default=0,
                        output_field=DecimalField(),
                    )
                ),
                debit_sum=Sum(
                    Case(
                        When(
                            Q(latest_statement_date__isnull=True)
                            | Q(debit_txns__created__gt=F("latest_statement_date")),
                            then="debit_txns__amount",
                        ),
                        default=0,
                        output_field=DecimalField(),
                    )
                ),
                aleg_credit_sum=Sum(
                    Case(
                        When(
                            Q(latest_statement_date__isnull=True)
                            | Q(
                                aleg__created__gt=F("latest_statement_date"),
                                aleg__XactTypeCode="Cr",
                            ),
                            then="aleg__amount",
                        ),
                        default=0,
                        output_field=DecimalField(),
                    )
                ),
                aleg_debit_sum=Sum(
                    Case(
                        When(
                            Q(latest_statement_date__isnull=True)
                            | Q(
                                aleg__created__gt=F("latest_statement_date"),
                                aleg__XactTypeCode="Dr",
                            ),
                            then="aleg__amount",
                        ),
                        default=0,
                        output_field=DecimalField(),
                    )
                ),
            )
        )


class BaseAccountManager(models.Manager):
    def get_queryset(self, *args, **kwargs):
        return (
            super()
            .get_queryset(*args, **kwargs)
            .select_related("AccountType_Ext", "contact", "entity")
            .prefetch_related("accounttransactions", "accountstatements")
        )
