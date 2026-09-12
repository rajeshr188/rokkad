from django.db.models import Q
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.tenant_apps.rates.models import Rate
from .models import (
    CollateralAppraisal, LoanMonitoringPolicy, LoanRiskSnapshot,
    ObligationAllocation, PawnCollateralItem, PawnLoan,
    PawnLoanEvent, RepaymentObligation,
    RepaymentScheduleChange, RepaymentScheduleVersion,
)


LOAN_SOURCES = (
    PawnLoan, PawnLoanEvent, RepaymentScheduleVersion,
    RepaymentObligation, ObligationAllocation, RepaymentScheduleChange,
    PawnCollateralItem, CollateralAppraisal,
)


def _loan_id(instance):
    if isinstance(instance, PawnLoan): return instance.pk
    if isinstance(instance, CollateralAppraisal): return instance.collateral_item.loan_id
    return instance.loan_id


def _mark_loan(sender, instance, **kwargs):
    loan_id = _loan_id(instance)
    # Invalidate inside the source transaction while its RLS context is active.
    LoanRiskSnapshot.objects.filter(workspace_id=instance.workspace_id, loan_id=loan_id, loan__state="ACTIVE").exclude(status=LoanRiskSnapshot.Status.ERROR).update(
        status=LoanRiskSnapshot.Status.STALE, error_message="Source evidence changed; reassessment required.")


for source in LOAN_SOURCES:
    post_save.connect(_mark_loan, sender=source, weak=False, dispatch_uid=f"loans-risk-stale-{source.__name__}")


@receiver(post_save, sender=LoanMonitoringPolicy, dispatch_uid="loans-risk-stale-monitoring-policy")
def _mark_policy_scope(sender, instance, **kwargs):
    def update():
        queryset = LoanRiskSnapshot.objects.filter(workspace_id=instance.workspace_id, loan__state="ACTIVE")
        if instance.license_id: queryset = queryset.filter(loan__license_id=instance.license_id)
        queryset = queryset.filter(as_of_date__gte=instance.effective_from)
        if instance.effective_until:
            queryset = queryset.filter(as_of_date__lte=instance.effective_until)
        queryset.exclude(status=LoanRiskSnapshot.Status.ERROR).update(status=LoanRiskSnapshot.Status.STALE, error_message="Monitoring policy changed; reassessment required.")
    update()


@receiver(post_save, sender=Rate, dispatch_uid="loans-risk-stale-rate")
def _mark_rate_change(sender, instance, **kwargs):
    signatures = {
        signature
        for signature in (
            _rate_signature(instance.supersedes) if instance.supersedes_id else None,
            _rate_signature(instance),
        )
        if signature is not None
    }

    def update():
        scope = Q()
        for metal, effective_date in signatures:
            scope |= Q(
                loan__collateral_items__metal=metal,
                as_of_date__gte=effective_date,
            )
        if scope:
            LoanRiskSnapshot.objects.filter(scope, workspace_id=instance.workspace_id, loan__state="ACTIVE").exclude(status=LoanRiskSnapshot.Status.ERROR).update(
                status=LoanRiskSnapshot.Status.STALE,
                error_message="Applicable valuation rate changed; reassessment required.",
            )

    update()


def _rate_signature(rate):
    if rate is None or rate.currency != Rate.Currency.INR or rate.purity != Rate.Purity.K24:
        return None
    metal = {
        Rate.Metal.GOLD: "GOLD",
        Rate.Metal.SILVER: "SILVER",
    }.get(rate.metal)
    if metal is None or rate.effective_at is None:
        return None
    return metal, timezone.localtime(rate.effective_at).date()
