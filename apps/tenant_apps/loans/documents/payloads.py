"""Immutable projections used by every PawnLoan document renderer.

Projection builders are the only document layer allowed to read loan models.
Renderers receive scalar rows and never calculate loan or accounting facts.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist

from apps.tenant_apps.loans.domain import PawnLoanState, TransactionKind


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

    @property
    def details(self):
        """Fixed-renderer compatibility view over the typed field registry."""
        return tuple((field.label, field.value) for field in self.fields)


class PawnLoanDocumentProjectionBuilder:
    SCHEMA_VERSION = 1
    FIELD_KEYS = {
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
        "Effective date": "event.effective_date", "Amount received": "repayment.amount_received",
        "Fees": "amounts.fees", "Overdue interest": "amounts.overdue_interest",
        "Current interest": "amounts.current_interest", "Total interest": "amounts.total_interest",
        "Accounting delivery": "accounting.delivery", "DEA voucher / journal": "accounting.references",
        "Release source ID": "release.source_id", "Release number": "release.number",
        "Accounting event ID": "accounting.event_source_id", "Release type": "release.type",
        "Principal settled": "amounts.principal_settled", "Interest settled": "amounts.interest_settled",
        "Fees settled": "amounts.fees_settled", "Total settlement": "amounts.total_settlement",
        "Auction source ID": "auction.source_id", "Auction number": "auction.number",
        "Notice date": "auction.notice_date", "Scheduled auction date": "auction.scheduled_date",
        "Notice delivery job": "auction.notice_delivery_job", "Buyer": "auction.buyer",
        "Buyer reference": "auction.buyer_reference", "Principal recovered": "amounts.principal_recovered",
        "Interest recovered": "amounts.interest_recovered", "Fees recovered": "amounts.fees_recovered",
        "Total recovery": "amounts.total_recovery", "Renewal source ID": "renewal.source_id",
        "Renewal number": "renewal.number", "Renewal date": "renewal.date", "Mode": "renewal.mode",
        "Source loan": "renewal.source_loan", "Successor loan": "renewal.successor_loan",
        "Source principal settled": "renewal.source_principal_settled",
        "Principal paid": "renewal.principal_paid", "Top-up disbursed": "renewal.top_up_disbursed",
        "Successor principal": "renewal.successor_principal", "Settlement accounting": "renewal.settlement_accounting",
        "Successor opening": "renewal.successor_opening",
        "Successor advance interest": "renewal.successor_advance_interest",
        "Successor deducted fees": "renewal.successor_deducted_fees",
        "Net cash handoff": "renewal.net_cash_handoff",
        "Product": "contract.product", "Product version": "contract.product_version",
        "Repayment structure": "contract.repayment_structure",
        "Schedule fingerprint": "contract.schedule_fingerprint",
        "Maturity date": "contract.maturity_date", "Contractual interest": "contract.interest",
        "Total contractual repayment": "contract.total_repayment",
    }
    SECTION_KEYS = {
        "Collateral": "collateral.items", "Collateral principal allocation": "repayment.principal_allocations",
        "Collateral returned": "release.collateral_returned", "Item principal settled": "release.principal_settled",
        "Collateral disposed": "auction.collateral_disposed", "Collateral movement": "renewal.collateral_movement",
        "Source item principal settled": "renewal.source_principal_settled",
        "Successor item principal opened": "renewal.successor_principal_opened",
        "Repayment schedule": "contract.repayment_schedule",
    }

    @classmethod
    def loan_ticket(cls, loan):
        if loan.state == PawnLoanState.DRAFT.value:
            raise DocumentProjectionError(
                "Loan ticket is unavailable while the loan is an editable draft."
            )
        approval = loan.approval_snapshots.order_by("-version").first()
        if approval is None:
            raise DocumentProjectionError(
                "Loan ticket is available only after the loan has an approval snapshot."
            )
        source = approval.payload
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
        rows = [("Item ID", "Description", "Metal", "Net weight", "Purity", "Appraisal", "Custody")]
        rows.extend(
            (
                str(item["item_id"]), item["description"], item["metal"].title(),
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
    def repayment_receipt(cls, event):
        if event.event_kind != TransactionKind.REPAYMENT.value:
            raise DocumentProjectionError("A repayment receipt requires a repayment event.")
        loan = event.loan
        values = event.payload.get("values") or {}
        repayment = event.payload.get("repayment") or {}
        reversed_by = cls._related_or_none(event, "reversed_by_event")
        verification = cls._verification(loan, f"repayment:{event.pk}:{event.payload_fingerprint}")
        outbox = event.outbox
        details = cls._identity_rows(loan) + (
            ("Document", "Repayment receipt"),
            ("Repayment source ID", f"PawnLoanAccountingEvent:{event.pk}"),
            ("Document status", f"Reversed by event {reversed_by.pk}" if reversed_by else "Recorded"),
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
            ("Accounting delivery", outbox.get_status_display()),
            ("DEA voucher / journal", f"{outbox.dea_voucher_id or '—'} / {outbox.dea_journal_entry_id or '—'}"),
        )
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
        loan, event = release.loan, release.accounting_event
        outbox = cls._related_or_none(event, "outbox")
        reversal = cls._related_or_none(release, "reversal")
        verification = cls._verification(
            loan, f"release:{release.pk}:{release.release_number}:{event.payload_fingerprint}"
        )
        details = cls._identity_rows(loan) + (
            ("Document", "Release memo / Form H equivalent"),
            ("Release source ID", f"PawnLoanRelease:{release.pk}"),
            ("Document status", f"Reversed by release reversal {reversal.pk}" if reversal else "Completed"),
            ("Release number", release.release_number),
            ("Official loan number", loan.loan_number),
            ("Accounting event ID", f"PawnLoanAccountingEvent:{event.pk}"),
            ("Event fingerprint", event.payload_fingerprint),
            ("Effective date", release.effective_date),
            ("Release type", "Full" if release.is_full_release else "Partial"),
            ("Borrower", f"{loan.borrower.display_name} ({loan.borrower.party_code})"),
            ("Principal settled", cls._money(release.principal_amount)),
            ("Interest settled", cls._money(release.interest_amount)),
            ("Fees settled", cls._money(release.fee_amount)),
            ("Total settlement", cls._money(release.settlement_amount)),
            ("Accounting delivery", outbox.get_status_display() if outbox else "Not required"),
            ("DEA voucher / journal", f"{outbox.dea_voucher_id or 'Not available'} / {outbox.dea_journal_entry_id or 'Not available'}" if outbox else "Not applicable"),
        )
        item_rows = [("Item ID", "Description", "Value at release", "Returned at")]
        for item in release.items.all():
            snapshot = item.valuation_snapshot or {}
            item_rows.append((str(item.collateral_item_id), item.collateral_item.description,
                              cls._money(snapshot.get("valuation_amount")), str(item.returned_at)))
        sections = [("Collateral returned", item_rows)]
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
            ("Notice delivery job", getattr(auction.notice, "notification_job_id", "Not available")),
        )
        return cls._payload("auction_notice", "Pawn Loan Auction Notice",
                            f"pawn_auction_notice_{auction.auction_number}.pdf", verification, details)

    @classmethod
    def auction_recovery_memo(cls, auction):
        if not auction.accounting_event_id:
            raise DocumentProjectionError("Auction recovery memo is available only after completion.")
        loan, event = auction.loan, auction.accounting_event
        outbox = event.outbox
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
            ("Accounting delivery", outbox.get_status_display()),
            ("DEA voucher / journal", f"{outbox.dea_voucher_id or 'Not available'} / {outbox.dea_journal_entry_id or 'Not available'}"),
        )
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
        source, successor = renewal.source_loan, renewal.successor_loan
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
        details = cls._identity_rows(source) + (
            ("Document", "Pawn loan renewal agreement"),
            ("Renewal source ID", f"PawnLoanRenewal:{renewal.pk}"),
            ("Renewal number", renewal.renewal_number),
            ("Document status", f"Reversed by {reversal.pk}" if reversal else "Completed"),
            ("Renewal date", renewal.renewal_date), ("Mode", renewal.get_mode_display()),
            ("Source loan", source.loan_number), ("Successor loan", successor.loan_number),
            ("Borrower", f"{source.borrower.display_name} ({source.borrower.party_code})"),
            ("Source principal settled", cls._money(renewal.source_principal_amount)),
            ("Interest settled", cls._money(renewal.interest_settled)),
            ("Fees settled", cls._money(renewal.fees_settled)),
            ("Principal paid", cls._money(renewal.principal_paid)),
            ("Top-up disbursed", cls._money(renewal.top_up_amount)),
            ("Successor principal", cls._money(renewal.successor_principal_amount)),
            ("Successor advance interest", cls._money(renewal.successor_advance_interest)),
            ("Successor deducted fees", cls._money(renewal.successor_deducted_fees)),
            ("Net cash handoff", net_cash_handoff),
            ("Settlement accounting", renewal.settlement_event.outbox.get_status_display()),
            ("Successor opening", renewal.opening_event.outbox.get_status_display()),
        )
        successor_items = tuple(successor.collateral_items.select_related("renewed_from").order_by("pk"))
        by_source = {item.renewed_from_id: item for item in successor_items if item.renewed_from_id is not None}
        values = {item["source_item_id"]: item for item in (renewal.valuation_snapshot.get("items") or [])}
        movement = [("Movement", "Source item", "Successor item", "Description", "Value")]
        for item in source.collateral_items.order_by("pk"):
            next_item, value = by_source.get(item.pk), values.get(item.pk) or {}
            movement.append(("Retained" if next_item else "Returned", str(item.pk),
                             str(next_item.pk) if next_item else "—", item.description,
                             cls._money(value.get("valuation_amount"))))
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
            ("License validity", f"{license.issued_on} to {license.expires_on}"),
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
        return f"INR {Decimal(str(value or '0')).quantize(Decimal('0.01'))}"


__all__ = ["DocumentField", "DocumentPayload", "DocumentProjectionError", "DocumentSection", "PawnLoanDocumentProjectionBuilder"]
