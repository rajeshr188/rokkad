"""
Views for subscription and payment processing.
Includes checkout, payment confirmation, and invoice management.
"""

import json
from decimal import Decimal, ROUND_HALF_UP
from django.views.generic import ListView, DetailView, TemplateView
from django.views import View
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse, HttpResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import Plan, Subscription, Invoice, ProviderWebhookEvent
from .razorpay_service import BillingProviderError, RazorpayService
from .services import get_workspace_member_usage
from apps.orgs.tenant_context import resolve_request_workspace


class BillingPermissionMixin:
    """Require canonical ownership in the explicit Workspace for billing pages."""

    def dispatch(self, request, *args, **kwargs):
        from .checkout import require_billing_owner
        require_billing_owner(workspace=resolve_request_workspace(request), actor=request.user)
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
        workspace = resolve_request_workspace(self.request)
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
            "approvals_workflow": "Approval Workflow",
            "api_access": "API Access",
            "custom_fields": "Custom Fields",
        }
        context["features"] = all_features
        context["trial_start_enabled"] = settings.BILLING_ALLOW_TRIAL_START

        return context


class StartTrialView(LoginRequiredMixin, BillingPermissionMixin, View):
    """Explicitly start a plan trial; Workspace creation grants no access."""

    def post(self, request, *args, **kwargs):
        if not settings.BILLING_ALLOW_TRIAL_START:
            raise PermissionDenied("Trial activation is disabled.")

        workspace = resolve_request_workspace(request)
        plan = get_object_or_404(Plan, pk=kwargs["plan_id"], is_active=True)

        from apps.subscriptions.billing import start_trial

        try:
            subscription = start_trial(
                workspace=workspace,
                plan=plan,
                actor=request.user,
            )
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
            return redirect(
                "workspace_subscriptions:plan-list",
                workspace_slug=workspace.slug,
            )

        messages.success(
            request,
            f"Your {subscription.plan.name} trial is active until "
            f"{subscription.trial_end_date:%d %b %Y}.",
        )
        return redirect(
            "workspace_slug_dashboard",
            workspace_slug=workspace.slug,
        )


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
        gst_amount = (amount * (gst_rate / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
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


class OrderView(LoginRequiredMixin, BillingPermissionMixin, View):
    def post(self, request, *args, **kwargs):
        from .checkout import create_checkout
        try:
            data = _payment_json(request)
            invoice = create_checkout(
                workspace=resolve_request_workspace(request), actor=request.user,
                plan_id=data.get("plan_id"), billing_cycle=data.get("billing_cycle"),
                request_key=data.get("checkout_key"),
            )
            return JsonResponse({"order_id": invoice.razorpay_order_id,
                                 "amount": invoice.checkout_snapshot["amount"], "currency": "INR"})
        except ValidationError as exc:
            return JsonResponse({"success": False, "error": exc.messages[0]}, status=400)
        except BillingProviderError as exc:
            return JsonResponse({"success": False, "error": str(exc)}, status=502)


class PaymentView(LoginRequiredMixin, BillingPermissionMixin, View):
    def post(self, request, *args, **kwargs):
        from .checkout import confirm_checkout
        workspace = resolve_request_workspace(request)
        try:
            data = _payment_json(request)
            invoice = confirm_checkout(
                workspace=workspace, actor=request.user, order_id=data.get("razorpay_order_id"),
                payment_id=data.get("razorpay_payment_id"), signature=data.get("razorpay_signature"),
            )
            return JsonResponse({"success": True, "subscription_id": invoice.subscription_id,
                                 "redirect_url": reverse("workspace_subscriptions:dashboard",
                                                         kwargs={"workspace_slug": workspace.slug})})
        except ValidationError as exc:
            return JsonResponse({"success": False, "error": exc.messages[0]}, status=400)
        except BillingProviderError as exc:
            return JsonResponse({"success": False, "error": str(exc)}, status=502)


def _payment_json(request):
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValidationError("Provide a JSON object.") from exc
    if not isinstance(data, dict):
        raise ValidationError("Provide a JSON object.")
    return data


class SubscriptionDashboardView(LoginRequiredMixin, BillingPermissionMixin, TemplateView):
    """Customer billing dashboard"""

    template_name = "subscriptions/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get workspace (subscription is linked to workspace, not user)
        workspace = resolve_request_workspace(self.request)
        if not workspace:
            context["subscription"] = None
            context["message"] = "Please select a workspace first."
            return context

        try:
            subscription = workspace.subscription
            context["subscription"] = subscription
            context["plan"] = subscription.plan
            from .billing import effective_billing_state
            context["billing_decision"] = effective_billing_state(subscription)
            context["billing_status_label"] = Subscription.StatusChoices(
                context["billing_decision"].status
            ).label

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
            current_user_count = get_workspace_member_usage(workspace=workspace)
            context["current_user_count"] = current_user_count
            context["user_overage"] = max(
                0, current_user_count - subscription.plan.max_users
            )
            context["overage_charge"] = (
                context["user_overage"] * subscription.plan.extra_user_price
            )
            context["usage_percentage_users"] = (
                min(100, round(current_user_count / subscription.plan.max_users * 100))
                if subscription.plan.max_users > 0
                else 0
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
        workspace = resolve_request_workspace(self.request)
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
        context["review_revision"] = invoice.subscription.updated_at.isoformat()
        return context


class BillingReviewListView(LoginRequiredMixin, BillingPermissionMixin, ListView):
    template_name = "subscriptions/reviews.html"
    context_object_name = "invoices"
    paginate_by = 25

    def get_queryset(self):
        from django.db.models import Q
        return Invoice.objects.filter(
            subscription__company=resolve_request_workspace(self.request), billing_resolution__isnull=True,
        ).exclude(checkout_snapshot={}).filter(
            Q(payment__status="refunded") | Q(status="issued"),
        ).select_related("payment").order_by("-created_at", "-pk")


class ResolveBillingReviewView(LoginRequiredMixin, BillingPermissionMixin, View):
    def post(self, request, *args, **kwargs):
        from .reviews import resolve_billing_review
        workspace = resolve_request_workspace(request)
        try:
            resolve_billing_review(
                workspace=workspace, actor=request.user, invoice_id=kwargs["pk"],
                action=request.POST.get("decision"), reason=request.POST.get("reason"),
                revision=request.POST.get("revision"), payment_id=request.POST.get("payment_id") or None,
                refund_ids=request.POST.get("refund_ids", "").split(),
            )
        except (ValidationError, BillingProviderError) as exc:
            messages.error(request, exc.messages[0] if isinstance(exc, ValidationError) else str(exc))
        else:
            messages.success(request, "Billing review decision recorded.")
        return redirect("workspace_subscriptions:invoice-detail", workspace_slug=workspace.slug, pk=kwargs["pk"])


class ReconcileInvoiceView(LoginRequiredMixin, BillingPermissionMixin, View):
    def post(self, request, *args, **kwargs):
        from .recovery import reconcile_payment
        workspace = resolve_request_workspace(request)
        try:
            result = reconcile_payment(
                workspace=workspace, actor=request.user, invoice_id=kwargs["pk"],
                payment_id=request.POST.get("payment_id"), refund_id=request.POST.get("refund_id") or None,
                reason=request.POST.get("reason"), apply=request.POST.get("action") == "apply",
            )
        except (ValidationError, BillingProviderError) as exc:
            messages.error(request, exc.messages[0] if isinstance(exc, ValidationError) else str(exc))
        else:
            messages.success(request, "Provider records reconciled." if result["applied"] else
                             "Provider identifiers and amounts verified. No changes saved; apply to reconcile.")
        return redirect("workspace_subscriptions:invoice-detail", workspace_slug=workspace.slug, pk=kwargs["pk"])


class InvoicePDFView(LoginRequiredMixin, BillingPermissionMixin, DetailView):
    """Download invoice as PDF"""

    model = Invoice

    def get_object(self):
        # Get workspace (subscription is linked to workspace, not user)
        workspace = resolve_request_workspace(self.request)
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
                50, 690, f"Customer: {invoice.billing_contact_name}"
            )

            # Amount details
            pdf.drawString(50, 650, f"Subtotal: INR {invoice.subtotal}")
            pdf.drawString(50, 635, f"GST ({invoice.gst_rate}%): INR {invoice.gst_amount}")
            pdf.drawString(50, 620, f"Total: INR {invoice.total_amount}")

            pdf.save()

            buffer.seek(0)
            response = HttpResponse(buffer, content_type="application/pdf")
            response[
                "Content-Disposition"
            ] = f'attachment; filename="invoice_{invoice.invoice_number}.pdf"'
            return response

        except Exception as e:
            messages.error(request, f"Error generating PDF: {str(e)}")
            return redirect(
                "workspace_subscriptions:invoice-detail",
                workspace_slug=invoice.subscription.company.slug,
                pk=invoice.id,
            )


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    import hashlib
    import hmac
    import logging

    secret = settings.RAZORPAY_WEBHOOK_SECRET
    signature = request.headers.get("X-Razorpay-Signature", "")
    expected = hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
    if not secret or not signature.isascii() or not hmac.compare_digest(expected, signature):
        return HttpResponse("Signature verification failed", status=400)
    try:
        data = _payment_json(request)
    except ValidationError:
        return HttpResponse("Invalid payload", status=400)
    event_id = request.headers.get("X-Razorpay-Event-Id") or hashlib.sha256(request.body).hexdigest()
    if len(event_id) > 255 or not isinstance(data.get("event"), str) or len(data["event"]) > 100:
        return HttpResponse("Invalid event identity", status=400)
    with transaction.atomic():
        event, _ = ProviderWebhookEvent.objects.get_or_create(
            provider="razorpay", provider_event_id=event_id,
            defaults={"event_type": data["event"], "payload": data},
        )
        event = ProviderWebhookEvent.objects.select_for_update().get(pk=event.pk)
        if event.payload != data:
            return HttpResponse("Event identity already has a different payload", status=400)
        if event.status == ProviderWebhookEvent.StatusChoices.PROCESSED:
            return HttpResponse("Webhook already processed", status=200)
        try:
            with transaction.atomic():
                if not RazorpayService.handle_payment_webhook(data):
                    raise ValidationError("Event requires operator review.")
        except Exception:
            logging.getLogger(__name__).exception("Billing webhook needs review: event %s", event.pk)
            event.status = ProviderWebhookEvent.StatusChoices.FAILED
            event.error_message = "Processing failed; reconcile with provider before retrying."
        else:
            event.status = ProviderWebhookEvent.StatusChoices.PROCESSED
            event.error_message = ""
            event.processed_at = timezone.now()
        event.save(update_fields=["status", "error_message", "processed_at", "updated_at"])
    return HttpResponse("Webhook processed" if not event.error_message else "Webhook needs review",
                        status=200 if not event.error_message else 500)
