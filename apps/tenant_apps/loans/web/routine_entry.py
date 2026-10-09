"""Bound fields for the shared routine editor; financial adapters stay separate."""

from django.core.exceptions import ValidationError

from apps.tenant_apps.loans.domain import LoanDocumentKind
from apps.tenant_apps.loans.models import LoanNumberSequence
from apps.tenant_apps.loans.services.number_allocation import preview_number


def routine_entry_context(request, form, *, purpose):
    names = (("borrower", "series", "product_version", "loan_date", "tenure_months")
        if purpose == "direct" else ("borrower_id", "series_id", "product_version_id", "date", "tenure"))
    return dict(loan_details_fields=[form[name] for name in names],
        routine_editor=True,
        **(_paper_number_context(form) if purpose == "paper" else {}),
        **(_paper_agreement_context(form) if purpose == "paper" else {}),
        entry_photo_reselect=bool(request.FILES),
        can_add_customer=any(request.loans_workspace_access.can(action) for action in ("contact.create", "data.create")),
        can_manage_loan_setup=request.loans_workspace_access.can("workspace.settings.manage"))


def _paper_number_context(form):
    """Describe the selected series without reserving or replacing a paper number."""
    form.fields["number"].widget.attrs["aria-describedby"] = "paper-number-guidance"
    try:
        series = form.fields["series_id"].to_python(form["series_id"].value())
    except ValidationError:
        series = None
    sequence = LoanNumberSequence.objects.filter(
        workspace_id=series.workspace_id, series=series,
        document_kind=LoanDocumentKind.PAWN_LOAN.value,
    ).first() if series else None
    hint = None
    if series:
        hint = {"prefix": sequence.prefix, "width": sequence.width} if sequence else {}
        try:
            hint["value"] = preview_number(series=series, document_kind=LoanDocumentKind.PAWN_LOAN).value
        except ValueError as exc:
            hint["error"] = str(exc)
    return {"paper_number_hint": hint,
            "paper_number_suggestion": getattr(form, "paper_number_suggestion",
                form.data.get("paper_number_suggestion", "") if form.is_bound else "")}


def prepare_paper_number_defaults(form):
    """Prefill routine presentation only; submitted financial facts are never replaced."""
    context = _paper_number_context(form)
    suggested = (context["paper_number_hint"] or {}).get("value")
    if not suggested or (form.is_bound and (form.data.get("review_token") or
            form.data.get("action") not in {"entry_change", "layout_change", "terms"})):
        return
    previous = form.data.get("paper_number_suggestion", "") if form.is_bound else ""
    values = form.data.copy() if form.is_bound else form.initial
    for name in ("number", "source_reference"):
        value = values.get(name, "")
        if not str(value or "").strip() or (previous and value == previous):
            values[name] = suggested
    if form.is_bound:
        values["paper_number_suggestion"] = suggested
        form.data = values
    form.paper_number_suggestion = suggested


def _paper_agreement_context(form):
    defaults = (form.terms or {}).get("values", {})
    monitoring_names = ("monitoring_method", "monitoring_ltv", "monitoring_reason")
    # No selected/valid series means setup has not been resolved yet, rather
    # than a missing policy. Only ask for setup after checking that scope.
    missing_monitoring = form.terms is not None and any(
        defaults.get(name) is None for name in monitoring_names)
    # A retained actual rounding exception must remain visible on redisplay;
    # ordinary entry only carries the standing value as a hidden form field.
    rounding = form["currency_quantum"].value()
    rounding_needed = form.terms is not None and (defaults.get("currency_quantum") is None or (
        bool(form["exceptions"].value()) and str(rounding) != str(defaults["currency_quantum"])))
    term_names = ("rate", "advance_months", "document_charge", "exception_reason")
    missing_tenure = form.terms is not None and defaults.get("tenure") is None
    # A percentage fee awaits the entered principal; that is not missing setup.
    # Item-specific setup messages also matter when the first item's rate exists.
    missing_agreement = form.terms is not None and (any(
        defaults.get(name) is None for name in ("rate", "tenure", "advance_months")) or any(
        not message.startswith("Choose the current monitoring basis;")
        for message in form.terms.get("messages", [])))
    terms_open = missing_agreement or bool(form["exceptions"].value()) or any(
        name in form.errors for name in (*term_names, "tenure"))
    payout_open = bool(form["cash_paid"].value()) or form["payout_basis"].value() == "CASH" or any(
        name in form.errors for name in ("cash_paid", "payout_basis"))
    return {
        "paper_term_fields": [form[name] for name in term_names],
        "paper_monitoring_fields": [form[name] for name in monitoring_names],
        "paper_monitoring_missing": missing_monitoring,
        "paper_rounding_needed": rounding_needed,
        "paper_tenure_missing": missing_tenure,
        "paper_agreement_missing": missing_agreement,
        "paper_terms_open": terms_open,
        "paper_payout_open": payout_open,
        "paper_additional_open": terms_open or payout_open or missing_monitoring or rounding_needed
            or bool(form["license_revision_id"].errors)
            or (form.is_bound and "source_license_from_setup" in form.data
                and not form["source_license_from_setup"].value())
            or bool(form["license_revision_id"].value() and not form["source_license_from_setup"].value()),
    }
