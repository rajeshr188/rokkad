from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.tenant_apps.rates.models import Rate
from .models import (
    CollateralAppraisal, LoanMonitoringPolicy, LoanRiskSnapshot,
    ObligationAllocation, PawnCollateralItem, PawnLoan,
    PawnLoanAccountingEvent, RepaymentObligation,
    RepaymentScheduleChange, RepaymentScheduleVersion,
)


LOAN_SOURCES = (
    PawnLoan, PawnLoanAccountingEvent, RepaymentScheduleVersion,
    RepaymentObligation, ObligationAllocation, RepaymentScheduleChange,
    PawnCollateralItem, CollateralAppraisal,
)


def _loan_id(instance):
    if isinstance(instance, PawnLoan): return instance.pk
    if isinstance(instance, CollateralAppraisal): return instance.collateral_item.loan_id
    return instance.loan_id


def _mark_loan(sender, instance, **kwargs):
    loan_id = _loan_id(instance)
    transaction.on_commit(lambda: LoanRiskSnapshot.objects.filter(loan_id=loan_id).update(status=LoanRiskSnapshot.Status.STALE, error_message="Source evidence changed; reassessment required."))


for source in LOAN_SOURCES:
    post_save.connect(_mark_loan, sender=source, weak=False, dispatch_uid=f"loans-risk-stale-{source.__name__}")


@receiver(post_save, sender=LoanMonitoringPolicy, dispatch_uid="loans-risk-stale-monitoring-policy")
def _mark_policy_scope(sender, instance, **kwargs):
    def update():
        queryset = LoanRiskSnapshot.objects.filter(workspace_id=instance.workspace_id)
        if instance.license_id: queryset = queryset.filter(loan__license_id=instance.license_id)
        queryset.update(status=LoanRiskSnapshot.Status.STALE, error_message="Monitoring policy changed; reassessment required.")
    transaction.on_commit(update)


@receiver(post_save, sender=Rate, dispatch_uid="loans-risk-stale-rate")
def _mark_rate_change(sender, instance, **kwargs):
    transaction.on_commit(lambda: LoanRiskSnapshot.objects.update(status=LoanRiskSnapshot.Status.STALE, error_message="Valuation rate changed; reassessment required."))
