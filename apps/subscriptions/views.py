"""
Views for subscription and payment processing.
Includes checkout, payment confirmation, and invoice management.
"""

import json
from decimal import Decimal
from datetime import datetime
from django.views.generic import ListView, DetailView, CreateView, TemplateView
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.urls import reverse
from django.core.exceptions import PermissionDenied

from .models import Plan, Subscription, Invoice, Payment
from .razorpay_service import RazorpayService
from apps.orgs.tenant_context import resolve_request_workspace


class BillingPermissionMixin:
    """Require workspace owner role in current workspace for billing pages."""

    OWNER_ROLE_NAMES = {"Owner"}

    def dispatch(self, request, *args, **kwargs):
        workspace = resolve_request_workspace(request, allow_profile_fallback=True)

        from apps.orgs.models import Membership

        membership = None
        if not workspace:
            # Public-schema convenience: auto-select first available workspace
            # so billing links work without forcing an extra click.
            membership = (
                Membership.objects.select_related("company", "role")
                .filter(user=request.user, company__is_deleted=False)
                .order_by("created")
                .first()
            )
            if membership:
                workspace = membership.company
                if hasattr(request.user, "profile"):
                    request.user.profile.set_workspace(workspace)
            else:
                messages.error(request, "Please select a workspace first.")
                return redirect("workspace_selector")

        # Platform admins always have access
        from apps.orgs.permissions import is_platform_admin

        if is_platform_admin(request.user):
            return super().dispatch(request, *args, **kwargs)

        if membership is None:
            try:
                membership = Membership.objects.select_related("role").get(
                    user=request.user,
                    company=workspace,
                )
            except Membership.DoesNotExist:
                raise PermissionDenied("Not a workspace member")

        # Billing is strictly owner-only.
        role_name = membership.role.name if membership.role else ""
        if role_name not in self.OWNER_ROLE_NAMES:
            raise PermissionDenied("Only workspace owners can access billing")

        return super().dispatch(request, *args, **kwargs)


class SubscriptionPlanListView(LoginRequiredMixin, BillingPermissionMixin, ListView):
    """Display available subscription plans"""

    model = Plan
    template_name = "subscriptions/plan_list.html"
    context_object_name = "plans"

    def get_queryset(self):
        return Plan.objects.filter(is_active=True).order_by("price")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get current subscription if exists (subscription is linked to workspace)
        workspace = resolve_request_workspace(self.request, allow_profile_fallback=True)
        try:
            if workspace:
                context["current_subscription"] = workspace.subscription
                context["current_plan"] = workspace.subscription.plan
            else:
                context["current_subscription"] = None
                context["current_plan"] = None
        except Subscription.DoesNotExist:
            context["current_subscription"] = None
            context["current_plan"] = None

        # Calculate features comparison
        all_features = {
            "advanced_reporting": "Advanced Reporting",
            "multi_warehouse": "Multi-Warehouse Support",
            "approvals_workflow": "Approval Workflow",
            "api_access": "API Access",
            "custom_fields": "Custom Fields",
        }
        context["features"] = all_features

        return context


class CheckoutView(LoginRequiredMixin, BillingPermissionMixin, TemplateView):
    """Checkout page - display plan details and payment form"""

    template_name = "subscriptions/checkout.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        plan_id = self.kwargs.get("plan_id")
        billing_cycle = self.request.GET.get("billing_cycle", "monthly")

        plan = get_object_or_404(Plan, id=plan_id, is_active=True)

        # Calculate amount based on billing cycle
        if billing_cycle == "yearly" and plan.yearly_price:
            amount = plan.yearly_price
        else:
            amount = plan.price
            billing_cycle = "monthly"

        # Calculate GST
        gst_rate = Decimal(str(getattr(settings, "BILLING_TAX_RATE", "18")))
        gst_amount = amount * (gst_rate / Decimal("100"))
        total_amount = amount + gst_amount

        context.update(
            {
                "plan": plan,
                "billing_cycle": billing_cycle,
                "base_amount": amount,
                "gst_rate": gst_rate,
                "gst_amount": gst_amount,
                "total_amount": total_amount,
                "razorpay_key_id": settings.RAZORPAY_KEY_ID,
            }
        )

        return context


class PaymentView(LoginRequiredMixin, BillingPermissionMixin, CreateView):
    """Process payment and create subscription"""

    model = Subscription
    fields = []

    @require_POST
    def post(self, request, *args, **kwargs):
        """Handle payment creation"""

        try:
            data = json.loads(request.body)

            plan_id = data.get("plan_id")
            razorpay_payment_id = data.get("razorpay_payment_id")
            razorpay_order_id = data.get("razorpay_order_id")
            razorpay_signature = data.get("razorpay_signature")

            # Verify payment signature
            if not RazorpayService.verify_payment_signature(
                razorpay_order_id, razorpay_payment_id, razorpay_signature
            ):
                return JsonResponse(
                    {"success": False, "error": "Payment verification failed"},
                    status=400,
                )

            plan = get_object_or_404(Plan, id=plan_id)

            # Create or update subscription
            subscription, created = Subscription.objects.update_or_create(
                user=request.user,
                defaults={
                    "plan": plan,
                    "status": Subscription.StatusChoices.ACTIVE,
                },
            )

            # Update invoice as paid
            try:
                invoice = Invoice.objects.get(razorpay_order_id=razorpay_order_id)
                invoice.mark_as_paid(razorpay_payment_id)
            except Invoice.DoesNotExist:
                pass

            # Create payment record
            Payment.objects.create(
                invoice=invoice,
                razorpay_payment_id=razorpay_payment_id,
                razorpay_order_id=razorpay_order_id,
                amount=invoice.total_amount,
                status=Payment.PaymentStatusChoices.CAPTURED,
                payment_date=datetime.now(),
            )

            # Send confirmation email
            _send_subscription_confirmation_email(request.user, subscription)

            return JsonResponse(
                {
                    "success": True,
                    "message": "Payment successful",
                    "subscription_id": subscription.id,
                    "redirect_url": reverse("subscriptions:dashboard"),
                }
            )

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)


class SubscriptionDashboardView(LoginRequiredMixin, BillingPermissionMixin, TemplateView):
    """Customer billing dashboard"""

    template_name = "subscriptions/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get workspace (subscription is linked to workspace, not user)
        workspace = resolve_request_workspace(self.request, allow_profile_fallback=True)
        if not workspace:
            context["subscription"] = None
            context["message"] = "Please select a workspace first."
            return context

        try:
            subscription = workspace.subscription
            context["subscription"] = subscription
            context["plan"] = subscription.plan

            # Get recent invoices
            context["recent_invoices"] = Invoice.objects.filter(
                subscription=subscription
            ).order_by("-invoice_date")[:5]

            # Get usage metrics
            from .models import UsageMetrics

            try:
                context["current_usage"] = UsageMetrics.objects.filter(
                    subscription=subscription
                ).latest("date")
            except UsageMetrics.DoesNotExist:
                context["current_usage"] = None

            # Calculate overage
            context["user_overage"] = max(
                0, subscription.current_user_count - subscription.plan.max_users
            )
            context["overage_charge"] = (
                context["user_overage"] * subscription.plan.extra_user_price
            )

            # Days until renewal
            context["days_until_renewal"] = subscription.days_until_renewal()
            context["is_trial"] = subscription.is_trial_active()

        except Subscription.DoesNotExist:
            context["subscription"] = None
            context["message"] = "No active subscription. Please set up billing."

        return context


class InvoiceDetailView(LoginRequiredMixin, BillingPermissionMixin, DetailView):
    """View invoice details"""

    model = Invoice
    template_name = "subscriptions/invoice_detail.html"
    context_object_name = "invoice"

    def get_object(self):
        # Get workspace (subscription is linked to workspace, not user)
        workspace = resolve_request_workspace(self.request, allow_profile_fallback=True)
        if not workspace:
            raise Http404("No workspace selected")

        invoice = get_object_or_404(
            Invoice, id=self.kwargs["pk"], subscription__company=workspace
        )
        return invoice

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.get_object()
        context["subscription"] = invoice.subscription
        context["gst_percentage"] = invoice.gst_rate
        return context


class InvoicePDFView(LoginRequiredMixin, BillingPermissionMixin, DetailView):
    """Download invoice as PDF"""

    model = Invoice

    def get_object(self):
        # Get workspace (subscription is linked to workspace, not user)
        workspace = resolve_request_workspace(self.request, allow_profile_fallback=True)
        if not workspace:
            raise Http404("No workspace selected")

        return get_object_or_404(
            Invoice, id=self.kwargs["pk"], subscription__company=workspace
        )

    def get(self, request, *args, **kwargs):
        invoice = self.get_object()

        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            from io import BytesIO

            # Create PDF (simplified - use django-weasyprint or similar for better results)
            buffer = BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=letter)

            # Title
            pdf.setFont("Helvetica-Bold", 16)
            pdf.drawString(50, 750, "INVOICE")

            # Invoice details
            pdf.setFont("Helvetica", 10)
            pdf.drawString(50, 720, f"Invoice #: {invoice.invoice_number}")
            pdf.drawString(50, 705, f"Date: {invoice.invoice_date}")
            pdf.drawString(
                50, 690, f"Customer: {invoice.subscription.user.get_full_name()}"
            )

            # Amount details
            pdf.drawString(50, 650, f"Subtotal: ₹{invoice.subtotal}")
            pdf.drawString(50, 635, f"GST ({invoice.gst_rate}%): ₹{invoice.gst_amount}")
            pdf.drawString(50, 620, f"Total: ₹{invoice.total_amount}")

            pdf.save()

            buffer.seek(0)
            response = HttpResponse(buffer, content_type="application/pdf")
            response[
                "Content-Disposition"
            ] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
            return response

        except Exception as e:
            messages.error(request, f"Error generating PDF: {str(e)}")
            return redirect("subscriptions:invoice-detail", pk=invoice.id)


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    """
    Handle Razorpay webhook events.
    https://razorpay.com/docs/webhooks/
    """

    try:
        # Get webhook signature
        razorpay_signature = request.META.get("HTTP_X_RAZORPAY_SIGNATURE")
        webhook_body = request.body

        # Verify webhook signature
        import hmac
        import hashlib

        key = settings.RAZORPAY_WEBHOOK_SECRET.encode("utf-8")
        generated_signature = hmac.new(key, webhook_body, hashlib.sha256).hexdigest()

        if generated_signature != razorpay_signature:
            return HttpResponse("Signature verification failed", status=400)

        # Parse and process event
        event_data = json.loads(webhook_body)
        RazorpayService.handle_payment_webhook(event_data)

        return HttpResponse("Webhook processed", status=200)

    except Exception as e:
        print(f"Webhook error: {str(e)}")
        return HttpResponse("Webhook processing failed", status=500)


# ============================================================================
# Helper Functions
# ============================================================================


def _send_subscription_confirmation_email(user, subscription):
    """Send subscription confirmation email"""

    subject = f"Welcome to {subscription.plan.name} Plan!"

    context = {
        "user": user,
        "plan": subscription.plan,
        "subscription": subscription,
        "support_email": getattr(
            settings, "BILLING_EMAIL_SUPPORT", "support@rokkad.com"
        ),
    }

    html_message = render_to_string(
        "subscriptions/emails/subscription_confirmation.html", context
    )
    plain_message = strip_tags(html_message)

    send_mail(
        subject,
        plain_message,
        getattr(settings, "BILLING_EMAIL_SENDER", "billing@rokkad.com"),
        [user.email],
        html_message=html_message,
        fail_silently=True,
    )


def _send_invoice_email(invoice):
    """Send invoice email to customer"""

    subject = f"Invoice {invoice.invoice_number} from Rokkad"

    context = {
        "user": invoice.subscription.user,
        "invoice": invoice,
        "subscription": invoice.subscription,
    }

    html_message = render_to_string("subscriptions/emails/invoice.html", context)
    plain_message = strip_tags(html_message)

    send_mail(
        subject,
        plain_message,
        getattr(settings, "BILLING_EMAIL_SENDER", "billing@rokkad.com"),
        [invoice.subscription.user.email],
        html_message=html_message,
        fail_silently=True,
    )
