"""Workflow helpers for loan create/update view orchestration."""

from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.girvi.models import GivenLoan
from apps.tenant_apps.girvi.models.license import Series
from apps.tenant_apps.girvi.services import (
    LoanCreateCommand,
    LoanCreationService,
    LoanItemCreateInput,
)
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.party.services.customer_bridge import ensure_party_customer


class LoanWorkflowService:
    """Keep loan views focused on HTTP flow while centralizing orchestration."""

    @staticmethod
    def extract_initial_item_inputs(item_formset):
        initial_items = []
        for item_data in getattr(item_formset, "cleaned_data", []) if item_formset else []:
            if not item_data or item_data.get("DELETE"):
                continue
            if not any(
                item_data.get(field) not in (None, "")
                for field in ("item", "itemdesc", "weight", "loanamount")
            ):
                continue
            initial_items.append(
                LoanItemCreateInput(
                    item=item_data.get("item"),
                    itemdesc=item_data.get("itemdesc") or "",
                    itemtype=item_data.get("itemtype") or "Gold",
                    quantity=item_data.get("quantity") or 1,
                    weight=item_data.get("weight"),
                    purity=item_data.get("purity"),
                    loanamount=item_data.get("loanamount"),
                    interestrate=item_data.get("interestrate"),
                )
            )
        return initial_items

    @classmethod
    def build_loan_create_command(cls, form, user, item_formset=None):
        borrower_party = form.cleaned_data["borrower_party"]
        bridge = ensure_party_customer(borrower_party, created_by=user)
        return LoanCreateCommand(
            borrower=bridge["customer"],
            borrower_party=borrower_party,
            series=form.cleaned_data["series"],
            loan_date=form.cleaned_data["loan_date"],
            tenure=form.cleaned_data["tenure"],
            interest_type=form.cleaned_data["interest_type"],
            created_by=user,
            loan_id=form.cleaned_data.get("loan_id") or "",
            initial_items=cls.extract_initial_item_inputs(item_formset),
        )

    @staticmethod
    def parse_preview_loan_date(raw_value):
        if not raw_value:
            return timezone.now()
        if isinstance(raw_value, datetime):
            return raw_value

        for fmt in ("%Y-%m-%dT%H:%M", "%d-%m-%Y %H:%M"):
            try:
                return datetime.strptime(str(raw_value), fmt)
            except (TypeError, ValueError):
                continue

        return raw_value

    @staticmethod
    def build_preview_initial_item_inputs(data):
        initial_items = []

        try:
            total_forms = int(data.get("items-TOTAL_FORMS") or 0)
        except (TypeError, ValueError):
            total_forms = 0

        for index in range(total_forms):
            item_data = {
                "itemdesc": data.get(f"items-{index}-itemdesc") or "",
                "itemtype": data.get(f"items-{index}-itemtype") or "Gold",
                "quantity": data.get(f"items-{index}-quantity") or 1,
                "weight": data.get(f"items-{index}-weight"),
                "purity": data.get(f"items-{index}-purity"),
                "loanamount": data.get(f"items-{index}-loanamount"),
                "interestrate": data.get(f"items-{index}-interestrate"),
            }
            if any(
                item_data.get(field) not in (None, "")
                for field in ("itemdesc", "weight", "loanamount")
            ):
                initial_items.append(LoanItemCreateInput(**item_data))

        return initial_items

    @classmethod
    def build_create_preview_from_data(cls, data, user):
        borrower = None
        borrower_party = None
        series = None

        borrower_party_id = data.get("borrower_party") or data.get("borrower")
        if borrower_party_id:
            try:
                borrower_party = Party.objects.filter(pk=int(borrower_party_id)).first()
                try:
                    borrower = borrower_party.legacy_customer if borrower_party else None
                except Customer.DoesNotExist:
                    borrower = borrower_party
            except (TypeError, ValueError):
                borrower = None
                borrower_party = None

        series_id = data.get("series")
        if series_id:
            try:
                series = Series.objects.filter(pk=int(series_id)).first()
            except (TypeError, ValueError):
                series = None

        try:
            tenure = int(data.get("tenure") or 3)
        except (TypeError, ValueError):
            tenure = 3

        interest_type = data.get("interest_type") or GivenLoan._meta.get_field(
            "interest_type"
        ).default

        return LoanCreationService.preview(
            LoanCreateCommand(
                borrower=borrower,
                borrower_party=borrower_party,
                series=series,
                loan_date=cls.parse_preview_loan_date(data.get("loan_date")),
                tenure=tenure,
                interest_type=interest_type,
                created_by=user,
                loan_id="",
                initial_items=cls.build_preview_initial_item_inputs(data),
            )
        )

    @staticmethod
    def persist_loan_update(form, *, user):
        if not form.is_valid():
            raise ValidationError("Form must be valid before persisting loan update.")

        with transaction.atomic():
            loan = form.save(commit=False)
            if not loan.created_by:
                loan.created_by = user
            loan.save()

        return loan
