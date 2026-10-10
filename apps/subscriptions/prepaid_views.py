from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from apps.orgs.models import Company
from .views import BillingPermissionMixin, _payment_json
from .razorpay_service import BillingProviderError
from . import public_prepaid


class AnnualPrepaidView(LoginRequiredMixin, BillingPermissionMixin, TemplateView):
    template_name = 'subscriptions/annual_prepaid.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(public_prepaid.offer_context(workspace=self.request.workspace, actor=self.request.user))
        return context


class AnnualPrepaidStartView(LoginRequiredMixin, View):
    """Global CSRF-protected adapter; the service owns durable transaction boundaries."""
    def post(self, request):
        try:
            data = _payment_json(request)
            consent = public_prepaid.read_consent(data.get('offer_token'), request.user)
            if data.get('accepted_terms') != public_prepaid.TERMS:
                raise ValidationError('Accept the annual prepaid terms before continuing.')
            workspace = Company.all_objects.filter(pk=consent.get('workspace_id')).first()
            if workspace is None:
                raise ValidationError('This Workspace is unavailable.')
            invoice = public_prepaid.prepare_purchase(workspace_id=workspace.pk,
                actor=request.user, consent=consent)
            options = public_prepaid.payment_options(workspace_id=workspace.pk,
                actor=request.user, invoice_id=invoice.pk)
            return JsonResponse({**options, 'redirect_url': reverse('workspace_subscriptions:dashboard',
                kwargs={'workspace_slug': workspace.slug})})
        except (ValidationError, BillingProviderError) as exc:
            return JsonResponse({'error': exc.messages[0] if isinstance(exc, ValidationError) else str(exc)}, status=400)
