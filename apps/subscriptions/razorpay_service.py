"""
Razorpay payment gateway integration for subscription billing.
Documentation: https://razorpay.com/docs/
"""

import os
import razorpay
import hashlib
import hmac
from decimal import Decimal
from datetime import datetime
from .models import Invoice, Payment, Subscription
from django.conf import settings

# Initialize Razorpay client
razorpay_client = razorpay.Client(
    auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
)


class RazorpayService:
    """Service to handle Razorpay payments for subscriptions"""

    @staticmethod
    def create_order(subscription: Subscription, amount: Decimal) -> dict:
        """
        Create a Razorpay order for subscription payment.

        Args:
            subscription: Subscription object
            amount: Amount in INR (will be converted to paise)

        Returns:
            Order details dict containing order_id, amount, etc.
        """
        try:
            # Convert to paise (Razorpay uses paise, not rupees)
            amount_paise = int(amount * 100)

            order_data = {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": f"sub_{subscription.id}_{datetime.now().timestamp()}",
                "payment_capture": 1,  # Auto-capture payment
                "notes": {
                    "subscription_id": subscription.id,
                    "user_email": subscription.user.email,
                    "user_name": subscription.user.get_full_name()
                    or subscription.user.username,
                },
            }

            order = razorpay_client.order.create(data=order_data)
            return order

        except Exception as e:
            raise Exception(f"Failed to create Razorpay order: {str(e)}")

    @staticmethod
    def create_subscription_plan(plan):
        """
        Create a recurring subscription in Razorpay for auto-payments.

        Args:
            plan: Plan object

        Returns:
            Razorpay subscription plan ID
        """
        try:
            # Convert to paise
            amount_paise = int(plan.price * 100)

            # Determine period
            period = "monthly" if plan.billing_cycle == "monthly" else "yearly"

            subscription_plan = razorpay_client.subscription.create(
                plan_id=None,  # Or use existing Razorpay plan ID
                period=period,
                interval=1,
                amount=amount_paise,
                currency="INR",
                receipt=f"plan_{plan.id}_{datetime.now().timestamp()}",
                description=f"{plan.name} subscription",
            )

            return subscription_plan["id"]

        except Exception as e:
            raise Exception(f"Failed to create Razorpay subscription plan: {str(e)}")

    @staticmethod
    def verify_payment_signature(
        razorpay_order_id: str, razorpay_payment_id: str, signature: str
    ) -> bool:
        """
        Verify Razorpay payment signature to ensure payment authenticity.

        Args:
            razorpay_order_id: Order ID from Razorpay
            razorpay_payment_id: Payment ID from Razorpay
            signature: Signature from payment response

        Returns:
            True if signature is valid, False otherwise
        """
        try:
            # Create signature string
            data = f"{razorpay_order_id}|{razorpay_payment_id}"

            # Create HMAC
            key = settings.RAZORPAY_KEY_SECRET.encode("utf-8")
            generated_signature = hmac.new(
                key, data.encode("utf-8"), hashlib.sha256
            ).hexdigest()

            # Compare signatures
            return generated_signature == signature

        except Exception as e:
            print(f"Signature verification failed: {str(e)}")
            return False

    @staticmethod
    def handle_payment_webhook(event_data: dict) -> bool:
        """
        Process webhook from Razorpay payment status updates.

        Args:
            event_data: Event data from Razorpay webhook

        Returns:
            True if processed successfully
        """
        try:
            event = event_data.get("event")
            payload = event_data.get("payload", {})

            if event == "payment.authorized":
                # Payment authorized but not captured
                return True

            elif event == "payment.captured":
                # Payment successfully captured
                payment_data = payload.get("payment", {})
                razorpay_payment_id = payment_data.get("id")
                order_id = payment_data.get("order_id")

                # Find and update invoice
                try:
                    invoice = Invoice.objects.get(razorpay_order_id=order_id)
                    invoice.mark_as_paid(razorpay_payment_id)
                except Invoice.DoesNotExist:
                    print(f"Invoice not found for order {order_id}")
                    return False

                return True

            elif event == "payment.failed":
                # Payment failed
                payment_data = payload.get("payment", {})
                order_id = payment_data.get("order_id")

                try:
                    invoice = Invoice.objects.get(razorpay_order_id=order_id)
                    invoice.status = Invoice.StatusChoices.OVERDUE
                    invoice.save()
                    from apps.subscriptions.billing import transition_subscription

                    transition_subscription(
                        subscription=invoice.subscription,
                        target_status=Subscription.StatusChoices.PAST_DUE,
                        event_type="payment.failed",
                        payload={"provider_order_id": order_id},
                    )
                except Invoice.DoesNotExist:
                    pass

                return True

            elif event == "payment.refunded":
                # Refund processed
                refund_data = payload.get("refund", {})
                payment_data = payload.get("payment", {})
                razorpay_payment_id = payment_data.get("id")

                try:
                    payment = Payment.objects.get(
                        razorpay_payment_id=razorpay_payment_id
                    )
                    payment.status = Payment.PaymentStatusChoices.REFUNDED
                    payment.refund_amount = (
                        Decimal(str(refund_data.get("amount", 0))) / 100
                    )
                    payment.save()
                except Payment.DoesNotExist:
                    pass

                return True

            return True

        except Exception as e:
            print(f"Webhook processing failed: {str(e)}")
            return False

    @staticmethod
    def create_invoice_and_order(
        subscription: Subscription, override_amount=None
    ) -> tuple:
        """
        Create an invoice and corresponding Razorpay order.

        Args:
            subscription: Subscription object
            override_amount: Optional custom amount (for overrides)

        Returns:
            Tuple of (Invoice object, Razorpay order dict)
        """
        try:
            from django.utils import timezone

            # Calculate amount
            if override_amount:
                amount = override_amount
            else:
                amount = subscription.get_total_charges()

            # Create invoice
            invoice = Invoice.objects.create(
                subscription=subscription,
                base_amount=subscription.plan.price
                if not override_amount
                else override_amount,
                overage_amount=Decimal("0.00"),
                invoice_date=timezone.now().date(),
                due_date=(timezone.now() + timezone.timedelta(days=7)).date(),
            )

            # Create Razorpay order
            order = RazorpayService.create_order(subscription, amount)
            invoice.razorpay_order_id = order["id"]
            invoice.save()

            return invoice, order

        except Exception as e:
            raise Exception(f"Failed to create invoice and order: {str(e)}")

    @staticmethod
    def get_payment_status(razorpay_payment_id: str) -> dict:
        """
        Fetch payment status from Razorpay.

        Args:
            razorpay_payment_id: Payment ID from Razorpay

        Returns:
            Payment status dict
        """
        try:
            payment = razorpay_client.payment.fetch(razorpay_payment_id)
            return payment
        except Exception as e:
            raise Exception(f"Failed to fetch payment status: {str(e)}")
