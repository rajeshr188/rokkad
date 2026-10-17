"""Reuse an unpaid draft's identity for reviewed completed-payout admission."""

from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from .action_access import require_loan_action
from apps.tenant_apps.loans import models as m


def completed_payout_adapter(loan):
    """Presentation choice only; each command rechecks its own locked evidence."""
    if loan.state not in ("DRAFT", "APPROVED"):
        return None
    events = loan.loan_events
    snapshots = loan.disbursal_snapshots
    if not events.exists() and not snapshots.exists():
        return "RECORDED"
    if (
        loan.state == "DRAFT"
        and loan.loan_date < timezone.localdate()
        and snapshots.exists()
        and not snapshots.exclude(basis="APPROVED").exists()
        and events.filter(event_kind="DISBURSAL").exists()
        and not events.exclude(event_kind__in=("DISBURSAL", "REVERSAL")).exists()
        and not events.filter(
            event_kind="DISBURSAL", reversed_by_event__isnull=True
        ).exists()
    ):
        return "RETAINED_NATIVE"
    return None


def completed_payout_profile_blockers(loan):
    """Early factual disclosure reused by the concrete completed-fact command."""
    blockers = []
    product = loan.product_version
    if (
        product is None
        or product.repayment_structure
        not in ("SINGLE_PAYMENT_BULLET", "FLEXIBLE_PARTIAL_PAYMENT")
        or product.amortisation_method != "NONE"
    ):
        blockers.append(
            "Completed payout recording needs a supported non-amortising monthly bullet/flexible agreement."
        )
    approval = loan.approval_snapshots.order_by("-version").first()
    if approval:
        frozen = approval.payload.get("collateral_economics", {})
        if (
            frozen.get("interest_method") != "SIMPLE"
            or frozen.get("partial_month_method") != "FULL_MONTH"
            or frozen.get("rounding_method") != "PER_ACCRUAL_PERIOD"
        ):
            blockers.append(
                "The retained agreement requires its supported calculation review; monthly terms cannot be substituted."
            )
        fees = frozen.get("fees", [])
        if any(
            not row.get("deducted_at_disbursal")
            or row.get("code") not in {"DOCUMENT_CHARGE", "DOC", "DOCUMENT", "DOC_FEE"}
            for row in fees
        ):
            blockers.append(
                "Retained fee components need their supported agreement review; they cannot be relabelled as a document charge."
            )
    return tuple(blockers)


def draft_source(workspace, actor, draft_id):
    loan = (
        m.PawnLoan.objects.select_for_update(of=("self",))
        .select_related("license", "series", "borrower", "product_version")
        .get(pk=draft_id, workspace=workspace)
    )
    require_loan_action(loan, actor, "data.edit", "loan.disburse")
    return loan


def require_unpaid_draft(loan):
    if (
        loan.state not in ("DRAFT", "APPROVED")
        or loan.loan_events.exists()
        or loan.disbursal_snapshots.exists()
    ):
        raise ValueError(
            "Completed payout admission requires an unpaid draft with no financial origin. Use the existing loan's correction workflow for posted history."
        )
    if loan.collateral_items.exclude(custody_state="IN_VAULT").exists():
        raise ValueError(
            "Review the draft's collateral custody before completed payout admission."
        )
    if loan.collateral_items.filter(renewed_from__isnull=False).exists():
        raise ValueError("A linked renewal draft requires its renewal workflow.")


def source_evidence(loan):
    """Bind review to saved draft facts, genuine approvals and issued copies."""
    from .recorded_history import _digest

    fields = (
        "id",
        "borrower_id",
        "license_id",
        "license_revision_id",
        "series_id",
        "product_version_id",
        "loan_number",
        "loan_date",
        "principal_amount",
        "monthly_interest_rate",
        "tenure_months",
        "state",
        "creation_submission_id",
        "policy_snapshot_id",
        "updated_at",
    )
    items = list(loan.collateral_items.select_for_update().order_by("pk"))
    material = dict(
        loan={name: str(getattr(loan, name)) for name in fields},
        items=[
            {
                field.name: str(getattr(item, field.attname))
                for field in item._meta.concrete_fields
            }
            for item in items
        ],
        approvals=list(
            loan.approval_snapshots.order_by("pk").values("id", "fingerprint")
        ),
        photos=list(
            m.PawnCollateralPhoto.objects.filter(collateral_item__loan=loan)
            .order_by("pk")
            .values_list("pk", "sha256")
        ),
        documents=list(
            m.LoanDocumentIssue.objects.filter(
                workspace_id=loan.workspace_id,
                source_type="PawnLoan",
                source_id=str(loan.pk),
            )
            .order_by("pk")
            .values_list("pk", "source_fingerprint")
        ),
    )
    quotes = retained_approval_evidence(loan)
    if quotes:
        material["approval_evidence"] = quotes
    return dict(
        loan_id=loan.pk,
        original_state=loan.state,
        source_sha256=_digest(material),
        item_ids=[item.pk for item in items],
        retained_approvals=material["approvals"],
        **({"approval_evidence": quotes} if quotes else {}),
    )


def retained_approval_evidence(loan):
    """Describe original quote evidence without reapproving or replacing it."""
    from apps.tenant_apps.rates.models import Rate
    from apps.tenant_apps.loans.selectors.origination_rates import quote_evidence

    approvals = list(loan.approval_snapshots.order_by("version"))
    quoted = [
        (approval, approval.payload.get("origination_rates", {}).get("quotes", {}))
        for approval in approvals
    ]
    ids = {
        value.get("rate_id")
        for _, quotes in quoted
        for value in quotes.values()
        if isinstance(value, dict)
    }
    rates = {
        row.pk: row
        for row in Rate.objects.filter(
            workspace_id=loan.workspace_id, pk__in=[pk for pk in ids if type(pk) is int]
        ).annotate(successor_id=F("successor__pk"))
    }
    result = []
    for approval, quotes in quoted:
        observations = []
        for metal, expected in sorted(quotes.items()):
            rate = (
                rates.get(expected.get("rate_id"))
                if isinstance(expected, dict)
                else None
            )
            status = (
                "MISSING"
                if rate is None
                else (
                    "WITHDRAWN"
                    if rate.is_withdrawal
                    else (
                        "CORRECTED_OR_WITHDRAWN"
                        if rate.successor_id
                        else (
                            "RETAINED"
                            if quote_evidence(rate) == expected
                            else "DIFFERS_FROM_SAVED"
                        )
                    )
                )
            )
            observations.append(
                dict(
                    metal=metal,
                    rate_id=(
                        expected.get("rate_id") if isinstance(expected, dict) else None
                    ),
                    status=status,
                    successor_id=rate.successor_id if rate else None,
                )
            )
        result.append(
            dict(approval_id=approval.pk, version=approval.version, quotes=observations)
        )
    return result


def completed_payout_defaults(loan):
    """Standing defaults are suggestions; retained agreement facts take precedence."""
    from .paper_entry_terms import paper_entry_terms

    items = list(loan.collateral_items.order_by("pk"))
    if not items:
        raise ValueError(
            "Add the actual collateral to this draft before recording its payout."
        )
    values = paper_entry_terms(
        workspace=loan.workspace,
        series=loan.series,
        day=loan.loan_date,
        metal=items[0].metal,
        principal=loan.principal_amount,
    )["values"]
    approval = loan.approval_snapshots.order_by("-version").first()
    frozen = approval.payload.get("collateral_economics", {}) if approval else {}
    if frozen:
        values.update(
            advance_months=frozen.get("advance_interest_periods"),
            document_charge=frozen.get("deducted_fees"),
            cash_paid=frozen.get("net_disbursed"),
            currency_quantum=str(Decimal(frozen["currency_quantum"]).normalize()),
            monitoring_method=frozen.get("valuation_method"),
            monitoring_ltv=frozen.get("maximum_ltv_ratio"),
            monitoring_reason="Retained agreement basis; current monitoring remains independently assessed.",
        )
    elif loan.policy_snapshot_id:
        values["currency_quantum"] = str(
            loan.policy_snapshot.currency_quantum.normalize()
        )
    return dict(values, source_reference=loan.loan_number)


def _completed_input(workspace, actor, loan_id, values):
    """Build facts under the same Workspace/loan locks as admission."""
    from apps.orgs.models import Company
    from .action_access import require_workspace_action
    from .recorded_history import validate_input, _text
    from .recorded_items import monthly_interest
    from .origination_summary import recorded_origination_summary

    if m.current_tenant_workspace_id() != workspace.pk:
        raise PermissionDenied(
            "Completed payout requires the matching active Workspace."
        )
    require_workspace_action(
        workspace, actor, "data.create", "data.edit", "loan.disburse"
    )
    Company.all_objects.select_for_update().get(pk=workspace.pk)
    loan = draft_source(workspace, actor, loan_id)
    blockers = completed_payout_profile_blockers(loan)
    if blockers:
        raise ValueError(" ".join(blockers))
    if type(values.get("advance_months")) is not int or values[
        "advance_months"
    ] not in (0, 1):
        raise ValueError("Record zero or one agreed advance month.")
    items = list(loan.collateral_items.select_for_update().order_by("pk"))
    if not items:
        raise ValueError(
            "Add the actual collateral to this draft before recording its payout."
        )
    evidence = retained_approval_evidence(loan)
    if evidence and values.get("reviewed_evidence") is not True:
        raise ValueError(
            "Review and acknowledge the retained approval evidence before recording the completed facts."
        )
    facts = [
        dict(
            description=row.description,
            metal=row.metal,
            quantity=row.quantity,
            gross_weight=str(row.gross_weight),
            net_weight=str(row.net_weight),
            purity=str(row.purity_percentage),
            principal=str(row.allocated_principal),
            rate=str(
                row.monthly_interest_rate
                if row.monthly_interest_rate is not None
                else loan.monthly_interest_rate
            ),
        )
        for row in items
    ]
    data = dict(
        borrower_id=loan.borrower_id,
        series_id=loan.series_id,
        product_version_id=loan.product_version_id,
        number=loan.loan_number,
        date=loan.loan_date.isoformat(),
        principal=str(loan.principal_amount),
        rate=str(loan.monthly_interest_rate),
        tenure=loan.tenure_months,
        collateral=facts,
        description=facts[0]["description"],
        metal=facts[0]["metal"],
        quantity=facts[0]["quantity"],
        gross_weight=facts[0]["gross_weight"],
        net_weight=facts[0]["net_weight"],
        purity=facts[0]["purity"],
        source_reference=values["source_reference"],
        advance_months=values["advance_months"],
        currency_quantum=values["currency_quantum"],
        document_charge=str(values["document_charge"]),
        monitoring_method=values["monitoring_method"],
        monitoring_ltv=str(values["monitoring_ltv"]),
        monitoring_reason=values["monitoring_reason"],
        payout_basis="CASH",
        events=[],
        complete_through=loan.loan_date.isoformat(),
        final_state="ACTIVE",
        confirmed_history=False,
        confirmed_rule=values.get("confirmed_rule") is True,
        recording_mode="TRANSACTION_ENTRY",
        entry_note="Completed payout: "
        + _text(
            values.get("reason"), "why this completed payout is being recorded now", 235
        ),
    )
    if loan.license_revision_id is not None:
        data["license_revision_id"] = loan.license_revision_id
    try:
        quantum = Decimal(data["currency_quantum"])
        if quantum not in (Decimal("0.01"), Decimal("1")):
            raise ValueError("Select paise or whole-rupee agreement rounding.")
        monthly = monthly_interest(facts, quantum)
    except (ArithmeticError, TypeError) as exc:
        raise ValueError(
            "Complete the saved item principals and monthly rates before reviewing the payout."
        ) from exc
    data["cash_paid"] = str(
        values["cash_paid"]
        if values.get("cash_paid") is not None
        else loan.principal_amount
        - monthly * data["advance_months"]
        - Decimal(data["document_charge"])
    )
    data = validate_input(data)
    approval = loan.approval_snapshots.order_by("-version").first()
    if approval:
        _check_retained_agreement(loan, approval, data, monthly)
    agreement = recorded_origination_summary(
        data, customer=loan.borrower, series=loan.series
    )
    return loan, data, agreement


def _check_retained_agreement(loan, approval, data, monthly):
    """A changed quote is reviewable; different agreed economics need correction."""
    from .recorded_items import contract_items
    from .borrower_corrections import corrected_ticket_source

    payload, _ = corrected_ticket_source(loan, approval.payload)
    frozen = payload.get("collateral_economics", {})
    message = "Actual terms differ from retained approval evidence. Reconcile the draft explicitly before admission."
    try:
        if (
            frozen["interest_method"] != "SIMPLE"
            or frozen["partial_month_method"] != "FULL_MONTH"
            or frozen["rounding_method"] != "PER_ACCRUAL_PERIOD"
        ):
            raise ValueError(
                "This retained agreement requires its supported calculation review; do not substitute monthly terms."
            )
        if any(
            Decimal(str(payload[name])) != Decimal(str(getattr(loan, name)))
            for name in ("principal_amount", "monthly_interest_rate", "tenure_months")
        ):
            raise ValueError(message)
        if any(
            payload.get(name) != value
            for name, value in (
                ("borrower_id", loan.borrower_id),
                ("series_id", loan.series_id),
                ("loan_number", loan.loan_number),
                ("loan_date", loan.loan_date.isoformat()),
            )
        ):
            raise ValueError(message)
        expected = (
            Decimal(frozen["monthly_interest"]),
            frozen["advance_interest_periods"],
            Decimal(frozen["deducted_fees"]),
            Decimal(frozen["net_disbursed"]),
            Decimal(frozen["currency_quantum"]),
        )
        actual = (
            monthly,
            data["advance_months"],
            Decimal(data["document_charge"]),
            Decimal(data["cash_paid"]),
            Decimal(data["currency_quantum"]),
        )
        if actual != expected or any(
            not row["deducted_at_disbursal"] for row in frozen.get("fees", [])
        ):
            raise ValueError(message)
        if any(
            row.get("code") not in {"DOCUMENT_CHARGE", "DOC", "DOCUMENT", "DOC_FEE"}
            for row in frozen.get("fees", [])
        ):
            raise ValueError(
                "Retained fee components require their supported agreement review; do not relabel them as a document charge."
            )
        retained = payload["collateral"]
        items = list(loan.collateral_items.order_by("pk"))
        if [row["item_id"] for row in retained] != [row.pk for row in items]:
            raise ValueError(message)
        for original, row in zip(retained, contract_items(data), strict=True):
            for key, source in (
                ("principal", "allocated_principal"),
                ("rate", "monthly_interest_rate"),
                ("gross_weight", "gross_weight"),
                ("net_weight", "net_weight"),
                ("purity", "purity_percentage"),
            ):
                if Decimal(original[source]) != Decimal(row[key]):
                    raise ValueError(message)
            if any(
                original[key] != row[key]
                for key in ("description", "quantity", "metal")
            ):
                raise ValueError(message)
    except (KeyError, TypeError, ArithmeticError) as exc:
        raise ValueError(
            "Retained approval lacks supported agreement facts. Review its evidence explicitly before recording."
        ) from exc


@transaction.atomic
def preview_completed_payout(*, workspace, actor, loan_id, values, intent_token):
    from .recorded_history import preview_recorded_history

    loan, data, agreement = _completed_input(workspace, actor, loan_id, values)
    review, token = preview_recorded_history(
        workspace=workspace,
        actor=actor,
        data=data,
        intent_token=intent_token,
        draft_id=loan.pk,
    )
    return review, token, agreement


@transaction.atomic
def record_completed_payout(
    *, workspace, actor, loan_id, values, intent_token, review_token, confirmed=False
):
    from .recorded_history import admit_recorded_history

    loan, data, _ = _completed_input(workspace, actor, loan_id, values)
    return admit_recorded_history(
        workspace=workspace,
        actor=actor,
        data=data,
        intent_token=intent_token,
        draft_id=loan.pk,
        review_token=review_token,
        confirmed=confirmed,
    )


def apply_actual_contract(loan, data, *, actor, correction=False):
    """No quotes, policy lookup, number reissue, item replacement or fake approval."""
    from .recorded_items import contract_items

    if correction:
        from .origination_corrections import correction_source

        correction_source(loan, actor=actor)
    else:
        require_unpaid_draft(loan)
    if (
        data["borrower_id"],
        data["series_id"],
        data["product_version_id"],
        data["number"],
        data["date"],
    ) != (
        loan.borrower_id,
        loan.series_id,
        loan.product_version_id,
        loan.loan_number,
        loan.loan_date.isoformat(),
    ):
        raise ValueError(
            "Keep this draft's customer, series, product, number and original date. Correct its identity explicitly before recording a payout."
        )
    facts = contract_items(data)
    items = list(loan.collateral_items.select_for_update().order_by("pk"))
    if not items or len(items) != len(facts):
        raise ValueError(
            "Keep this draft's collateral items; correct item membership explicitly before admission."
        )
    frozen = loan.approval_snapshots.exists() and not correction
    actual = dict(
        principal_amount=Decimal(data["principal"]),
        monthly_interest_rate=Decimal(data["rate"]),
        tenure_months=data["tenure"],
    )
    if frozen and any(getattr(loan, name) != value for name, value in actual.items()):
        raise ValueError(
            "Actual terms differ from retained approval evidence. Reconcile the draft explicitly before admission."
        )
    for item, row in zip(items, facts, strict=True):
        values = dict(
            description=row["description"],
            metal=row["metal"],
            quantity=row["quantity"],
            gross_weight=Decimal(row["gross_weight"]),
            net_weight=Decimal(row["net_weight"]),
            purity_percentage=Decimal(row["purity"]),
            allocated_principal=Decimal(row["principal"]),
            monthly_interest_rate=Decimal(row["rate"]),
        )
        if correction and any(
            getattr(item, name) != values[name]
            for name in (
                "description",
                "metal",
                "quantity",
                "gross_weight",
                "net_weight",
                "purity_percentage",
            )
        ):
            raise ValueError(
                "Keep the retained physical collateral facts; reconcile changed jewellery evidence separately."
            )
        if frozen and any(
            getattr(item, name) != value for name, value in values.items()
        ):
            raise ValueError(
                "Actual collateral terms differ from retained approval evidence. Reconcile that evidence before admission."
            )
        for name, value in values.items():
            setattr(item, name, value)
        item.full_clean()
        item.save(update_fields=[*values, "updated_at"])
    for name, value in actual.items():
        setattr(loan, name, value)
    loan.updated_by = actor
    loan.full_clean()
    loan.save(update_fields=[*actual, "updated_by", "updated_at"])
    return items
