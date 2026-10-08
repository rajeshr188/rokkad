"""Immutable projections used by every PawnLoan document renderer.

Projection builders and the first-issue ticket service read authorized sources.
Renderers receive typed values and never calculate loan-domain facts.
"""

from dataclasses import dataclass
import hashlib
import json
from .display import collateral_description
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist

from apps.tenant_apps.loans.domain import PawnLoanState, TransactionKind


TICKET_FIELD_KEYS = {
    "License proprietor": "license.proprietor_name",
    "License business name": "license.business_name",
    "License business address": "license.business_address",
    "Generated at": "document.generated_at",
    "License number": "license.number", "Customer name": "borrower.name",
    "Customer relationship": "borrower.relationship", "Customer address": "borrower.address",
    "Customer phone": "borrower.phone", "Customer contact block": "borrower.contact_block",
    "Approved collateral descriptions": "collateral.description_lines",
    "Approved net weight by metal": "collateral.net_weight_by_metal",
    "Approved appraisal total": "collateral.approved_appraisal_total",
    "Principal in words": "loan.principal_words", "Loan summary label": "loan.summary_label",
}
TICKET_MEDIA_KEYS = {
    "Customer profile photograph": "borrower.photo",
    "First approved collateral photograph": "collateral.first_approved_photo",
}


@dataclass(frozen=True)
class DocumentMedia:
    binding: str
    asset_key: str
    status: str
    optional: bool = False


class DocumentProjectionError(ValueError):
    """The source is not eligible for the requested document."""


@dataclass(frozen=True)
class DocumentSection:
    key: str
    heading: str
    rows: tuple[tuple[object, ...], ...]


@dataclass(frozen=True)
class DocumentField:
    key: str
    label: str
    value: object


@dataclass(frozen=True)
class DocumentPayload:
    schema_version: int
    document_type: str
    title: str
    file_name: str
    verification_id: str
    fields: tuple[DocumentField, ...]
    sections: tuple[DocumentSection, ...] = ()
    media: tuple[DocumentMedia, ...] = ()

    @property
    def details(self):
        """Fixed-renderer compatibility view over the typed field registry."""
        return tuple((field.label, field.value) for field in self.fields)


class PawnLoanDocumentProjectionBuilder:
    SCHEMA_VERSION = 1
    FIELD_KEYS = {
        "Original approval time (source claim)": "provenance.original_approval_time",
        "Original approval actor reference": "provenance.original_approval_actor",
        "Evidence imported at": "provenance.approval_evidence_imported_at",
        "Release batch": "release.batch_id", "Paid by": "release.paid_by",
        "Paper reference": "release.paper_reference", "Entry source": "release.entry_source",
        "Later handover confirmation": "release.handover_confirmation",
        "Collected by": "release.collector_name", "Collector relationship": "release.collector_relationship",
        "Collection authorization": "release.collection_authorization",
        "Workspace": "workspace.name", "Workspace source ID": "workspace.source_id",
        "Regulatory license": "license.display", "License source ID": "license.source_id",
        "License authority": "license.authority", "License validity": "license.validity",
        "Document": "document.name", "Document status": "document.status",
        "Loan source ID": "loan.source_id", "Approval source ID": "approval.source_id",
        "Approval version": "approval.version", "Approval fingerprint": "approval.fingerprint",
        "Official loan number": "loan.number", "Loan date": "loan.date",
        "Lifecycle state": "loan.lifecycle_state", "Principal": "loan.principal",
        "Monthly interest rate": "loan.monthly_interest_rate", "Tenure": "loan.tenure",
        "Borrower": "borrower.display", "Borrower source ID": "borrower.source_id",
        "Repayment source ID": "repayment.source_id", "Event fingerprint": "event.fingerprint",
        "Paper receipt reference": "repayment.paper_reference",
        "Receipt entered at": "repayment.recorded_at",
        "Effective date": "event.effective_date", "Amount received": "repayment.amount_received",
        "Fees": "amounts.fees", "Overdue interest": "amounts.overdue_interest",
        "Current interest": "amounts.current_interest", "Total interest": "amounts.total_interest",
        "Release source ID": "release.source_id", "Release number": "release.number",
        "Loan event ID": "loan.event_source_id", "Release type": "release.type",
        "Principal settled": "amounts.principal_settled", "Interest settled": "amounts.interest_settled",
        "Fees settled": "amounts.fees_settled", "Total settlement": "amounts.total_settlement",
        "Interest lost / concession": "amounts.interest_conceded", "Concession reason": "release.concession_reason",
        "Auction source ID": "auction.source_id", "Auction number": "auction.number",
        "Notice date": "auction.notice_date", "Scheduled auction date": "auction.scheduled_date",
        "Notice delivery job": "auction.notice_delivery_job", "Buyer": "auction.buyer",
        "Buyer reference": "auction.buyer_reference", "Principal recovered": "amounts.principal_recovered",
        "Interest recovered": "amounts.interest_recovered", "Fees recovered": "amounts.fees_recovered",
        "Total recovery": "amounts.total_recovery", "Renewal source ID": "renewal.source_id",
        "Collection basis": "auction.collection_basis", "Paper coverage review": "auction.paper_coverage_review",
        "Renewal number": "renewal.number", "Renewal date": "renewal.date", "Mode": "renewal.mode",
        "Source loan": "renewal.source_loan", "Successor loan": "renewal.successor_loan",
        "Source principal settled": "renewal.source_principal_settled",
        "Principal paid": "renewal.principal_paid", "Top-up disbursed": "renewal.top_up_disbursed",
        "Gross new advance": "renewal.top_up_disbursed",
        "Successor principal": "renewal.successor_principal",
        "Successor advance interest": "renewal.successor_advance_interest",
        "Successor deducted fees": "renewal.successor_deducted_fees",
        "Net cash handoff": "renewal.net_cash_handoff",
        "Product": "contract.product", "Product version": "contract.product_version",
        "Repayment structure": "contract.repayment_structure",
        "Schedule fingerprint": "contract.schedule_fingerprint",
        "Maturity date": "contract.maturity_date", "Contractual interest": "contract.interest",
        "Total contractual repayment": "contract.total_repayment",
        "Advance interest deducted": "contract.advance_interest_deducted",
        "Document charge deducted": "contract.document_charge_deducted",
        "Paper proceeds after deductions": "contract.paper_proceeds",
        "Physical cash confirmation": "contract.physical_cash_confirmation",
        "Principal outstanding": "amounts.principal_outstanding",
        "Interest outstanding": "amounts.interest_outstanding",
        "Total due": "amounts.total_due",
    }
    SECTION_KEYS = {
        "Charged anniversary interest": "contract.repayment_schedule",
        "Collateral at paper closure": "release.collateral_returned",
        "Collateral": "collateral.items", "Collateral principal allocation": "repayment.principal_allocations",
        "Collateral returned": "release.collateral_returned", "Item principal settled": "release.principal_settled",
        "Collateral disposed": "auction.collateral_disposed", "Collateral movement": "renewal.collateral_movement",
        "Source item principal settled": "renewal.source_principal_settled",
        "Successor item principal opened": "renewal.successor_principal_opened",
        "Repayment schedule": "contract.repayment_schedule",
    }

    @classmethod
    def loan_ticket(cls, loan):
        from apps.tenant_apps.loans.services.recorded_collections import recording_for
        if recording_for(loan):
            return cls.recorded_contract(loan)
        if loan.state == PawnLoanState.DRAFT.value:
            raise DocumentProjectionError(
                "Loan ticket is unavailable while the loan is an editable draft."
            )
        approval = loan.approval_snapshots.order_by("-version").first()
        if approval is None:
            raise DocumentProjectionError(
                "Loan ticket is available only after the loan has an approval snapshot."
            )
        source = dict(approval.payload)
        historical = source.get('historical_approval')
        if historical and hasattr(loan, 'historical_import') and 'collateral' not in source:
            # Older approved-history admission freezes economics and source
            # claims rather than a prospective approval form. Project those
            # accepted facts without changing the immutable approval row.
            original = loan.historical_import.document.get('loan', {})
            references = loan.historical_import.references.get('items', {})
            if not original.get('collateral'):
                raise DocumentProjectionError('Imported approval is missing its retained original agreement.')
            source.update(loan_number=loan.loan_number, loan_date=original['disbursed_on'], borrower_id=loan.borrower_id,
                monthly_interest_rate=str(loan.monthly_interest_rate), tenure_months=original['tenure_months'],
                collateral=[dict(item_id=references[r['id']], description=r['description'], metal=r['metal'],
                    net_weight=r['net_weight'], purity_percentage=r['purity'], latest_appraised_value=r['appraised_value']) for r in original['collateral']])
        verification = cls._verification(
            loan, f"approval:{approval.pk}:v{approval.version}:{approval.fingerprint}"
        )
        details = cls._identity_rows(loan) + (
            ("Document", "Pawn loan ticket"),
            ("Loan source ID", f"PawnLoan:{loan.pk}"),
            ("Approval source ID", f"PawnLoanApprovalSnapshot:{approval.pk}"),
            ("Approval version", approval.version),
            ("Official loan number", source["loan_number"]),
            ("Loan date", source["loan_date"]),
            ("Lifecycle state", loan.get_state_display()),
            ("Principal", cls._money(source["principal_amount"])),
            ("Monthly interest rate", f"{source['monthly_interest_rate']}%"),
            ("Tenure", f"{source['tenure_months']} months"),
            ("Borrower", f"{loan.borrower.display_name} ({loan.borrower.party_code})"),
            ("Borrower source ID", f"Party:{source['borrower_id']}"),
            ("Approval fingerprint", approval.fingerprint),
        )
        if historical:
            details += (("Document status", "Imported source agreement; this copy does not attest to a new retrospective lending approval"),
                ("Original approval time (source claim)", historical.get('at') or 'Unknown'),
                ("Original approval actor reference", historical.get('actor') or 'Unknown'),
                ("Evidence imported at", approval.approved_at.isoformat()))
        rows = [("Item ID", "Description", "Metal", "Net weight", "Purity", "Appraisal", "Custody")]
        rows.extend(
            (
                str(item["item_id"]), collateral_description(item), item["metal"].title(),
                item["net_weight"], f"{item['purity_percentage']}%",
                cls._money(item["latest_appraised_value"])
                if item["latest_appraised_value"] is not None else "—",
                "At approval",
            )
            for item in source["collateral"]
        )
        return cls._payload(
            "loan_ticket", "Pawn Loan Ticket",
            f"pawn_loan_ticket_{source['loan_number']}.pdf", verification, details,
            (("Collateral", rows),),
        )

    @classmethod
    def loan_kfs_schedule(cls, loan):
        from apps.tenant_apps.loans.services.recorded_collections import recording_for
        if recording_for(loan):
            return cls.recorded_contract(loan, position=True)
        schedule = loan.repayment_schedules.order_by("-version").first()
        if schedule is None:
            raise DocumentProjectionError("A key-facts schedule requires a persisted repayment schedule.")
        product_version = loan.product_version
        verification = cls._verification(loan, f"schedule:{schedule.pk}:{schedule.fingerprint}")
        total = schedule.principal + schedule.contractual_interest + schedule.rounding_adjustment
        details = cls._identity_rows(loan) + (
            ("Document", "Key facts and repayment schedule"),
            ("Official loan number", loan.loan_number),
            ("Borrower", f"{loan.borrower.display_name} ({loan.borrower.party_code})"),
            ("Product", product_version.product.name),
            ("Product version", f"{product_version.product.code} v{product_version.version}"),
            ("Repayment structure", product_version.get_repayment_structure_display()),
            ("Principal", cls._money(schedule.principal)),
            ("Contractual interest", cls._money(schedule.contractual_interest)),
            ("Total contractual repayment", cls._money(total)),
            ("Maturity date", schedule.maturity_date),
            ("Schedule fingerprint", schedule.fingerprint),
        )
        rows = [("Sequence", "Due date", "Opening principal", "Principal due", "Interest due", "Closing principal")]
        rows.extend((row.sequence, row.due_date, cls._money(row.opening_principal), cls._money(row.principal_due), cls._money(row.interest_due), cls._money(row.closing_principal)) for row in schedule.obligations.order_by("sequence"))
        return cls._payload("loan_kfs_schedule", "Key Facts and Repayment Schedule", f"pawn_loan_kfs_{loan.loan_number}.pdf", verification, details, (("Repayment schedule", rows),))

    @classmethod
    def recorded_position_fingerprint(cls, loan, day):
        from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_fingerprint, transaction_completeness
        material = dict(financial=transaction_fingerprint(loan), date=day.isoformat(),
            coverage=transaction_completeness(loan, day).evidence())
        return hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest()

    @classmethod
    def recorded_contract(cls, loan, *, position=False, as_of_date=None):
        from django.utils import timezone
        from apps.tenant_apps.loans.services.recorded_collections import recording_for, collection_state, collection_balance
        from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
        recording = recording_for(loan)
        origin = loan.loan_events.filter(event_kind__in=("DISBURSAL", "RENEWAL_OPENING"), reversed_by_event__isnull=True).order_by("-pk").first()
        if not recording or not origin:
            raise DocumentProjectionError("A recorded contract requires its original financial source.")
        terms, day = recording["terms"], as_of_date or timezone.localdate()
        identity = cls.recorded_position_fingerprint(loan, day) if position else origin.payload_fingerprint
        status = f"Recorded from paper; source {recording['source_reference']}; entered {origin.created_at.isoformat()}; generated {timezone.now().isoformat()}; original digital approval absent"
        if recording.get("origination_correction"):
            correction = recording["origination_correction"]
            status += f"; actual-paper origination correction; reversed digital attempts retained; reason {correction['reason']}"
        if recording.get("contract_correction"):
            correction = recording["contract_correction"]
            status += f"; corrected contract; previous event #{correction['source_event_id']}; checked source {correction['reference']}; reason {correction['reason']}"
        details = cls._identity_rows(loan) + (
            ("Document", "Recorded paper contract and current interest position" if position else "Recorded paper loan contract"),
            ("Document status", status), ("Loan source ID", f"PawnLoan:{loan.pk}"),
            ("Loan event ID", f"PawnLoanEvent:{origin.pk}"), ("Event fingerprint", origin.payload_fingerprint),
            ("Official loan number", terms["loan_number"]), ("Loan date", recording["occurred_on"]),
            ("Borrower", f"{loan.borrower.display_name} ({loan.borrower.party_code})"),
            ("Principal", cls._money(terms["principal_amount"])),
            ("Monthly interest rate", f"{terms['monthly_interest_rate']}%"), ("Tenure", f"{terms['tenure_months']} months"),
        )
        funding = recording.get("funding", {})
        cash = recording.get("cash_evidence", {})
        charge = funding.get("document_charge", cash.get("new_document_charge", "0"))
        confirmation = ("Unspecified; proceeds may have settled another paper loan" if funding.get("basis") == "PROCEEDS"
            else f"Net received {cash['cash_received']}; net paid {cash['cash_paid']}" if cash else "Cash payout recorded from paper")
        details += (("Advance interest deducted", cls._money(recording["advance_interest"])),
            ("Document charge deducted", cls._money(charge)),
            ("Paper proceeds after deductions", cls._money(Decimal(terms["principal_amount"])-Decimal(recording["advance_interest"])-Decimal(charge))),
            ("Physical cash confirmation", confirmation))
        rows = [("Item ID", "Description", "Metal", "Net weight", "Purity", "Original appraisal")]
        rows.extend((row["item_id"], collateral_description(row), row["metal"], row["net_weight"],
            row["purity_percentage"], "Not recorded") for row in terms["collateral"])
        sections = [("Collateral", rows)]
        if position:
            balance = collection_balance(loan, day)
            coverage = transaction_completeness(loan, day)
            status += f"; transaction coverage {coverage.status}; paper checked through {coverage.through_date}"
            details = tuple((label, status if label == "Document status" else value) for label, value in details)
            details += (("Effective date", day), ("Principal paid", cls._money(balance.principal_paid)),
                ("Principal outstanding", cls._money(balance.principal_outstanding)),
                ("Interest outstanding", cls._money(balance.interest_outstanding)),
                ("Total due", cls._money(balance.total_due)),)
            months = collection_state(loan, day)["months"]
            charges = [("Anniversary", "Principal charged", "Full-month interest", "First-month credit")]
            charges.extend((row["start"], cls._money(row["principal"]), cls._money(row["interest"]),
                cls._money(recording["advance_interest"]) if index == 0 else "0") for index, row in enumerate(months))
            sections.append(("Charged anniversary interest", charges))
        return cls._payload("loan_kfs_schedule" if position else "loan_ticket",
            "Recorded Paper Contract and Interest Position" if position else "Recorded Paper Loan Contract",
            f"paper_{'position' if position else 'contract'}_{loan.loan_number}.pdf",
            cls._verification(loan, f"recorded:{identity}"), details, sections)

    @classmethod
    def repayment_receipt(cls, event):
        if event.event_kind != TransactionKind.REPAYMENT.value:
            raise DocumentProjectionError("A repayment receipt requires a repayment event.")
        loan = event.loan
        values = event.payload.get("values") or {}
        repayment = event.payload.get("repayment") or {}
        reversed_by = cls._related_or_none(event, "reversed_by_event")
        recording = repayment.get("recording")
        status = f"Reversed by event {reversed_by.pk}" if reversed_by else "Recorded"
        if recording:
            status += " from paper; allocation calculated from agreed terms"
        correction = event.payload.get("history_correction")
        if correction:
            status += (f"; historical correction recorded {event.created_at.isoformat()}; "
                       f"{correction.get('description', 'Revised historical evidence')}; source event {correction.get('source_event_id') or 'missing receipt'}; "
                       "not a new cash collection")
        verification = cls._verification(loan, f"repayment:{event.pk}:{event.payload_fingerprint}")
        details = cls._identity_rows(loan) + (
            ("Document", "Repayment receipt"),
            ("Repayment source ID", f"PawnLoanEvent:{event.pk}"),
            ("Document status", status),
            ("Event fingerprint", event.payload_fingerprint),
            ("Effective date", event.effective_date),
            ("Official loan number", loan.loan_number),
            ("Borrower", f"{loan.borrower.display_name} ({loan.borrower.party_code})"),
            ("Amount received", cls._money(repayment.get("amount_received"))),
            ("Fees", cls._money(values.get("fees"))),
            ("Overdue interest", cls._money(values.get("overdue_interest"))),
            ("Current interest", cls._money(values.get("current_interest"))),
            ("Total interest", cls._money(values.get("interest"))),
            ("Principal", cls._money(values.get("principal"))),
        )
        if recording:
            details += (("Paper receipt reference", recording["receipt_reference"]),
                        ("Receipt entered at", event.created_at))
        manager = cls._related_or_none(event, "repayment_allocation_lines")
        sections = ()
        if manager is not None:
            lines = manager.select_related("collateral_item").order_by("allocation_order")
            rows = [("Item", "Description", "Rate", "Before", "Principal", "After")]
            rows.extend(
                (line.collateral_item_id, line.collateral_item.description,
                 f"{line.monthly_interest_rate}%", cls._money(line.balance_before),
                 cls._money(line.principal_applied), cls._money(line.balance_after))
                for line in lines
            )
            if len(rows) > 1:
                sections = (("Collateral principal allocation", rows),)
        return cls._payload(
            "repayment_receipt", "Pawn Loan Repayment Receipt",
            f"pawn_repayment_{loan.loan_number}_{event.pk}.pdf", verification, details, sections,
        )

    @classmethod
    def release_memo(cls, release):
        from apps.tenant_apps.loans.selectors.recorded_settlements import restated_release, correction_label
        release = restated_release(release)
        loan, event = release.loan, release.loan_event
        paper = (getattr(event, "payload", {}) or {}).get("release", {}).get("paper_closure", {})
        recorded_status = (f"Recorded from paper; source {paper.get('paper_reference', '')}; entered {event.created_at.isoformat()}"
                           if paper.get("profile") == "recorded-history-closure/1" else "Completed")
        recorded_status = correction_label(event) or recorded_status
        concession = (getattr(event, "payload", {}) or {}).get("values", {}).get("interest_concession", "0")
        interest_display = cls._money(release.interest_amount)
        if Decimal(str(concession)):
            # This existing mandatory binding also reaches previously published layouts.
            interest_display += (f" collected; {cls._money(concession)} forgone: "
                                 + event.payload["release"]["interest_concession_reason"])
        reversal = cls._related_or_none(release, "reversal")
        from apps.tenant_apps.loans.services.paper_handover import release_document_fingerprint
        verification = cls._verification(
            loan, f"release:{release.pk}:{release.release_number}:{release_document_fingerprint(release)}"
        )
        details = cls._identity_rows(loan) + (
            ("Document", "Release memo / Form H equivalent"),
            ("Release source ID", f"PawnLoanRelease:{release.pk}"),
            ("Document status", f"Reversed by release reversal {reversal.pk}" if reversal else recorded_status),
            ("Release number", release.release_number + (" (system recording number; no original paper number)" if paper.get("number_basis") == "SYSTEM_ASSIGNED" else "")),
            ("Official loan number", loan.loan_number),
            ("Loan event ID", f"PawnLoanEvent:{event.pk}"),
            ("Event fingerprint", event.payload_fingerprint),
            ("Effective date", release.effective_date),
            ("Release type", "Full" if release.is_full_release else "Partial"),
            ("Borrower", f"{loan.borrower.display_name} ({loan.borrower.party_code})"),
            ("Principal settled", cls._money(release.principal_amount)),
            ("Interest settled", interest_display),
            ("Fees settled", cls._money(release.fee_amount)),
            ("Total settlement", cls._money(release.settlement_amount)),
        )
        batch_line = cls._related_or_none(release, "batch_line")
        if paper.get("profile") == "recorded-history-closure/1":
            details += (("Paper reference", paper["paper_reference"]), ("Collected by", paper["collector_name"]),
                        ("Entry source", "Recorded paper history; actual return date retained, original operator and time unknown"))
            if paper.get("closure_basis") == "PAPER_SETTLEMENT":
                details = tuple((label, "Not confirmed by paper record" if label == "Collected by" else
                    "Paper settlement; physical cash and customer handover unspecified" if label == "Entry source" else value)
                    for label, value in details)
            elif batch_line is None and "paid_by" in paper:
                details += (("Paid by", paper["paid_by"]),
                    ("Collector relationship", "Borrower" if paper["collector_is_borrower"] else paper["relationship"]),
                    ("Collection authorization", paper["authorization_note"] or "Borrower receipt attested from paper record"))
        if Decimal(str(concession)):
            details += (("Interest lost / concession", cls._money(concession)),
                        ("Concession reason", event.payload["release"]["interest_concession_reason"]))
        if batch_line is not None:
            unspecified = paper.get("closure_basis") == "PAPER_SETTLEMENT"
            details += (
                ("Release batch", batch_line.batch_id), ("Paid by", "Not established" if unspecified else batch_line.paid_by or batch_line.batch.paid_by),
                ("Collected by", "Not confirmed by paper record" if unspecified else batch_line.collector_name),
                ("Collector relationship", "Not established" if unspecified else "Borrower" if batch_line.collector_is_borrower else batch_line.relationship),
                ("Collection authorization", "Not established" if unspecified else batch_line.authorization_note or ("Borrower receipt attested from paper record" if batch_line.batch.mode == "PAPER" else "Borrower verified; items ready for handover")),
            )
            if batch_line.batch.mode == "PAPER":
                details += (("Paper reference", batch_line.paper_reference or "Not supplied"),
                            ("Entry source", "Paper settlement; physical cash and customer handover unspecified" if unspecified else "Paper closure; return date attested, exact time unknown"))
        item_rows = [("Item ID", "Description", "Value at release", "Returned at")]
        for item in release.items.all():
            snapshot = item.valuation_snapshot or {}
            item_rows.append((str(item.collateral_item_id), item.collateral_item.description,
                              ("Not recorded" if paper.get("profile") == "recorded-history-closure/1" and snapshot.get("valuation_amount") is None else cls._money(snapshot.get("valuation_amount"))), str(item.returned_at) if item.returned_at else release.effective_date.strftime("%d/%m/%Y") + " (time unknown; paper record)"))
        if paper.get("closure_basis") == "PAPER_SETTLEMENT":
            item_rows = [item_rows[0]] + [tuple(row[:3]) + ("Customer handover unconfirmed",) for row in item_rows[1:]]
            from apps.tenant_apps.loans.services.paper_handover import confirmation_for
            handover = confirmation_for(release)
            if handover:
                facts = handover["facts"]
                details += (("Later handover confirmation", f"{facts['date']}; recipient {facts['recipient']}; source {facts['reference']}"),)
                item_rows = [item_rows[0]] + [tuple(row[:3]) + (facts["date"] + " (confirmed later; original return time unknown)",) for row in item_rows[1:]]
        sections = [("Collateral at paper closure" if paper.get("closure_basis") == "PAPER_SETTLEMENT" else "Collateral returned", item_rows)]
        manager = cls._related_or_none(event, "principal_closing_lines")
        if manager is not None:
            rows = [("Item", "Description", "Rate", "Before", "Settled", "After")]
            rows.extend(
                (line.collateral_item_id, line.collateral_item.description,
                 f"{line.monthly_interest_rate}%", cls._money(line.balance_before),
                 cls._money(line.principal_settled), cls._money(line.balance_after))
                for line in manager.select_related("collateral_item").order_by("allocation_order")
            )
            if len(rows) > 1:
                sections.append(("Item principal settled", rows))
        return cls._payload("release_memo", "Pawn Loan Release Memo",
                            f"pawn_release_{release.release_number}.pdf", verification, details, sections)

    @classmethod
    def auction_notice(cls, auction):
        loan = auction.loan
        reversal = cls._related_or_none(auction, "reversal")
        verification = cls._verification(loan, f"auction-notice:{auction.pk}:{auction.auction_number}")
        details = cls._identity_rows(loan) + (
            ("Document", "Pawn loan auction notice"),
            ("Auction source ID", f"PawnLoanAuction:{auction.pk}"),
            ("Auction number", auction.auction_number),
            ("Document status", f"Recovery reversed by {reversal.pk}" if reversal else auction.get_state_display()),
            ("Official loan number", loan.loan_number),
            ("Borrower", f"{loan.borrower.display_name} ({loan.borrower.party_code})"),
            ("Notice date", auction.notice_date),
            ("Scheduled auction date", auction.scheduled_date),
            ("Notice delivery job", getattr(getattr(auction, "notice", None), "notification_job_id", "Not requested")),
        )
        return cls._payload("auction_notice", "Pawn Loan Auction Notice",
                            f"pawn_auction_notice_{auction.auction_number}.pdf", verification, details)

    @classmethod
    def auction_recovery_memo(cls, auction):
        if not auction.loan_event_id:
            raise DocumentProjectionError("Auction recovery memo is available only after completion.")
        loan, event = auction.loan, auction.loan_event
        reversal = cls._related_or_none(auction, "reversal")
        verification = cls._verification(loan, f"auction-recovery:{auction.pk}:{event.payload_fingerprint}")
        details = cls._identity_rows(loan) + (
            ("Document", "Pawn loan auction recovery memo"),
            ("Auction source ID", f"PawnLoanAuction:{auction.pk}"),
            ("Auction number", auction.auction_number),
            ("Document status", f"Reversed by auction reversal {reversal.pk}" if reversal else "Completed"),
            ("Effective date", event.effective_date),
            ("Buyer", auction.buyer_name),
            ("Buyer reference", auction.buyer_reference or "Not recorded"),
            ("Principal recovered", cls._money(auction.principal_amount)),
            ("Interest recovered", cls._money(auction.interest_amount)),
            ("Fees recovered", cls._money(auction.fee_amount)),
            ("Total recovery", cls._money(auction.recovery_amount)),
        )
        collection = getattr(event, "payload", {}).get("auction", {}).get("recorded_collection")
        if collection:
            details += (("Collection basis", "Agreed paper anniversary interest; actual principal history"),
                        ("Paper coverage review", str(collection["coverage"]["review_id"])))
        opening_collection = event.payload.get("opening_collection")
        if opening_collection:
            details += (("Collection basis", "Reviewed opening checkpoint; original anniversary and post-cutover principal history"),
                        ("Opening source event", str(opening_collection["opening_event_id"])))
        rows = [("Item ID", "Description", "Metal", "Net weight", "Purity")]
        for item in auction.items.select_related("collateral_item"):
            snapshot = item.snapshot or {}
            rows.append((str(item.collateral_item_id), snapshot.get("description", item.collateral_item.description),
                         snapshot.get("metal", ""), snapshot.get("net_weight", ""),
                         snapshot.get("purity_percentage", "")))
        return cls._payload("auction_recovery", "Pawn Loan Auction Recovery Memo",
                            f"pawn_auction_recovery_{auction.auction_number}.pdf", verification,
                            details, (("Collateral disposed", rows),))

    @classmethod
    def renewal_memo(cls, renewal):
        from apps.tenant_apps.loans.selectors.recorded_settlements import restated_renewal, correction_label
        renewal = restated_renewal(renewal)
        source, successor = renewal.source_loan, renewal.successor_loan
        paper = renewal.valuation_snapshot.get("recorded_admission")
        cash_evidence = renewal.valuation_snapshot.get("cash_evidence") or {}
        reversal = cls._related_or_none(renewal, "reversal")
        verification = cls._verification(source, f"renewal:{renewal.pk}:{renewal.settlement_event.payload_fingerprint}")
        cash_received = (
            renewal.interest_settled
            + renewal.fees_settled
            + renewal.principal_paid
            + renewal.successor_advance_interest
            + renewal.successor_deducted_fees
        )
        net_cash = cash_received - renewal.top_up_amount
        if net_cash > 0:
            net_cash_handoff = f"Collect {cls._money(net_cash)} from customer"
        elif net_cash < 0:
            net_cash_handoff = f"Pay {cls._money(-net_cash)} to customer"
        else:
            net_cash_handoff = "No net cash handoff"
        if paper:
            net_cash_handoff = f"Received {cls._money(net_cash)} on {renewal.renewal_date}; principal carried without fresh payout"
        if cash_evidence:
            net_cash_handoff = (f"Received {cls._money(cash_evidence['cash_received'])}; paid out {cls._money(cash_evidence['cash_paid'])} "
                f"on {renewal.renewal_date}; old interest offset {cls._money(cash_evidence['interest_offset'])}; "
                f"principal carried {cls._money(cash_evidence['principal_carried'])}")
        mode = ("Actual full principal repayment and fresh advance" if cash_evidence.get("method") == "REPAY_REDRAW"
                else "Principal carry with reduction or top-up") if cash_evidence else renewal.get_mode_display()
        recorded_status = (f"Recorded from paper; source {renewal.valuation_snapshot['paper_reference']}; entered {renewal.created_at.isoformat()}"
                           if paper else "Completed")
        recorded_status = correction_label(renewal.settlement_event) or recorded_status
        details = cls._identity_rows(source) + (
            ("Document", "Pawn loan renewal agreement"),
            ("Renewal source ID", f"PawnLoanRenewal:{renewal.pk}"),
            ("Renewal number", renewal.renewal_number),
            ("Document status", f"Reversed by {reversal.pk}" if reversal else recorded_status),
            ("Renewal date", renewal.renewal_date), ("Mode", mode),
            ("Source loan", source.loan_number), ("Successor loan", successor.loan_number),
            ("Borrower", f"{source.borrower.display_name} ({source.borrower.party_code})"),
            ("Source principal settled", cls._money(renewal.source_principal_amount)),
            ("Interest settled", cls._money(renewal.interest_settled)),
            ("Fees settled", cls._money(renewal.fees_settled)),
            ("Principal paid", cls._money(renewal.principal_paid)),
            ("Gross new advance" if cash_evidence else "Top-up disbursed", cls._money(renewal.top_up_amount)),
            ("Successor principal", cls._money(renewal.successor_principal_amount)),
            ("Successor advance interest", cls._money(renewal.successor_advance_interest)),
            ("Successor deducted fees", cls._money(renewal.successor_deducted_fees)),
            ("Net cash handoff", net_cash_handoff),
        )
        successor_items = tuple(successor.collateral_items.select_related("renewed_from").order_by("pk"))
        by_source = {item.renewed_from_id: item for item in successor_items if item.renewed_from_id is not None}
        values = {item["source_item_id"]: item for item in (renewal.valuation_snapshot.get("items") or [])}
        movement = [("Movement", "Source item", "Successor item", "Description", "Value")]
        for item in source.collateral_items.order_by("pk"):
            next_item, value = by_source.get(item.pk), values.get(item.pk) or {}
            movement_label = ("Returned and repledged; recipient " + cash_evidence["recipient"]
                if cash_evidence.get("custody") == "RETURNED_REPLEDGED" else ("Retained" if next_item else "Returned"))
            movement.append((movement_label, str(item.pk),
                             str(next_item.pk) if next_item else "—", item.description,
                             "Not recorded" if paper and value.get("valuation_amount") is None else cls._money(value.get("valuation_amount"))))
        for item in successor_items:
            if item.renewed_from_id is None:
                movement.append(("Additional", "—", str(item.pk), item.description,
                                 cls._money(item.latest_appraised_value)))
        sections = [("Collateral movement", movement)]
        closing = cls._related_or_none(renewal.settlement_event, "principal_closing_lines")
        if closing is not None:
            rows = [("Source item", "Rate", "Before", "Settled", "After")]
            rows.extend((line.collateral_item_id, f"{line.monthly_interest_rate}%",
                         cls._money(line.balance_before), cls._money(line.principal_settled),
                         cls._money(line.balance_after)) for line in closing.order_by("allocation_order"))
            if len(rows) > 1: sections.append(("Source item principal settled", rows))
        opening = cls._related_or_none(renewal.opening_event, "principal_opening_lines")
        if opening is not None:
            rows = [("Successor item", "Predecessor", "Rate", "Principal opened")]
            rows.extend((line.collateral_item_id, line.predecessor_collateral_item_id or "Additional",
                         f"{line.monthly_interest_rate}%", cls._money(line.principal_opened))
                        for line in opening.order_by("allocation_order"))
            if len(rows) > 1: sections.append(("Successor item principal opened", rows))
        return cls._payload("renewal", "Pawn Loan Renewal Agreement",
                            f"pawn_renewal_agreement_{renewal.renewal_number}.pdf", verification, details, sections)

    @classmethod
    def _payload(cls, document_type, title, file_name, verification, details, sections=()):
        unknown_fields = [label for label, _value in details if label not in cls.FIELD_KEYS]
        unknown_sections = [heading for heading, _rows in sections if heading not in cls.SECTION_KEYS]
        if unknown_fields or unknown_sections:
            raise DocumentProjectionError(
                f"Unregistered document bindings: fields={unknown_fields}, sections={unknown_sections}."
            )
        return DocumentPayload(
            schema_version=cls.SCHEMA_VERSION, document_type=document_type, title=title,
            file_name=file_name, verification_id=verification,
            fields=tuple(DocumentField(cls.FIELD_KEYS[label], label, value) for label, value in details),
            sections=tuple(DocumentSection(cls.SECTION_KEYS[heading], heading, tuple(tuple(row) for row in rows)) for heading, rows in sections),
        )

    @staticmethod
    def _identity_rows(loan):
        license_revision = getattr(loan, "license_revision", None)
        license = license_revision or loan.license
        source_type = "LoanLicenseRevision" if license_revision else "LoanLicense"
        return (
            ("Workspace", loan.workspace.name), ("Workspace source ID", f"Workspace:{loan.workspace_id}"),
            ("Regulatory license", f"{license.name} ({license.license_number})"),
            ("License source ID", f"{source_type}:{license.pk}"),
            ("License authority", license.issuing_authority or "—"),
            ("License validity", "Not recorded (legacy reference)" if getattr(license, "is_legacy_reference", False) else f"{license.issued_on} to {license.expires_on}"),
        )

    @staticmethod
    def _verification(loan, source):
        return f"ROKKAD|workspace:{loan.workspace_id}|loan:{loan.pk}|{source}"

    @staticmethod
    def _related_or_none(source, name):
        try:
            return getattr(source, name)
        except (AttributeError, ObjectDoesNotExist):
            return None

    @staticmethod
    def _money(value):
        from .display import display_money
        return "INR " + display_money(value, grouping=True)


__all__ = ["DocumentField", "DocumentPayload", "DocumentProjectionError", "DocumentSection", "PawnLoanDocumentProjectionBuilder"]
