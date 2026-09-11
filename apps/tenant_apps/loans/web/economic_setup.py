"""Economic, interest, fee and monitoring setup; policy rules remain in services."""

from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.web.economic_forms import (
    LoanMonitoringPolicyForm,
    PawnEconomicConfigurationForm,
    PawnFeePolicyForm,
)
from apps.tenant_apps.loans.models import (
    LoanMonitoringPolicy,
    PawnLoanEconomicPolicy,
    PawnLoanFeePolicy,
    PawnMetalInterestRatePolicy,
)
from apps.tenant_apps.loans.services import (
    create_loan_monitoring_policy,
    create_pawn_economic_configuration,
    create_pawn_loan_fee_policy,
)


@loans_setup_required
def pawn_economics_setup(request):
    action = request.POST.get("action") if request.method == "POST" else None
    configuration_form = PawnEconomicConfigurationForm(
        request.POST if action == "configuration" else None,
        workspace=request.loans_workspace,
        initial={"effective_from": timezone.localdate()},
        prefix="configuration",
    )
    fee_form = PawnFeePolicyForm(
        request.POST if action == "fee" else None,
        workspace=request.loans_workspace,
        initial={"effective_from": timezone.localdate()},
        prefix="fee",
    )
    monitoring_form = LoanMonitoringPolicyForm(
        request.POST if action == "monitoring" else None,
        workspace=request.loans_workspace,
        initial={
            "effective_from": timezone.localdate(),
            "compliance_profile": "Workspace monitoring v1",
            "ltv_warning_ratio": Decimal("0.70"),
            "ltv_breach_ratio": Decimal("0.80"),
            "ltv_critical_ratio": Decimal("0.90"),
        },
        prefix="monitoring",
    )
    if action == "configuration" and configuration_form.is_valid():
        data = configuration_form.cleaned_data
        try:
            create_pawn_economic_configuration(
                workspace=request.loans_workspace,
                actor=request.user,
                **data,
            )
        except (ValidationError, ValueError) as exc:
            configuration_form.add_error(None, str(exc))
        else:
            messages.success(request, "PawnLoan economic configuration added.")
            return redirect('workspace_loans:pawn_economics_setup', workspace_slug=request.workspace.slug)
    if action == "fee" and fee_form.is_valid():
        try:
            create_pawn_loan_fee_policy(
                workspace=request.loans_workspace,
                actor=request.user,
                **fee_form.cleaned_data,
            )
        except (ValidationError, ValueError) as exc:
            fee_form.add_error(None, str(exc))
        else:
            messages.success(request, "PawnLoan fee policy added.")
            return redirect('workspace_loans:pawn_economics_setup', workspace_slug=request.workspace.slug)
    if action == "monitoring" and monitoring_form.is_valid():
        try:
            create_loan_monitoring_policy(
                workspace=request.loans_workspace,
                actor=request.user,
                **monitoring_form.cleaned_data,
            )
        except (ValidationError, ValueError) as exc:
            monitoring_form.add_error(None, str(exc))
        else:
            messages.success(request, "Loan monitoring policy added.")
            return redirect('workspace_loans:pawn_economics_setup', workspace_slug=request.workspace.slug)
    context = {
        "configuration_form": configuration_form,
        "fee_form": fee_form,
        "monitoring_form": monitoring_form,
        "economic_policies": PawnLoanEconomicPolicy.objects.filter(
            workspace=request.loans_workspace
        ).select_related("license"),
        "rate_policies": PawnMetalInterestRatePolicy.objects.filter(
            workspace=request.loans_workspace
        ).select_related("license"),
        "fee_policies": PawnLoanFeePolicy.objects.filter(
            workspace=request.loans_workspace
        ).select_related("license"),
        "monitoring_policies": LoanMonitoringPolicy.objects.filter(
            workspace=request.loans_workspace
        ).select_related("license"),
    }
    return render(request, "loans/setup/economics.html", context)
