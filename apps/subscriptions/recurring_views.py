from datetime import datetime, timezone as dt_timezone
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from . import recurring_owner
from .models import RecurringAgreement, RecurringCycle
from .razorpay_service import BillingProviderError
from .views import BillingPermissionMixin, _payment_json


class RecurringDashboardView(LoginRequiredMixin, BillingPermissionMixin, TemplateView):
    template_name = "subscriptions/recurring.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agreement = RecurringAgreement.objects.filter(workspace=self.request.workspace).select_related(
            "binding").order_by("-created_at", "-pk").first()
        context["agreement"] = agreement
        if agreement:
            start_at = agreement.request_snapshot.get("start_at")
            context["scheduled_start"] = datetime.fromtimestamp(start_at, tz=dt_timezone.utc) if start_at else None
            context["schedule_expired"] = bool(start_at and start_at <= timezone.now().timestamp() and
                                                agreement.provider_status == "created")
            context["member_limit"] = next(item["value"] for item in agreement.binding.snapshot["entitlements"]
                                            if item["feature_code"] == "workspace.max_members")
            context["total_amount"] = Decimal(agreement.binding.snapshot["amount"]) / 100
            context["cancellation_requested"] = agreement.events.filter(event_type="cancel.requested").exists()
            context["ended"] = agreement.provider_status in recurring_owner.TERMINAL
            context["can_authorize"] = (settings.BILLING_RECURRING_ENABLED and
                settings.RAZORPAY_KEY_ID.startswith("rzp_test_") and agreement.binding.mode == "test" and
                agreement.state == "verified" and agreement.provider_status == "created" and
                not agreement.closed_at and not context["cancellation_requested"] and not context["schedule_expired"])
            context["can_cancel"] = (agreement.state == "verified" and agreement.binding.mode == "test" and
                settings.RAZORPAY_KEY_ID.startswith("rzp_test_") and
                not agreement.closed_at and not context["ended"] and not context["cancellation_requested"])
            context["cycles"] = agreement.cycles.exclude(access_action="review", access_resolution__isnull=True,
                invoice__billing_resolution__isnull=True).select_related(
                "invoice__billing_resolution", "access_resolution").order_by("-period_end", "-pk")[:12]
            reviews = RecurringCycle.objects.filter(agreement__workspace=self.request.workspace,
                access_action="review", access_resolution__isnull=True,
                invoice__billing_resolution__isnull=True).select_related("invoice").order_by("-period_start", "-pk")
            context["review_cycles"] = Paginator(reviews, 12).get_page(self.request.GET.get("review_page"))
        return context


class RecurringActionView(LoginRequiredMixin, BillingPermissionMixin, View):
    def post(self, request, agreement_id, action, **kwargs):
        args = {"workspace": request.workspace, "actor": request.user, "agreement_id": agreement_id}
        try:
            if action == "authorize":
                return JsonResponse(recurring_owner.authorization_options(**args))
            if action == "confirm":
                data = _payment_json(request)
                recurring_owner.confirm_authorization(**args, payment_id=data.get("razorpay_payment_id"),
                                                       signature=data.get("razorpay_signature"))
                return JsonResponse({"success": True})
            if action == "cancel":
                if request.POST.get("confirm_cancel") != "yes":
                    raise ValidationError("Confirm that you want to stop future renewals.")
                recurring_owner.request_cancellation(**args)
                messages.info(request, "Request saved. Check the agreement status below; already-paid time is preserved.")
            elif action == "refresh":
                recurring_owner.refresh_agreement(**args)
                messages.success(request, "Agreement status refreshed. Paid periods are verified separately.")
            elif action == "recover":
                from .recurring_cycles import reconcile_cycle
                cycle = reconcile_cycle(**args, provider_invoice_id=request.POST.get("provider_invoice_id"),
                                        reason="Owner requested missing recurring invoice recovery")
                if hasattr(cycle, "access_resolution"):
                    messages.info(request, "Payment verified. This period was applied after billing review; current access is shown in Billing.")
                elif cycle.access_action == "review":
                    messages.info(request, "Payment recorded. Workspace access is unchanged and needs a separate billing review.")
                else:
                    messages.success(request, "Paid invoice verified. Access result: " + cycle.access_action + ".")
        except (ValidationError, BillingProviderError) as exc:
            message = exc.messages[0] if isinstance(exc, ValidationError) else str(exc)
            if action in ("authorize", "confirm"):
                return JsonResponse({"error": message}, status=400)
            messages.error(request, message)
        return redirect("workspace_subscriptions:recurring", workspace_slug=request.workspace.slug)
