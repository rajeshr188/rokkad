"""Safe setup of the DEA borrower receivable mapping required by PawnLoan."""

from dataclasses import dataclass

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django_tenants.utils import get_public_schema_name, schema_context

from apps.orgs.audit import AuditLog
from apps.tenant_apps.dea import facade as dea_facade
from apps.tenant_apps.loans.models import PawnLoan, current_tenant_workspace_id
from apps.tenant_apps.party.models import Party


class PawnBorrowerAccountingSetupError(ValueError):
    """Raised when the borrower receivable mapping cannot be prepared safely."""


@dataclass(frozen=True)
class PawnBorrowerAccountingSetupResult:
    loan: PawnLoan
    party: Party
    account: object
    mapping: object
    mapping_created: bool


@transaction.atomic
def ensure_pawn_borrower_accounting(loan_id: int, *, actor=None, request=None):
    """Create or reuse the compatibility account and explicit DEA mapping.

    This is setup only. It never posts a voucher or journal entry.
    """
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnBorrowerAccountingSetupError(
            "Borrower accounting setup requires an active tenant schema."
        )
    try:
        loan = (
            PawnLoan.objects.select_for_update()
            .select_related("workspace", "borrower")
            .get(pk=loan_id, workspace_id=workspace_id)
        )
        party = Party.objects.select_for_update().get(pk=loan.borrower_id)
    except (PawnLoan.DoesNotExist, Party.DoesNotExist) as exc:
        raise PawnBorrowerAccountingSetupError(
            "PawnLoan borrower was not found in the active workspace."
        ) from exc

    if party.status != Party.PartyStatus.ACTIVE:
        raise PawnBorrowerAccountingSetupError(
            "The borrower Party must be active before accounting can be configured."
        )

    try:
        resolved = dea_facade.resolve_party_account(
            party,
            role_key="BORROWER",
            purpose="BORROWER_LOAN_RECEIVABLE",
            create=False,
        )
        if resolved is None:
            resolved = dea_facade.resolve_party_account(
                party,
                role_key="BORROWER",
                purpose="BORROWER_LOAN_RECEIVABLE",
                create=True,
            )
    except (ObjectDoesNotExist, ValidationError) as exc:
        raise PawnBorrowerAccountingSetupError(str(exc)) from exc

    if resolved is None or resolved.mapping is None:
        raise PawnBorrowerAccountingSetupError(
            "DEA did not return an active borrower loan-receivable mapping."
        )

    result = PawnBorrowerAccountingSetupResult(
        loan=loan,
        party=party,
        account=resolved.account,
        mapping=resolved.mapping,
        mapping_created=resolved.created,
    )
    if resolved.created:
        _audit_setup(result, actor=actor, request=request)
    return result


def _audit_setup(result, *, actor, request):
    with schema_context(get_public_schema_name()):
        AuditLog.log(
            "SETTINGS_UPDATE",
            user=actor,
            company=result.loan.workspace,
            description=(
                f"Configured borrower accounting for PawnLoan "
                f"{result.loan.loan_number}."
            ),
            data={
                "entity": "pawn_loan_borrower_accounting",
                "loan_id": result.loan.pk,
                "party_id": result.party.pk,
                "account_id": result.account.pk,
                "mapping_id": result.mapping.pk,
                "mapping_created": result.mapping_created,
            },
            request=request,
            success=True,
        )


__all__ = [
    "PawnBorrowerAccountingSetupError",
    "PawnBorrowerAccountingSetupResult",
    "ensure_pawn_borrower_accounting",
]
