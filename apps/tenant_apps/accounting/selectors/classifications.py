from datetime import date

from django.core.exceptions import ValidationError
from django.db.models import Q

from ..models import ExternalAccount, ExternalAccountClassification


def resolve_external_account_classification(
    *,
    external_account: ExternalAccount,
    effective_date: date,
) -> ExternalAccountClassification:
    """Return the one immutable classification effective on the given date."""

    if not isinstance(external_account, ExternalAccount):
        raise ValidationError("external_account must be an ExternalAccount")
    if not isinstance(effective_date, date):
        raise ValidationError("effective_date must be a date")
    matches = list(
        ExternalAccountClassification.objects.filter(
            external_account=external_account,
            effective_from__lte=effective_date,
        )
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=effective_date))
        .select_related("reporting_ledger")[:2]
    )
    if not matches:
        raise ValidationError(
            "No external-account classification is effective on the posting date."
        )
    if len(matches) != 1:
        raise ValidationError(
            "More than one external-account classification is effective on the posting date."
        )
    return matches[0]
