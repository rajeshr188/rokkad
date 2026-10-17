"""Ordinary typed review of original agreement and verified opening facts."""

from copy import deepcopy
from decimal import Decimal
from uuid import uuid4

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from apps.tenant_apps.loans.domain.monthly_contract import item_monthly_interest
from apps.tenant_apps.loans.services.agreement_corrections import (
    preview_agreement_correction,
    record_agreement_correction,
)
from apps.tenant_apps.loans.services.opening_evidence import read_opening_evidence
from apps.tenant_apps.loans.services.opening_corrections import SUPPORTED_PROFILES


class CheckpointCorrectionForm(forms.Form):
    reference = forms.CharField(
        max_length=160, label="Supporting agreement and checked cutover book reference"
    )
    reason = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Why these recorded facts need correction",
    )
    request_key = forms.CharField(max_length=80, widget=forms.HiddenInput)
    review_token = forms.CharField(required=False, widget=forms.HiddenInput)
    confirmed = forms.BooleanField(
        required=False,
        label="I checked original terms, cutover balances, period bases, advance coverage and remaining obligations. Earlier payments remain unavailable; this records no new cash.",
    )

    def __init__(self, *args, opening, **kwargs):
        super().__init__(*args, **kwargs)
        self.opening = opening
        review = opening["review"]
        carry = review["continuation"]
        aggregate = review["profile"] == "loan-opening-review/2"
        bases = {r["item_id"]: r["principal_base"] for r in carry.get("bases", [])}
        for row in review["collateral"]:
            pk = opening["item_mapping"][row["id"]]
            for name, source, label in (
                ("original", "original_principal", "Original principal"),
                (
                    "remaining",
                    "remaining_principal",
                    "Principal outstanding at cutover",
                ),
                ("rate", "monthly_rate", "Original monthly interest (%)"),
                ("base", None, "Principal used for the cutover period's interest"),
            ):
                if aggregate and name == "base":
                    continue
                key = f"item_{pk}_{name}"
                self.fields[key] = forms.DecimalField(
                    max_digits=14,
                    decimal_places=6 if name == "rate" else 2,
                    min_value=Decimal("0"),
                    label=f"{row['description']}: {label}",
                )
                self.initial[key] = bases[row["id"]] if name == "base" else row[source]
        for name, label in (
            ("recognized_interest", "Cumulative interest recognized through cutover"),
            ("recognized_unpaid_interest", "Interest outstanding at cutover"),
            (
                "current_period_recognized_interest",
                "Interest recognized for the cutover period",
            ),
            (
                "current_period_unpaid_interest",
                "Interest still unpaid for the cutover period",
            ),
        ):
            if aggregate and name.startswith("current_period_"):
                continue
            self.fields[name] = forms.DecimalField(
                max_digits=14, decimal_places=2, min_value=Decimal("0"), label=label
            )
            self.initial[name] = carry[name]
        self.fields["fees"] = forms.DecimalField(
            max_digits=14,
            decimal_places=2,
            min_value=Decimal("0"),
            label="Fees outstanding at cutover",
        )
        self.initial["fees"] = review["balances"]["fees"]
        periods = (
            set()
            if aggregate
            else {
                carry["period_number"],
                *(r["period_number"] for r in carry["advance_coverage"]),
            }
        )
        for number in sorted(periods):
            key = f"advance_{number}"
            self.fields[key] = forms.DecimalField(
                max_digits=14,
                decimal_places=2,
                min_value=Decimal("0"),
                label=f"Verified advance interest covering period {number}",
            )
            self.initial[key] = next(
                (
                    r["interest"]
                    for r in carry["advance_coverage"]
                    if r["period_number"] == number
                ),
                "0",
            )
        for index, row in enumerate(review["obligations"]):
            for name, label in (
                ("principal", "Principal remaining due"),
                ("interest", "Interest remaining due"),
                ("recognized_interest", "Recognized interest remaining due"),
            ):
                key = f"obligation_{index}_{name}"
                self.fields[key] = forms.DecimalField(
                    max_digits=14,
                    decimal_places=2,
                    min_value=Decimal("0"),
                    label=f"Due {row['due']}: {label}",
                )
                self.initial[key] = row[name]
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-check-input"
                if isinstance(field.widget, forms.CheckboxInput)
                else "form-control"
            )
        self.order_fields(
            [key for key in self.fields if key != "confirmed"] + ["confirmed"]
        )

    def facts(self):
        values = self.cleaned_data
        review = deepcopy(self.opening["review"])
        carry = review["continuation"]
        aggregate = review["profile"] == "loan-opening-review/2"
        for row in review["collateral"]:
            pk = self.opening["item_mapping"][row["id"]]
            for name, field in (
                ("original_principal", "original"),
                ("remaining_principal", "remaining"),
                ("monthly_rate", "rate"),
            ):
                row[name] = str(values[f"item_{pk}_{field}"])
            if not aggregate:
                next(r for r in carry["bases"] if r["item_id"] == row["id"])[
                    "principal_base"
                ] = str(values[f"item_{pk}_base"])
        for name in (
            "recognized_interest",
            "recognized_unpaid_interest",
            "current_period_recognized_interest",
            "current_period_unpaid_interest",
        ):
            if name in values:
                carry[name] = str(values[name])
        if not aggregate:
            carry["expected_period_interest"] = str(
                sum(
                    item_monthly_interest(
                        next(
                            r["principal_base"]
                            for r in carry["bases"]
                            if r["item_id"] == row["id"]
                        ),
                        row["monthly_rate"],
                        review["terms"]["interest_quantum"],
                    )
                    for row in review["collateral"]
                )
            )
            carry["advance_coverage"] = [
                dict(
                    period_number=int(key.removeprefix("advance_")),
                    interest=str(amount),
                    evidence_reference=values["reference"],
                )
                for key, amount in values.items()
                if key.startswith("advance_") and amount
            ]
        carry["evidence_reference"] = values["reference"]
        review["balances"].update(
            principal=str(
                sum(Decimal(r["remaining_principal"]) for r in review["collateral"])
            ),
            interest=str(values["recognized_unpaid_interest"]),
            fees=str(values["fees"]),
            evidence_reference=values["reference"],
        )
        for index, row in enumerate(review["obligations"]):
            for name in ("principal", "interest", "recognized_interest"):
                row[name] = str(values[f"obligation_{index}_{name}"])
        return dict(
            checkpoint=review,
            **{key: values[key] for key in ("reference", "reason", "request_key")},
        )


def opening_agreement_correction(request, loan):
    if loan.is_imported_closed_position:
        return render(
            request,
            "loans/pawn/checkpoint_correction.html",
            dict(
                loan=loan,
                form=None,
                blockers=[
                    "This verified closed position has no complete original agreement. Reconcile its source position before correcting financial facts."
                ],
            ),
        )
    origin = loan.loan_events.get(event_kind="MIGRATION_OPENING")
    opening = read_opening_evidence(loan, origin)
    blockers = []
    if opening["review"]["profile"] not in SUPPORTED_PROFILES:
        blockers.append(
            "This older opening needs a supported checkpoint review before correcting its financial terms."
        )
    if (
        loan.state != "ACTIVE"
        or loan.loan_events.exclude(
            event_kind__in=("MIGRATION_OPENING", "OPENING_CORRECTION")
        ).exists()
    ):
        blockers.append(
            "This checkpoint has later financial activity or settlement; review that connected history before changing its baseline."
        )
    form = (
        None
        if blockers
        else CheckpointCorrectionForm(
            request.POST if request.method == "POST" else None,
            opening=opening,
            initial=dict(request_key=uuid4().hex),
        )
    )
    review = None
    if request.method == "POST" and form and form.is_valid():
        try:
            data = form.facts()
            if request.POST.get("action") == "confirm":
                _, created = record_agreement_correction(
                    loan.pk,
                    actor=request.user,
                    data=data,
                    review_token=form.cleaned_data["review_token"],
                    confirmed=form.cleaned_data["confirmed"],
                )
                messages.success(
                    request,
                    (
                        "Checkpoint correction recorded."
                        if created
                        else "This checkpoint correction was already recorded."
                    ),
                )
                return redirect(
                    "workspace_loans:pawn_loan_detail",
                    workspace_slug=request.workspace.slug,
                    pk=loan.pk,
                )
            review, token = preview_agreement_correction(
                loan.pk, actor=request.user, data=data
            )
            form.data = form.data.copy()
            form.data["review_token"] = token
        except (ValueError, ValidationError) as exc:
            form.add_error(None, str(exc))
    return render(
        request,
        "loans/pawn/checkpoint_correction.html",
        dict(
            loan=loan,
            form=form,
            review=review,
            blockers=blockers,
            checkpoint=opening["review"],
        ),
    )
