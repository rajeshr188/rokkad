from django.db.models import Exists, OuterRef
from apps.tenant_apps.party.widgets import PartyAutocompleteWidget
from .models import PawnLoan


class LoanBorrowerAutocompleteWidget(PartyAutocompleteWidget):
    """Find existing borrowers, including inactive/archived identities."""
    active_only = False
    max_results = 20

    def get_queryset(self):
        return super().get_queryset().filter(Exists(PawnLoan.objects.filter(
            borrower_id=OuterRef("pk"), workspace_id=OuterRef("workspace_id"))))
