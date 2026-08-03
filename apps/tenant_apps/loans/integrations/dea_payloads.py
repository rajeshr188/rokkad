"""Stable PawnLoan-to-DEA event contracts; this module never posts accounting."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.tenant_apps.dea import facade as dea_facade
from apps.tenant_apps.loans.domain import TransactionKind


class LoanDeaPayloadError(ValueError):
    """Raised when an accounting event contract is incomplete or inconsistent."""


@dataclass(frozen=True)
class PawnLoanDeaPayload:
    loan_id: int
    loan_number: str
    borrower_id: int
    event_kind: TransactionKind
    effective_date: date
    values: dict[str, Decimal]
    source_event_id: int | None = None
    reversal_of_event_id: int | None = None
    reversal_of_event_kind: TransactionKind | None = None
    reversal_reason: str = ""
    currency: str = "INR"
    contract_version: int = 1

    def __post_init__(self):
        if self.loan_id <= 0 or self.borrower_id <= 0:
            raise LoanDeaPayloadError("Loan and borrower source identities are required.")
        if not self.loan_number:
            raise LoanDeaPayloadError("Official loan number is required.")
        if not self.values:
            raise LoanDeaPayloadError("At least one economic value is required.")
        for name, amount in self.values.items():
            if not name or Decimal(str(amount)) < 0:
                raise LoanDeaPayloadError("Economic values must be named and non-negative.")
        if self.event_kind == TransactionKind.REVERSAL:
            if (
                not self.reversal_of_event_id
                or not self.reversal_of_event_kind
                or not self.reversal_reason.strip()
            ):
                raise LoanDeaPayloadError(
                    "Reversal requires original event identity, kind, and reason."
                )

    @property
    def source_identity(self):
        return {
            "app": "loans",
            "model": "PawnLoan",
            "loan_id": self.loan_id,
            "loan_number": self.loan_number,
            "accounting_event_id": self.source_event_id,
        }

    @property
    def fingerprint(self):
        return hashlib.sha256(
            json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @property
    def idempotency_key(self):
        return f"loans:dea:{self.loan_id}:{self.event_kind.value}:{self.fingerprint}"

    def to_dict(self):
        return {
            "contract_version": self.contract_version,
            "event_kind": self.event_kind.value,
            "effective_date": self.effective_date.isoformat(),
            "currency": self.currency,
            "source_identity": self.source_identity,
            "party": {
                "party_id": self.borrower_id,
                "role_key": "BORROWER",
                "purpose": "BORROWER_LOAN_RECEIVABLE",
            },
            "values": {
                key: format(value.normalize(), "f") for key, value in sorted(self.values.items())
            },
            "reversal": {
                "original_event_id": self.reversal_of_event_id,
                "original_event_kind": self.reversal_of_event_kind.value,
                "reason": self.reversal_reason,
            }
            if self.event_kind == TransactionKind.REVERSAL
            else None,
        }


def disbursal_payload(loan, *, effective_date, principal_amount, source_event_id=None):
    return _payload(
        loan, TransactionKind.DISBURSAL, effective_date, {"principal": principal_amount}, source_event_id
    )


def repayment_payload(
    loan, *, effective_date, principal_amount, interest_amount, fee_amount=Decimal("0"), source_event_id=None
):
    return _payload(
        loan,
        TransactionKind.REPAYMENT,
        effective_date,
        {"principal": principal_amount, "interest": interest_amount, "fees": fee_amount},
        source_event_id,
    )


def accrual_payload(loan, *, effective_date, interest_amount, source_event_id=None):
    return _payload(loan, TransactionKind.INTEREST_ACCRUAL, effective_date, {"interest": interest_amount}, source_event_id)


def capitalization_payload(loan, *, effective_date, interest_amount, source_event_id=None):
    return _payload(loan, TransactionKind.INTEREST_CAPITALIZATION, effective_date, {"interest": interest_amount}, source_event_id)


def release_receipt_payload(
    loan, *, effective_date, principal_amount, interest_amount, fee_amount=Decimal("0"), source_event_id=None
):
    return _payload(
        loan,
        TransactionKind.RELEASE_RECEIPT,
        effective_date,
        {"principal": principal_amount, "interest": interest_amount, "fees": fee_amount},
        source_event_id,
    )


def reversal_payload(
    loan, *, effective_date, original_event_id, original_event_kind, values, reason, source_event_id=None
):
    original_kind = TransactionKind(original_event_kind)
    if original_kind == TransactionKind.REVERSAL:
        raise LoanDeaPayloadError("A reversal cannot reverse another reversal directly.")
    return _payload(
        loan,
        TransactionKind.REVERSAL,
        effective_date,
        values,
        source_event_id,
        reversal_of_event_id=original_event_id,
        reversal_of_event_kind=original_kind,
        reversal_reason=reason,
    )


def resolve_borrower_account(loan, *, create=False):
    """Resolve through DEA's public facade; posting remains DEA-owned."""
    return dea_facade.resolve_party_account(
        loan.borrower,
        role_key="BORROWER",
        purpose="BORROWER_LOAN_RECEIVABLE",
        create=create,
    )


def _payload(loan, kind, effective_date, values, source_event_id, **kwargs):
    return PawnLoanDeaPayload(
        loan_id=loan.pk,
        loan_number=loan.loan_number,
        borrower_id=loan.borrower_id,
        event_kind=kind,
        effective_date=effective_date,
        values={key: Decimal(str(value)) for key, value in values.items()},
        source_event_id=source_event_id,
        **kwargs,
    )
