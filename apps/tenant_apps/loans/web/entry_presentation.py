"""Read-only changes to the New loan presentation; never save a loan here."""
import json

from django.forms.utils import ErrorDict
from django.http import QueryDict

from apps.tenant_apps.loans.services.entry_purpose import default_entry_purpose


COMMON = (("borrower", "borrower_id"), ("series", "series_id"),
          ("product_version", "product_version_id"), ("loan_date", "date"))
ITEM_FACTS = ("description", "quantity", "metal", "gross_weight", "net_weight",
              "purity_percentage", "allocated_principal", "DELETE")
EXCLUDED = {"csrfmiddlewaretoken", "action", "entry_values", "review_token", "confirm_review", "direct_layout"}


def entry_presentation(request):
    """Return purpose and form state. Only entry_change may apply a new default."""
    posted = request.method == "POST"
    source = request.POST.get("entry_mode", "direct") if posted else request.GET.get("entry")
    source = source if source in ("paper", "direct") else "direct"
    # Already-open trial forms must remain read-only; the layout is no longer selectable.
    layout_change = posted and request.POST.get("action") == "layout_change"
    changing = posted and request.POST.get("action") in ("entry_change", "layout_change")
    selection = request.POST.get("entry_selection", "auto") if posted else request.GET.get("entry", "auto")
    if selection not in ("auto", "paper", "direct"):
        selection = "auto"
    old_series = (request.POST.get("include_old_series") if posted else request.GET.get("include_old_series")) in ("on", "true", "True", "1")
    if old_series and (source == "paper" or selection == "paper"):
        selection = "paper"
    archive = request.POST.get("archive_evidence_id") if posted else request.GET.get("archive")
    purpose, error = source, ""
    series = request.POST.get("series_id" if source == "paper" else "series") if posted else request.GET.get("series")
    if not posted and not series:
        from apps.tenant_apps.loans.selectors.series import running_series
        choices = list(running_series(request.loans_workspace).values_list("pk", flat=True)[:2])
        series = choices[0] if len(choices) == 1 else None
    if archive:
        purpose = "paper"
        changing = False
    elif not posted or (changing and not layout_change):
        try:
            configured = default_entry_purpose(workspace=request.loans_workspace, series_id=series)
            purpose = selection if selection != "auto" else configured.lower()
        except (ValueError, TypeError):
            error = "Select a series in this Workspace before applying its entry setting."

    state = {}
    try:
        raw = request.POST.get("entry_values", "") if posted else ""
        candidate = json.loads(raw) if raw and len(raw) <= 150000 else {}
        if isinstance(candidate, dict):
            for mode in ("paper", "direct"):
                values = candidate.get(mode, {})
                if isinstance(values, dict):
                    state[mode] = {key: value for key, value in values.items()
                                   if isinstance(key, str) and isinstance(value, str) and key not in EXCLUDED}
    except (ValueError, TypeError):
        pass
    if changing:
        values = {key: request.POST.get(key, "") for key in request.POST if key not in EXCLUDED}
        state[source] = values
        target = dict(state.get(purpose, {})) if purpose != source else dict(values)
        for native, paper in COMMON:
            target[paper if purpose == "paper" else native] = values.get(paper if source == "paper" else native, "")
        # Current physical item facts win; mode-specific rates/appraisals stay retained.
        try:
            count = max(0, min(100, int(values.get("collateral-TOTAL_FORMS", "0"))))
        except ValueError:
            count = 0
        for key in list(target):
            if key.startswith("collateral-") and not key.split("-", 2)[-1] in ITEM_FACTS:
                continue
            if key.startswith("collateral-"):
                target.pop(key)
        for index in range(count):
            for name in ITEM_FACTS:
                key = f"collateral-{index}-{name}"
                target[key] = values.get(key, "")
        target.update({"collateral-TOTAL_FORMS": str(count), "collateral-INITIAL_FORMS": "0",
                       "collateral-MIN_NUM_FORMS": "1", "collateral-MAX_NUM_FORMS": "100",
                       "entry_mode": purpose, "entry_selection": selection,
                       "action": "layout_change" if layout_change else "entry_change"})
        if purpose == "paper":
            target.setdefault("routine_entry", "on")
            target.setdefault("source_license_from_setup", "on")
            target.setdefault("events-TOTAL_FORMS", "1")
            target.setdefault("events-INITIAL_FORMS", "0")
        else:
            target.setdefault("tenure_months", values.get("tenure", ""))
        data = QueryDict("", mutable=True)
        data.update(target)
        request.POST = data
    return purpose, {"entry_selection": selection, "entry_values": json.dumps(state),
                     "direct_new_entry": purpose == "direct",
                     "entry_changing": changing, "entry_change_error": error,
                     "entry_file_warning": changing and bool(request.FILES)}


def presentation_errors(form, formset=None):
    """An entry-choice response displays values without asserting financial validity."""
    form._errors = ErrorDict()
    if formset is not None:
        for row in formset:
            row._errors = ErrorDict()
        formset._errors = [ErrorDict() for row in formset]
        formset._non_form_errors = formset.error_class()
