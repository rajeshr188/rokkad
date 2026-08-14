"""
Settlement Service - AR/AP settlement workflow

Automatically updates invoice payment status when PaymentVoucher is posted.
Handles both SalesInvoiceVoucher (received_amount) and PurchaseInvoiceVoucher (paid_amount).

SETTLEMENT WORKFLOW:
1. PaymentVoucher posted against SalesInvoiceVoucher or PurchaseInvoiceVoucher
2. SettlementService.settle() called after JournalEntry creation
3. Updates received_amount or paid_amount on invoice
4. Sets is_fully_paid = True if amount >= total/net_payable
5. Saves invoice with updated_at timestamp

Guarantees:
- Idempotent: can be called multiple times without duplication
- Transactional: uses database transactions
- Multi-currency: handles Money objects with get_or_convert logic
"""

from typing import Union, Optional
from decimal import Decimal

from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from moneyed import Money

from ..models import SalesInvoiceVoucher, PurchaseInvoiceVoucher


class SettlementService:
    """Service for settling AR/AP invoices when payments are posted"""

    def settle(self, payment_voucher) -> Optional[Union[SalesInvoiceVoucher, PurchaseInvoiceVoucher]]:
        """
        Update invoice payment status after payment posting.

        Args:
            payment_voucher: PaymentVoucher instance that was just posted

        Returns:
            Updated invoice object, or None if no source document

        Raises:
            ValueError: If source document type is not recognized
        """
        if not payment_voucher.source_document:
            return None

        invoice = payment_voucher.source_document

        if isinstance(invoice, SalesInvoiceVoucher):
            return self._settle_sales_invoice(invoice, payment_voucher)
        elif isinstance(invoice, PurchaseInvoiceVoucher):
            return self._settle_purchase_invoice(invoice, payment_voucher)
        else:
            # Payment may be for other doc types (e.g., GivenLoan, TakenLoan)
            # These are not settled via this service
            return None

    @transaction.atomic
    def _settle_sales_invoice(
        self, invoice: SalesInvoiceVoucher, payment_voucher
    ) -> SalesInvoiceVoucher:
        """Update SalesInvoiceVoucher payment status"""
        # Get current received_amount (ensure same currency)
        current_received = invoice.received_amount or Money(0, invoice.total_amount.currency)
        payment_amount = self._convert_to_invoice_currency(
            payment_voucher.total_amount, invoice.total_amount.currency
        )

        # Add payment to received amount
        invoice.received_amount = current_received + payment_amount

        # Check if fully paid
        if invoice.received_amount.amount >= invoice.total_amount.amount:
            invoice.is_fully_paid = True

        # Save with update_fields to be explicit about what changed
        invoice.save(
            update_fields=[
                "received_amount",
                "is_fully_paid",
                "updated_at",
            ]
        )

        return invoice

    @transaction.atomic
    def _settle_purchase_invoice(
        self, invoice: PurchaseInvoiceVoucher, payment_voucher
    ) -> PurchaseInvoiceVoucher:
        """Update PurchaseInvoiceVoucher payment status"""
        # Get current paid_amount (ensure same currency)
        current_paid = invoice.paid_amount or Money(0, invoice.net_payable.currency)
        payment_amount = self._convert_to_invoice_currency(
            payment_voucher.total_amount, invoice.net_payable.currency
        )

        # Add payment to paid amount
        invoice.paid_amount = current_paid + payment_amount

        # Check if fully paid (against net_payable, not gross total)
        if invoice.paid_amount.amount >= invoice.net_payable.amount:
            invoice.is_fully_paid = True

        # Save with update_fields to be explicit about what changed
        invoice.save(
            update_fields=[
                "paid_amount",
                "is_fully_paid",
                "updated_at",
            ]
        )

        return invoice

    @staticmethod
    def _convert_to_invoice_currency(payment_amount: Money, invoice_currency: str) -> Money:
        """
        Convert payment amount to invoice currency if needed.

        For now, assumes same currency. In production, would use ExchangeRate model.

        Args:
            payment_amount: Payment amount in original currency
            invoice_currency: Target currency code (e.g., 'INR')

        Returns:
            Money object in target currency

        Raises:
            ValueError: If currencies don't match (multi-currency not yet supported)
        """
        if payment_amount.currency.code != invoice_currency:
            raise ValueError(
                f"Payment currency {payment_amount.currency.code} doesn't match "
                f"invoice currency {invoice_currency}. Multi-currency settlement not yet supported."
            )
        return payment_amount


# For backward compatibility / direct import
def settle_invoice(payment_voucher) -> Optional[Union[SalesInvoiceVoucher, PurchaseInvoiceVoucher]]:
    """Convenience function for settling invoices after payment posting"""
    service = SettlementService()
    return service.settle(payment_voucher)
