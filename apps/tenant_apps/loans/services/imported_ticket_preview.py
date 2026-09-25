"""Read-only reconstructed tickets from frozen opening evidence, never official issues."""
from dataclasses import replace
from apps.tenant_apps.loans.documents.display import collateral_description
from decimal import Decimal

import fitz

from apps.tenant_apps.loans.documents import ConfigurableDocumentRenderer, DocumentLayoutValidator
from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder as Projection
from .action_access import require_loan_action
from .document_issuance import _revision_assets
from .document_layouts import LoanDocumentLayoutService
from .documents import PawnLoanDocumentService
from .history_contract import digest
from .opening_evidence import read_opening_evidence
from .print_profiles import LoanDocumentPrintProfileService
from .ticket_documents import _prepare_ticket_display


def imported_ticket_payload(loan):
    origin = getattr(loan, "historical_import", None)
    event = loan.loan_events.filter(event_kind="MIGRATION_OPENING").first()
    if origin is None or event is None or loan.approval_snapshots.exists():
        raise ValueError("This preview requires an imported opening loan without a native approval.")
    opening = read_opening_evidence(loan, event)
    review = opening["review"]
    if origin.source_sha256 != digest(origin.document) or origin.document.get("review") != review:
        raise ValueError("Imported ticket evidence does not match its accepted source.")
    items = [{"item_id": opening["item_mapping"][row["id"]], "description": row["description"],
              "quantity": row.get("quantity"), "metal": row["metal"], "net_weight": row["net_weight"], "purity_percentage": row["purity"],
              # A source valuation claim is not a verified appraisal.
              "latest_appraised_value": row["valuation"].get("amount")}
             for row in review["collateral"]]
    principal = sum((Decimal(row["original_principal"]) for row in review["collateral"]), Decimal("0"))
    rates = {Decimal(row["monthly_rate"]) for row in review["collateral"]}
    rate = f"{next(iter(rates)):f}%" if len(rates) == 1 else "Varies by item (imported terms)"
    source = {"loan_number": review["source"]["number"], "loan_date": review["terms"]["original_date"],
              "principal_amount": str(principal), "borrower_id": loan.borrower_id, "collateral": items}
    details = Projection._identity_rows(loan) + (
        ("Document", "Reconstructed imported loan ticket preview"),
        ("Document status", "PREVIEW - reconstructed from imported records; not an original or official issue"),
        ("Loan source ID", f"PawnLoan:{loan.pk}"),
        ("Approval source ID", "Not recorded (imported opening)"),
        ("Approval fingerprint", "Not available"),
        ("Official loan number", source["loan_number"]), ("Loan date", source["loan_date"]),
        ("Principal", Projection._money(principal)), ("Monthly interest rate", rate),
        ("Borrower", f"{loan.borrower.display_name} ({loan.borrower.party_code})"),
        ("Borrower source ID", f"Party:{loan.borrower_id}"),
        ("Lifecycle state", "Imported opening"), ("Tenure", "Original tenure not verified"),
    )
    rows = [("Item ID", "Description", "Metal", "Net weight", "Purity", "Appraisal", "Custody")]
    rows.extend((str(row["item_id"]), collateral_description(row), row["metal"].title(), row["net_weight"],
                 f"{row['purity_percentage']}%", Projection._money(row["latest_appraised_value"])
                 if row["latest_appraised_value"] is not None else "Unknown", "At import") for row in items)
    payload = Projection._payload("loan_ticket", "Imported Loan Ticket Preview", f"imported-ticket-{loan.pk}.pdf",
        Projection._verification(loan, f"import-preview:{origin.public_id}:{origin.source_sha256}"),
        details, (("Collateral", rows),))
    return payload, source, origin


def render_imported_ticket_preview(*, loan, actor, address_id=None):
    return _render_imported_ticket(loan=loan, actor=actor, address_id=address_id, as_copy=False)


def render_imported_ticket_copy(*, loan, actor, address_id=None):
    """Print a reconstructed imported copy, without issuing a native ticket."""
    return _render_imported_ticket(loan=loan, actor=actor, address_id=address_id, as_copy=True)


def _render_imported_ticket(*, loan, actor, address_id, as_copy):
    require_loan_action(loan, actor, "data.view")
    payload, source, origin = imported_ticket_payload(loan)
    if as_copy:
        values = {"document.name": "Imported loan copy", "document.status": "Reprinted from imported records"}
        payload = replace(payload, title="Imported Loan Copy", file_name=f"imported-loan-copy-{loan.pk}.pdf",
            verification_id=Projection._verification(loan, f"import-copy:{origin.public_id}:{origin.source_sha256}"),
            fields=tuple(replace(field, value=values[field.key]) if field.key in values else field for field in payload.fields))
    revision = LoanDocumentLayoutService.resolve(workspace=loan.workspace, document_type="loan_ticket",
                                                license=loan.license, series=loan.series)
    if revision is None:
        result = PawnLoanDocumentService.render_payload(payload)
    else:
        layout = DocumentLayoutValidator.load(revision.definition)
        assets = _revision_assets(revision)
        if layout.schema_version >= 4:
            prepared = _prepare_ticket_display(loan=loan, layout=layout, actor=actor, address_id=address_id,
                preview=True, payload=payload, source=source,
                evidence={"historical_import_id": origin.pk, "source_sha256": origin.source_sha256})
            payload, assets = prepared.payload, assets + prepared.assets
        profile = LoanDocumentPrintProfileService.resolve(workspace=loan.workspace, document_type="loan_ticket", series=loan.series)
        result = ConfigurableDocumentRenderer.render_with_print_profile(payload, layout, profile.definition,
            preview=True, assets=assets, show_preview_notice=not as_copy)
    # Keep the provenance visible even when a custom layout omits document.status.
    # This is in-memory only; no issue row, stored artifact or financial event.
    with fitz.open(stream=result.pdf, filetype="pdf") as pdf:
        for page in pdf:
            remaining = page.insert_textbox(fitz.Rect(12, page.rect.height - 20, page.rect.width - 12, page.rect.height - 4),
                "Reprinted from imported records" if as_copy else "RECONSTRUCTED IMPORT PREVIEW - NOT AN OFFICIAL ISSUE",
                fontsize=7, color=(0.3, 0.3, 0.3) if as_copy else (0.7, 0, 0), align=1)
            if remaining < 0:
                raise ValueError("The imported-preview notice does not fit this paper size.")
        content = pdf.tobytes()
    return content, payload.file_name
