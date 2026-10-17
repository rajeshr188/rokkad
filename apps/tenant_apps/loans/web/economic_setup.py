"""Economic, interest, fee and monitoring setup; policy rules remain in services."""

from decimal import Decimal

from apps.onboarding.navigation import setup_saved_redirect

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.forms.models import model_to_dict
from django.http import Http404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.utils.translation import gettext as _

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.web.economic_forms import (
    LoanMonitoringPolicyForm,
    PawnEconomicConfigurationForm,
    PawnFeePolicyForm,
    PawnSeriesInterestForm,
)
from apps.tenant_apps.loans.services.monitoring_policies import cancellation_values
from apps.tenant_apps.loans.services.monitoring_policy_reviews import (
    preview_monitoring_policy,
    confirm_monitoring_policy,
)
from apps.tenant_apps.loans.services.economic_policy_reviews import (
    preview_economic_change,
    confirm_economic_change,
)
from apps.tenant_apps.loans.services.economic_policies import (
    PawnEconomicPolicyError,
    resolve_pawn_metal_interest_rate_policy,
)
from apps.tenant_apps.loans.models import (
    LoanMonitoringPolicy,
    PawnLoanEconomicPolicy,
    PawnLoanFeePolicy,
    PawnMetalInterestRatePolicy,
)
from apps.tenant_apps.loans.services import (
    create_loan_monitoring_policy,
    create_pawn_loan_fee_policy,
)
from .lending_setup_forms import (
    BusinessLendingTermsForm,
    LendingRatesForm,
    LendingTermsAmendForm,
    LoanEntryPreferenceForm,
    LendingTermsPreviewForm,
)
from apps.tenant_apps.loans.selectors.lending_terms import effective_lending_terms


@loans_setup_required
@never_cache
def pawn_economics_setup(request):
    action = request.POST.get("action") if request.method == "POST" else None
    terms_query = request.GET.copy()
    terms_query.setdefault("effective_from", timezone.localdate().isoformat())
    if action in {"rates", "terms", "entry"}:
        for name in ("license", "series", "effective_from"):
            terms_query[name] = request.POST.get(f"{action}-{name}", "")
    effective_form = LendingTermsPreviewForm(
        terms_query, workspace=request.loans_workspace
    )
    effective_terms = None
    scope_initial = {}
    if effective_form.is_valid():
        scope = effective_form.cleaned_data
        effective_terms = effective_lending_terms(
            workspace=request.loans_workspace,
            license=scope["license"],
            series=scope["series"],
            day=scope["effective_from"],
        )
        scope_initial = {
            "license": scope["license"],
            "series": scope["series"],
            "effective_from": max(timezone.localdate(), scope["effective_from"]),
        }
    configuration_initial = {"effective_from": timezone.localdate()}
    source_policy = None
    if request.method == "GET":
        copy_id = request.GET.get("copy_economics")
        policies = PawnLoanEconomicPolicy.objects.filter(
            workspace=request.loans_workspace
        )
        if copy_id:
            try:
                source_policy = get_object_or_404(policies, pk=int(copy_id))
            except (ValueError, TypeError) as exc:
                raise Http404("Calculation policy not found.") from exc
        elif scope_initial.get("license") or scope_initial.get("series"):
            source_policy = effective_terms.get("policy") if effective_terms else None
        else:
            source_policy = (
                policies.filter(
                    license__isnull=True,
                    series__isnull=True,
                    is_active=True,
                    effective_from__lte=timezone.localdate(),
                )
                .filter(
                    Q(effective_until__isnull=True)
                    | Q(effective_until__gte=timezone.localdate())
                )
                .order_by("-effective_from", "-revision", "-pk")
                .first()
            )
        if source_policy:
            configuration_initial.update(
                model_to_dict(
                    source_policy,
                    fields=tuple(PawnEconomicConfigurationForm.base_fields),
                )
            )
            configuration_initial["effective_from"] = max(
                timezone.localdate(), source_policy.effective_from
            )
            if not copy_id:
                configuration_initial.update(scope_initial)
            configured_metals = []
            for metal in ("GOLD", "SILVER", "BRONZE"):
                try:
                    rate = resolve_pawn_metal_interest_rate_policy(
                        workspace_id=request.loans_workspace.pk,
                        license_id=(
                            configuration_initial.get("license").pk
                            if hasattr(configuration_initial.get("license"), "pk")
                            else configuration_initial.get("license")
                        ),
                        metal=metal,
                        series_id=(
                            configuration_initial.get("series").pk
                            if hasattr(configuration_initial.get("series"), "pk")
                            else configuration_initial.get("series")
                        ),
                        as_of_date=configuration_initial["effective_from"],
                    )
                except PawnEconomicPolicyError:
                    continue
                configuration_initial[f"{metal.lower()}_monthly_interest_rate"] = (
                    rate.monthly_interest_rate
                )
                configured_metals.append(metal)
            if configured_metals:
                precious = [metal for metal in configured_metals if metal != "BRONZE"]
                configuration_initial["metals_to_configure"] = (
                    "BOTH"
                    if len(precious) == 2
                    else precious[0] if precious else "BRONZE"
                )
    configuration_form = BusinessLendingTermsForm(
        (
            request.POST
            if request.method == "POST"
            and action
            not in {"fee", "monitoring", "series_rates", "rates", "terms", "entry"}
            else None
        ),
        workspace=request.loans_workspace,
        initial=configuration_initial,
        prefix="configuration",
    )
    fee_form = PawnFeePolicyForm(
        request.POST if action == "fee" else None,
        workspace=request.loans_workspace,
        initial={"effective_from": timezone.localdate()},
        prefix="fee",
    )
    series_rate_form = PawnSeriesInterestForm(
        request.POST if action == "series_rates" else None,
        workspace=request.loans_workspace,
        initial={"effective_from": timezone.localdate()},
        prefix="series-rates",
    )
    series_review, series_review_token = None, ""
    if action == "series_rates" and series_rate_form.is_valid():
        try:
            if request.POST.get("economic_confirm") == "1":
                confirm_economic_change(
                    workspace=request.loans_workspace,
                    actor=request.user,
                    kind=action,
                    values=series_rate_form.cleaned_data,
                    token=request.POST.get("economic_review_token"),
                    acknowledged=request.POST.get("economic_acknowledged") == "on",
                )
                messages.success(
                    request,
                    "Series monthly interest rates added. Approved loans retain their agreed rates.",
                )
                return setup_saved_redirect(request, step="terms") or redirect(
                    "workspace_loans:pawn_economics_setup",
                    workspace_slug=request.workspace.slug,
                )
            series_review, series_review_token = preview_economic_change(
                workspace=request.loans_workspace,
                actor=request.user,
                kind=action,
                values=series_rate_form.cleaned_data,
            )
        except (ValidationError, ValueError) as exc:
            series_rate_form.add_error(None, str(exc))
    monitoring_initial = {
        "effective_from": timezone.localdate(),
        "compliance_profile": "Workspace monitoring v1",
        "ltv_warning_ratio": Decimal("0.70"),
        "ltv_breach_ratio": Decimal("0.80"),
        "ltv_critical_ratio": Decimal("0.90"),
    }
    amendment = None
    amendment_id = request.GET.get("amend_monitoring") or request.GET.get(
        "cancel_monitoring"
    )
    if request.method == "GET":
        if amendment_id:
            try:
                amendment_id = int(amendment_id)
            except (ValueError, TypeError) as exc:
                raise Http404("Monitoring policy not found.") from exc
            amendment = get_object_or_404(
                LoanMonitoringPolicy,
                pk=amendment_id,
                workspace=request.loans_workspace,
                successor__isnull=True,
            )
        elif request.GET.get("new_monitoring") != "1":
            amendment = LoanMonitoringPolicy.objects.filter(
                workspace=request.loans_workspace,
                license__isnull=True,
                successor__isnull=True,
                effective_until__isnull=True,
            ).first()
        if amendment is not None:
            monitoring_initial.update(
                model_to_dict(amendment, fields=LoanMonitoringPolicyForm.Meta.fields)
            )
            monitoring_initial.update(
                supersedes=amendment.pk,
                amendment_reason="",
                effective_from=max(timezone.localdate(), amendment.effective_from),
            )
            if request.GET.get("cancel_monitoring"):
                try:
                    monitoring_initial.update(cancellation_values(amendment))
                    monitoring_initial.update(
                        license=amendment.license_id,
                        supersedes=amendment.pk,
                        cancel_scheduled=True,
                    )
                except ValidationError as exc:
                    raise Http404(str(exc)) from exc
    monitoring_form = LoanMonitoringPolicyForm(
        request.POST if action == "monitoring" else None,
        workspace=request.loans_workspace,
        initial=monitoring_initial,
        actor=request.user,
        prefix="monitoring",
    )
    if request.method == "POST" and action not in {
        "configuration",
        "fee",
        "monitoring",
        "series_rates",
        "rates",
        "terms",
        "entry",
    }:
        configuration_form.add_error(
            None, _("Choose which policy to save and try again.")
        )
    configuration_review, configuration_review_token = None, ""
    if action == "configuration" and configuration_form.is_valid():
        data = configuration_form.cleaned_data
        try:
            if request.POST.get("economic_confirm") == "1":
                confirm_economic_change(
                    workspace=request.loans_workspace,
                    actor=request.user,
                    kind=action,
                    values=data,
                    token=request.POST.get("economic_review_token"),
                    acknowledged=request.POST.get("economic_acknowledged") == "on",
                )
                messages.success(
                    request,
                    "New calculation policy version saved. Earlier approved loans retain their agreed terms.",
                )
                return setup_saved_redirect(request, step="terms") or redirect(
                    "workspace_loans:pawn_economics_setup",
                    workspace_slug=request.workspace.slug,
                )
            configuration_review, configuration_review_token = preview_economic_change(
                workspace=request.loans_workspace,
                actor=request.user,
                kind=action,
                values=data,
            )
        except (ValidationError, ValueError) as exc:
            for message in (
                exc.messages if isinstance(exc, ValidationError) else [str(exc)]
            ):
                configuration_form.add_error(None, message)
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
            return setup_saved_redirect(request, step="terms") or redirect(
                "workspace_loans:pawn_economics_setup",
                workspace_slug=request.workspace.slug,
            )
    monitoring_review, monitoring_review_token = None, ""
    if action == "monitoring" and monitoring_form.is_valid():
        try:
            values = dict(monitoring_form.cleaned_data)
            cancelling = values.pop("cancel_scheduled", False)
            if cancelling:
                if not values.get("supersedes"):
                    raise ValidationError(
                        "Choose the latest scheduled policy before cancelling."
                    )
                values = dict(
                    cancellation_values(values["supersedes"]),
                    amendment_reason=values["amendment_reason"],
                )
            if request.POST.get("monitoring_confirm") == "1":
                confirm_monitoring_policy(
                    workspace=request.loans_workspace,
                    actor=request.user,
                    review_token=request.POST.get("monitoring_review_token"),
                    acknowledged=request.POST.get("monitoring_acknowledged") == "on",
                    **values,
                )
                messages.success(
                    request,
                    "Monitoring policy version saved. Earlier evidence is retained.",
                )
                return setup_saved_redirect(request, step="terms") or redirect(
                    "workspace_loans:pawn_economics_setup",
                    workspace_slug=request.workspace.slug,
                )
            monitoring_review, monitoring_review_token = preview_monitoring_policy(
                workspace=request.loans_workspace, actor=request.user, **values
            )
        except (ValidationError, ValueError) as exc:
            monitoring_form.add_error(None, str(exc))
    narrow_forms = []
    for kind, form_class, label in (
        ("rates", LendingRatesForm, "Monthly interest rates"),
        ("terms", LendingTermsAmendForm, "Tenure and upfront interest"),
        ("entry", LoanEntryPreferenceForm, "Default New loan screen"),
    ):
        form = form_class(
            request.POST if action == kind else None,
            workspace=request.loans_workspace,
            prefix=kind,
            initial=scope_initial,
        )
        review, token = None, ""
        if action == kind and form.is_valid():
            try:
                if request.POST.get("economic_confirm") == "1":
                    confirm_economic_change(
                        workspace=request.loans_workspace,
                        actor=request.user,
                        kind=kind,
                        values=form.cleaned_data,
                        token=request.POST.get("economic_review_token"),
                        acknowledged=request.POST.get("economic_acknowledged") == "on",
                    )
                    messages.success(
                        request,
                        "Change saved. Existing agreements and monitoring retain their rules.",
                    )
                    return setup_saved_redirect(request, step="terms") or redirect(
                        "workspace_loans:pawn_economics_setup",
                        workspace_slug=request.workspace.slug,
                    )
                review, token = preview_economic_change(
                    workspace=request.loans_workspace,
                    actor=request.user,
                    kind=kind,
                    values=form.cleaned_data,
                )
            except (ValidationError, ValueError) as exc:
                form.add_error(None, str(exc))
        narrow_forms.append(
            dict(kind=kind, form=form, label=label, review=review, token=token)
        )
    context = {
        "narrow_forms": narrow_forms,
        "narrow_change_active": action in {"rates", "terms", "entry"},
        "effective_terms_form": effective_form,
        "effective_lending_terms": effective_terms,
        "configuration_form": configuration_form,
        "configuration_source": source_policy,
        "configuration_review": configuration_review,
        "configuration_review_token": configuration_review_token,
        "series_review": series_review,
        "series_review_token": series_review_token,
        "series_rate_form": series_rate_form,
        "fee_form": fee_form,
        "monitoring_form": monitoring_form,
        "monitoring_amendment": amendment,
        "monitoring_review": monitoring_review,
        "monitoring_review_token": monitoring_review_token,
        "monitoring_cancelling": (
            getattr(monitoring_form, "cleaned_data", {}).get("cancel_scheduled", False)
            if monitoring_form.is_bound
            else bool(monitoring_initial.get("cancel_scheduled", False))
        ),
        "monitoring_today": timezone.localdate(),
        "economic_policies": PawnLoanEconomicPolicy.objects.filter(
            workspace=request.loans_workspace
        )
        .select_related("license", "series")
        .prefetch_related("series__number_sequences"),
        "rate_policies": PawnMetalInterestRatePolicy.objects.filter(
            workspace=request.loans_workspace
        )
        .select_related("license", "series")
        .prefetch_related("series__number_sequences"),
        "fee_policies": PawnLoanFeePolicy.objects.filter(
            workspace=request.loans_workspace
        ).select_related("license"),
        "monitoring_policies": LoanMonitoringPolicy.objects.filter(
            workspace=request.loans_workspace
        ).select_related("license", "successor", "created_by"),
    }
    return render(request, "loans/setup/economics.html", context)
