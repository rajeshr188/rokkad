from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import (
    ExternalAccount,
    ExternalAccountClassification,
    Ledger,
    LedgerSide,
    ReportingClass,
)


@transaction.atomic
def append_external_account_classification(
    *,
    external_account: ExternalAccount,
    version_key: str,
    effective_from,
    reporting_ledger: Ledger,
    reporting_class: str,
    normal_side: str,
) -> ExternalAccountClassification:
    """Close the current open version and append its immutable successor."""

    if not isinstance(external_account, ExternalAccount):
        raise ValidationError("external_account must be an ExternalAccount")
    if not isinstance(reporting_ledger, Ledger):
        raise ValidationError("reporting_ledger must be a Ledger")
    if not isinstance(effective_from, date):
        raise ValidationError("effective_from must be a date")
    if reporting_class not in ReportingClass.values:
        raise ValidationError("reporting_class is invalid")
    if normal_side not in LedgerSide.values:
        raise ValidationError("normal_side is invalid")

    versions = list(
        ExternalAccountClassification.objects.select_for_update()
        .filter(external_account=external_account)
        .order_by("effective_from", "created_at")
    )
    if versions:
        current = versions[-1]
        if current.effective_to is not None:
            if effective_from <= current.effective_to:
                raise ValidationError(
                    "New classification must start after the latest version ends."
                )
        else:
            if effective_from <= current.effective_from:
                raise ValidationError(
                    "New classification must start after the current version."
                )
            ExternalAccountClassification.objects.filter(pk=current.pk).update(
                effective_to=effective_from - timedelta(days=1)
            )

    return ExternalAccountClassification.objects.create(
        external_account=external_account,
        version_key=version_key,
        effective_from=effective_from,
        reporting_ledger=reporting_ledger,
        reporting_class=reporting_class,
        normal_side=normal_side,
    )
