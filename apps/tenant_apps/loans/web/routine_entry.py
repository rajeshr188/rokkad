"""Bound fields for the shared routine editor; financial adapters stay separate."""


def routine_entry_context(request, form, *, purpose):
    names = (("borrower", "series", "product_version", "loan_date", "tenure_months")
        if purpose == "direct" else ("borrower_id", "series_id", "product_version_id", "date", "tenure"))
    return dict(loan_details_fields=[form[name] for name in names],
        routine_editor=True,
        entry_photo_reselect=bool(request.FILES),
        can_add_customer=any(request.loans_workspace_access.can(action) for action in ("contact.create", "data.create")),
        can_manage_loan_setup=request.loans_workspace_access.can("workspace.settings.manage"))
