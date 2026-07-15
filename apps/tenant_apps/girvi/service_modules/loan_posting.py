"""Girvi GivenLoan posting orchestration service.

This module centralizes GivenLoan accounting posting behavior for repayment,
release, auction recovery, and sale recovery events.
"""

from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from moneyed import Money

from apps.tenant_apps.girvi.models.loan_refactored import GivenLoan
from apps.tenant_apps.girvi.service_modules.repayment_idempotency import (
    build_repayment_idempotency_marker,
)
from .posting_adapter import (
    create_and_post_voucher_for_doc,
    find_payment_by_marker,
    post_payment_voucher,
)


class GivenLoanPostingService:
    def post_repayment(self, loan, payment_payload: dict, user):
        """Create and post a GivenLoan repayment receipt."""
        if not hasattr(loan, "create_payment"):
            raise ValueError("post_repayment requires a Loan-like object with create_payment")

        total_amount = self._normalize_money(payment_payload["total_amount"])
        interest_amount = (
            self._normalize_money(payment_payload["interest_amount"])
            if payment_payload.get("interest_amount") is not None
            else None
        )
        principal_amount = payment_payload.get("principal_amount")
        if principal_amount is not None:
            principal_amount = self._normalize_money(principal_amount)
        elif interest_amount is not None:
            principal_amount = total_amount - interest_amount

        with transaction.atomic():
            reference_number = payment_payload.get("reference_number", "")
            if not reference_number:
                reference_number = build_repayment_idempotency_marker(
                    loan,
                    payment_payload,
                    loan_kind="given",
                )
                payment_payload = {**payment_payload, "reference_number": reference_number}
            if reference_number:
                existing = None
                payments = getattr(loan, "payments", None)
                if payments is not None:
                    existing = (
                        payments.filter(
                            direction="RECEIPT",
                            reference_number=reference_number,
                        )
                        .order_by("pk")
                        .first()
                    )
                if existing:
                    return existing, False

            return create_and_post_voucher_for_doc(
                loan,
                direction="RECEIPT",
                payment_type="RECEIPT",
                total_amount=total_amount,
                amount_in_base_currency=total_amount,
                payment_date=payment_payload.get("payment_date", timezone.now()),
                payment_method=payment_payload.get("payment_method", "CASH"),
                reference_number=reference_number,
                description=payment_payload.get("description", ""),
                is_final_payment=bool(payment_payload.get("is_final_payment", False)),
                create_release=False,
                principal_amount=principal_amount,
                interest_amount=interest_amount,
                created_by=user,
            )

    def post_release(self, release, user):
        """Create and post a GivenLoan release receipt."""
        loan = getattr(release, "loan", None)
        if loan is None or not hasattr(loan, "outstanding_principal"):
            raise ValueError("post_release requires a release with a Loan-like .loan")

        snapshot_total = self._release_snapshot_amount(
            release,
            "settlement_total_amount",
        )
        if snapshot_total is not None and snapshot_total > 0:
            outstanding = self._release_snapshot_amount(
                release,
                "settlement_principal_amount",
            )
            interest_amount = self._normalize_money(
                self._release_snapshot_amount(
                    release,
                    "settlement_interest_amount",
                )
            )
            total_amount = self._normalize_money(snapshot_total)
        else:
            outstanding = loan.outstanding_principal
            interest_amount = self._normalize_money(loan.interest_due())
            total_amount = self._normalize_money(outstanding) + interest_amount

        if total_amount.amount <= 0:
            return None, False

        marker = f"RELEASE-{release.pk}"

        # This is a release receipt, not a generic repayment.
        # `create_release=True` ensures the PaymentVoucher is classified as
        # `GIVENLOAN_RELEASE` by PaymentVoucher.get_voucher_type().
        return create_and_post_voucher_for_doc(
            loan,
            direction="RECEIPT",
            payment_type="RECEIPT",
            total_amount=total_amount,
            amount_in_base_currency=total_amount,
            payment_date=release.release_date,
            payment_method="CASH",
            reference_number=marker,
            description=f"Loan release receipt for {loan.loan_id} ({getattr(release, 'release_id', None)})",
            is_final_payment=True,
            create_release=True,
            principal_amount=outstanding,
            interest_amount=interest_amount,
            created_by=user,
        )

    @staticmethod
    def _release_snapshot_amount(release, field_name):
        value = getattr(release, field_name, None)
        if value in (None, ""):
            return None
        amount = getattr(value, "amount", value)
        try:
            return Decimal(str(amount))
        except Exception:
            return None

    def post_auction_recovery(self, loan: GivenLoan, amount, user):
        """Create and post an auction recovery payment for a GivenLoan."""
        return self._record_givenloan_recovery_payment(
            loan=loan,
            user=user,
            amount=amount,
            marker=f"AUCTION-{loan.pk}",
            description=f"Auction recovery receipt for {loan.loan_id}",
            voucher_type="GIVENLOAN_AUCTION",
        )

    def post_sale_recovery(self, loan: GivenLoan, amount, user):
        """Create and post a collateral sale recovery payment for a GivenLoan."""
        return self._record_givenloan_recovery_payment(
            loan=loan,
            user=user,
            amount=amount,
            marker=f"SOLD-{loan.pk}",
            description=f"Collateral sale recovery receipt for {loan.loan_id}",
            voucher_type="GIVENLOAN_SOLD",
        )

    def _normalize_money(self, amount, *, currency="INR"):
        if isinstance(amount, Money):
            return amount
        if isinstance(amount, Decimal):
            return Money(amount, currency)
        return Money(Decimal(str(amount)), currency)

    def _record_givenloan_recovery_payment(
        self,
        *,
        loan: GivenLoan,
        user,
        amount,
        marker: str,
        description: str,
        voucher_type: str,
    ):
        if not isinstance(loan, GivenLoan):
            raise ValueError("Recovery posting supports GivenLoan only")

        money_amount = self._normalize_money(amount)
        if money_amount.amount <= 0:
            raise ValueError("Recovery amount must be positive")

        existing = find_payment_by_marker(loan, marker)
        if existing:
            return existing, False

        payment = loan.create_payment(
            amount=money_amount,
            principal=money_amount,
            interest=Money(0, str(money_amount.currency)),
            payment_method="CASH",
            reference_number=marker,
            description=description,
            payment_date=timezone.now(),
            created_by=user,
        )
        post_payment_voucher(payment, user, voucher_type_override=voucher_type)
        return payment, True
