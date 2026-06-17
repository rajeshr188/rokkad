from dataclasses import dataclass

from apps.tenant_apps.girvi.filters import LoanFilter
from apps.tenant_apps.girvi.models import GivenLoan


@dataclass(frozen=True)
class LoanSelectionResult:
    loans: object | None
    error: str = ""
    invalid_ids: tuple[str, ...] = ()

    @property
    def is_valid(self):
        return not self.error


def parse_selected_ids(raw_ids):
    cleaned = []
    invalid = []
    for raw_id in raw_ids:
        try:
            parsed = int(raw_id)
            if parsed > 0:
                cleaned.append(parsed)
            else:
                invalid.append(raw_id)
        except (TypeError, ValueError):
            invalid.append(raw_id)
    return list(dict.fromkeys(cleaned)), tuple(invalid)


def unreleased_given_loan_selection(*, post_data, query_data):
    loan_kind = post_data.get("loan_kind", "given")
    if loan_kind != "given":
        return LoanSelectionResult(
            None,
            "This bulk action is available only for Given loans.",
        )

    base_qs = (
        GivenLoan.objects.unreleased()
        .select_related("borrower")
        .prefetch_related("notifications", "loanitems")
    )

    if post_data.get("selectall") == "selected":
        filterset = LoanFilter(query_data, queryset=base_qs)
        return LoanSelectionResult(filterset.qs.order_by("borrower"))

    selection, invalid_ids = parse_selected_ids(post_data.getlist("selection"))
    if invalid_ids:
        return LoanSelectionResult(
            None,
            "Invalid loan selection.",
            invalid_ids=invalid_ids,
        )
    if not selection:
        return LoanSelectionResult(
            None,
            "Please select at least one unreleased given loan.",
        )

    selected_loans = base_qs.filter(id__in=selection).order_by("borrower")
    if selected_loans.count() != len(selection):
        return LoanSelectionResult(
            None,
            "Some selected loans are not eligible.",
        )

    return LoanSelectionResult(selected_loans)
