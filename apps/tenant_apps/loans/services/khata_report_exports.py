"""Bounded CSV exports materialized inside the authorized Workspace read."""
import csv
import io

from django.urls import reverse
from django.utils import timezone

from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.selectors.khata_reports import cash_row

MAX_EXPORT_ROWS = 10000


def _cell(value):
    # Staff-entered text must remain text when opened in a spreadsheet.
    if isinstance(value, str) and (value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n"))):
        return "'" + value
    return "" if value is None else value


def export_csv(*, workspace, section, queryset, absolute_url):
    if current_workspace_id() != workspace.pk:
        raise ValueError("Khata exports require the matching Workspace context.")
    rows = list(queryset[:MAX_EXPORT_ROWS + 1])
    if any(row.workspace_id != workspace.pk for row in rows):
        raise ValueError("Khata export rows must belong to the matching Workspace.")
    if len(rows) > MAX_EXPORT_ROWS:
        raise ValueError(f"Export exceeds {MAX_EXPORT_ROWS:,} rows. Narrow the dates, borrower, series or search and export again.")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    today = timezone.localdate().isoformat()
    def event_url(account_id, operation_id):
        return absolute_url(reverse("workspace_loans:khata_event", args=(workspace.slug, account_id, operation_id))) if operation_id else ""
    if section == "cash":
        writer.writerow(("Knowledge date", "Business date", "Recorded at", "Khata", "Borrower", "Party code", "Series", "Licence / independent",
            "Operation ID", "Event", "Recorded source amount INR", "Principal received INR", "Interest received INR", "Cash in INR", "Cash out INR",
            "Cash / resolution reference", "Note", "Corrected by ID", "Corrected on", "Corrects ID", "Actor", "Source URL"))
        for op in rows:
            row = cash_row(op)
            writer.writerow(tuple(_cell(value) for value in (today, op.business_date, op.created_at.isoformat(), op.account.account_number,
                op.account.borrower.display_name, op.account.borrower.party_code, op.account.series.name,
                op.account.series.license.license_number if op.account.series.license_id else "Independent", op.pk, op.get_kind_display(),
                op.amount, op.principal_in, op.interest_in, op.cash_in, op.cash_out, row["reference"], row["note"],
                op.corrected_by.pk if getattr(op, "corrected_by", None) else "",
                op.corrected_by.business_date if getattr(op, "corrected_by", None) else "", op.correction_of_id,
                op.created_by.get_username(), event_url(op.account_id, op.pk))))
    elif section == "custody":
        writer.writerow(("Current custody date", "Received date", "Khata", "Borrower", "Party code", "Series", "Licence / independent",
            "Item ID", "Permanent UUID", "Description", "Metal", "Pieces", "Gross g", "Net g", "Purity percent", "Storage", "Current custody",
            "Receipt source URL", "Active reservation ID", "Reserved on", "Reservation source URL", "Actual return ID", "Actual return date",
            "Actual recipient", "Actual handover reference", "Actual return source URL"))
        for item in rows:
            writer.writerow(tuple(_cell(value) for value in (today, item.received_operation.business_date, item.account.account_number,
                item.account.borrower.display_name, item.account.borrower.party_code, item.account.series.name,
                item.account.series.license.license_number if item.account.series.license_id else "Independent", item.pk, item.public_id,
                item.description, item.get_metal_display(), item.quantity, item.gross_weight, item.net_weight, item.purity,
                item.storage_reference, dict(held="Held, not reserved", pending="Awaiting handover", returned="Returned")[item.custody],
                event_url(item.account_id, item.received_operation_id), item.reservation_id if not item.returned else None,
                item.reserved_on if not item.returned else None, event_url(item.account_id, item.reservation_id) if not item.returned else "",
                item.return_id, item.return_on, item.return_recipient, item.return_reference, event_url(item.account_id, item.return_id))))
    else:
        raise ValueError("Unknown Khata report.")
    return stream.getvalue().encode("utf-8-sig")
