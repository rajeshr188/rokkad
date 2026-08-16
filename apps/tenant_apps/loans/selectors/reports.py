"""Canonical PawnLoan operational reports and integrity findings."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist

from apps.tenant_apps.loans.domain import (
    CollateralCustodyState,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.models import LoanLicense, PawnLoan, current_tenant_workspace_id
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.selectors.balances import (
    PawnLoanBalanceSelectorError,
    calculate_pawn_loan_balance,
)


ZERO = Decimal("0")


@dataclass(frozen=True)
class PawnLoanPortfolioRow:
    loan: object
    balance: object | None
    balance_error: str
    status: str


@dataclass(frozen=True)
class PawnLoanReconciliationIssue:
    code: str
    severity: str
    message: str
    loan: object
    event: object | None = None
    collateral_item: object | None = None
    action: str = "Review the loan and its source records."


@dataclass(frozen=True)
class PawnLoanEventReportRow:
    event: object
    activity: str
    amount: object
    principal: Decimal
    interest: Decimal
    fees: Decimal
    correction_status: str
    correction_event_id: int | None


@dataclass(frozen=True)
class PawnLoanReportBundle:
    as_of_date: date
    portfolio: tuple[PawnLoanPortfolioRow, ...]
    accruals: tuple[object, ...]
    repayments: tuple[object, ...]
    releases: tuple[object, ...]
    renewals: tuple[object, ...]
    custody_items: tuple[object, ...]
    issues: tuple[PawnLoanReconciliationIssue, ...]
    license_expiry: tuple[object, ...] = ()

    @property
    def active_count(self):
        return sum(row.loan.state == PawnLoanState.ACTIVE.value for row in self.portfolio)

    @property
    def overdue_count(self):
        return sum(bool(row.balance and row.balance.is_overdue) for row in self.portfolio)

    @property
    def total_principal_outstanding(self):
        return sum(
            (row.balance.principal_outstanding for row in self.portfolio if row.balance),
            ZERO,
        )

    @property
    def total_due(self):
        return sum((row.balance.total_due for row in self.portfolio if row.balance), ZERO)

    @property
    def active_loans(self):
        return tuple(row for row in self.portfolio if row.loan.state == PawnLoanState.ACTIVE.value)

    @property
    def interest_due(self):
        return tuple(
            row for row in self.portfolio
            if row.balance and row.balance.interest_outstanding > ZERO
        )

    @property
    def overdue_loans(self):
        return tuple(row for row in self.portfolio if row.balance and row.balance.is_overdue)

    @property
    def daily_disbursals(self):
        return tuple(
            event for event in self._events(TransactionKind.DISBURSAL.value)
            if event.effective_date == self.as_of_date
        )

    @property
    def daily_repayments(self):
        return tuple(event for event in self.repayments if event.effective_date == self.as_of_date)

    @property
    def daily_activity(self):
        rows = []
        for row in self.portfolio:
            for event in row.loan.loan_events.all():
                if event.effective_date != self.as_of_date:
                    continue
                original_kind = (event.payload.get("reversal") or {}).get(
                    "original_event_kind"
                )
                if event.event_kind in {
                    TransactionKind.DISBURSAL.value,
                    TransactionKind.REPAYMENT.value,
                } or (
                    event.event_kind == TransactionKind.REVERSAL.value
                    and original_kind in {
                        TransactionKind.DISBURSAL.value,
                        TransactionKind.REPAYMENT.value,
                    }
                ):
                    rows.append(_event_report_row(event, as_of_date=self.as_of_date))
        return tuple(sorted(rows, key=lambda row: row.event.pk))

    @property
    def daily_releases(self):
        return tuple(row for row in self.releases if row.effective_date == self.as_of_date)

    @property
    def daily_renewals(self):
        return tuple(row for row in self.renewals if row.renewal_date == self.as_of_date)

    @property
    def storage_inventory(self):
        return tuple(
            item for item in self.custody_items
            if item.custody_state == CollateralCustodyState.IN_VAULT.value
        )

    def _events(self, event_kind):
        return tuple(
            event
            for row in self.portfolio
            for event in row.loan.loan_events.all()
            if event.event_kind == event_kind
        )


@dataclass(frozen=True)
class LoanLicenseExpiryRow:
    license: object
    days_remaining: int
    status: str


@dataclass(frozen=True)
class PawnPartyStatement:
    party: object
    as_of_date: date
    loans: tuple[PawnLoanPortfolioRow, ...]
    transactions: tuple[object, ...]

    @property
    def total_principal_outstanding(self):
        return sum((row.balance.principal_outstanding for row in self.loans if row.balance), ZERO)

    @property
    def total_due(self):
        return sum((row.balance.total_due for row in self.loans if row.balance), ZERO)

    @property
    def transaction_rows(self):
        return tuple(
            _event_report_row(event, as_of_date=self.as_of_date)
            for event in self.transactions
        )


def get_pawn_loan_reports(*, as_of_date: date) -> PawnLoanReportBundle:
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("PawnLoan reports require an active tenant schema.")
    loans = tuple(
        PawnLoan.objects.filter(workspace_id=workspace_id)
        .select_related("borrower", "license", "series", "policy_snapshot")
        .prefetch_related(
            "collateral_items__custody_history",
            "collateral_items__current_storage_location",
            "collateral_items__release_items__release__reversal",
            "loan_events__reversed_by_event",
            "loan_events__principal_closing_lines__collateral_item",
            "loan_events__principal_opening_lines__collateral_item",
            "interest_accruals",
            "releases__items",
            "renewal_as_source__successor_loan",
        )
        .order_by("loan_number")
    )
    license_rows = tuple(
        LoanLicenseExpiryRow(
            license=license,
            days_remaining=(license.expires_on - as_of_date).days,
            status=(
                "EXPIRED" if license.expires_on < as_of_date
                else "EXPIRING" if (license.expires_on - as_of_date).days <= 30
                else "CURRENT"
            ),
        )
        for license in LoanLicense.objects.filter(workspace_id=workspace_id).order_by("expires_on", "license_number")
    )
    return build_pawn_loan_reports(
        loans,
        as_of_date=as_of_date,
        license_expiry=license_rows,
    )


def build_pawn_loan_reports(loans, *, as_of_date, license_expiry=()):
    portfolio = []
    accruals = []
    repayments = []
    releases = []
    renewals = []
    custody_items = []
    issues = []
    for loan in loans:
        events = tuple(loan.loan_events.all())
        collateral = tuple(loan.collateral_items.all())
        balance = None
        balance_error = ""
        try:
            balance = calculate_pawn_loan_balance(
                loan,
                events=events,
                collateral_items=collateral,
                policy_snapshot=_optional_policy(loan),
                as_of_date=as_of_date,
            )
        except (PawnLoanBalanceSelectorError, ValueError) as exc:
            balance_error = str(exc)
            issues.append(_issue("BALANCE_DERIVATION_ERROR", loan, balance_error))
        portfolio.append(
            PawnLoanPortfolioRow(
                loan=loan,
                balance=balance,
                balance_error=balance_error,
                status=_portfolio_status(loan, balance),
            )
        )
        accruals.extend(loan.interest_accruals.all())
        repayments.extend(
            event for event in events if event.event_kind == TransactionKind.REPAYMENT.value
        )
        releases.extend(loan.releases.all())
        renewal = _optional_related(loan, "renewal_as_source")
        if renewal is not None:
            renewals.append(renewal)
        custody_items.extend(collateral)
        issues.extend(_loan_issues(loan, events, collateral, balance))
    return PawnLoanReportBundle(
        as_of_date=as_of_date,
        portfolio=tuple(portfolio),
        accruals=tuple(accruals),
        repayments=tuple(repayments),
        releases=tuple(releases),
        renewals=tuple(renewals),
        custody_items=tuple(custody_items),
        issues=tuple(issues),
        license_expiry=tuple(license_expiry),
    )


def get_pawn_party_statement(*, party_id: int, as_of_date: date) -> PawnPartyStatement:
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("Party statements require an active tenant schema.")
    party = Party.objects.get(pk=party_id)
    loans = tuple(
        PawnLoan.objects.filter(workspace_id=workspace_id, borrower=party)
        .select_related("borrower", "license", "series", "policy_snapshot")
        .prefetch_related(
            "collateral_items__custody_history",
            "collateral_items__current_storage_location",
            "collateral_items__release_items__release__reversal",
            "loan_events__reversed_by_event",
            "loan_events__principal_closing_lines__collateral_item",
            "loan_events__principal_opening_lines__collateral_item",
            "interest_accruals", "releases__items", "renewal_as_source__successor_loan",
        )
        .order_by("loan_number")
    )
    report = build_pawn_loan_reports(
        loans,
        as_of_date=as_of_date,
    )
    transactions = tuple(sorted(
        (
            event
            for row in report.portfolio
            for event in row.loan.loan_events.all()
            if event.effective_date <= as_of_date
        ),
        key=lambda event: (event.effective_date, event.pk),
    ))
    return PawnPartyStatement(party, as_of_date, report.portfolio, transactions)


def _loan_issues(loan, events, collateral, balance):
    issues = []
    if loan.state in {PawnLoanState.ACTIVE.value, PawnLoanState.CLOSED.value} and not any(
        event.event_kind
        in {
            TransactionKind.DISBURSAL.value,
            TransactionKind.RENEWAL_OPENING.value,
        }
        for event in events
    ):
        issues.append(
            _issue(
                "MISSING_DISBURSAL_EVENT",
                loan,
                "Active or closed loan has no disbursal source event.",
                action="Review lifecycle history before further servicing.",
            )
        )
    seen_intents = set()
    for event in events:
        intent = (event.event_kind, event.payload_fingerprint)
        if intent in seen_intents:
            issues.append(
                _issue(
                    "DUPLICATE_EVENT_INTENT",
                    loan,
                    "More than one source event has the same kind and economic payload.",
                    event=event,
                    action="Reverse the later duplicate in strict event order.",
                )
            )
        seen_intents.add(intent)
    issues.extend(_custody_issues(loan, collateral))
    issues.extend(_principal_evidence_issues(loan, events, collateral))
    renewal_completed = bool(collateral) and all(
        item.custody_state
        in {
            CollateralCustodyState.RENEWAL_TRANSFERRED.value,
            CollateralCustodyState.WITH_CUSTOMER.value,
        }
        for item in collateral
    )
    closed_reconciled = bool(
        balance
        and (
            balance.closure_ready
            or (balance.financially_settled and renewal_completed)
        )
    )
    if loan.state == PawnLoanState.CLOSED.value and not closed_reconciled:
        issues.append(
            _issue(
                "CLOSED_LOAN_NOT_RECONCILED",
                loan,
                "Closed loan does not have zero balance and completed release or renewal custody.",
                action="Review releases, custody history, and event reversals.",
            )
        )
    return issues


def _custody_issues(loan, collateral):
    issues = []
    for item in collateral:
        allowed_pre_active_custody = {CollateralCustodyState.IN_VAULT.value}
        if loan.state == PawnLoanState.CANCELLED.value:
            allowed_pre_active_custody.add(
                CollateralCustodyState.RENEWAL_REVERSED.value
            )
        if loan.state in {
            PawnLoanState.DRAFT.value,
            PawnLoanState.APPROVED.value,
            PawnLoanState.CANCELLED.value,
        } and item.custody_state not in allowed_pre_active_custody:
            issues.append(_custody_issue(loan, item, "Pre-disbursal or cancelled loan has collateral outside the vault."))
        if loan.state == PawnLoanState.CLOSED.value and item.custody_state not in {
            CollateralCustodyState.WITH_CUSTOMER.value,
            CollateralCustodyState.RENEWAL_TRANSFERRED.value,
        }:
            issues.append(_custody_issue(loan, item, "Closed loan still has collateral outside customer custody."))
        history = tuple(item.custody_history.all())
        if history and history[-1].to_state != item.custody_state:
            issues.append(_custody_issue(loan, item, "Current custody does not match the latest immutable custody event."))
        returned_by_renewal = any(
            getattr(event, "renewal_id", None) is not None for event in history
        )
        if (
            item.custody_state == CollateralCustodyState.WITH_CUSTOMER.value
            and not item.release_items.exists()
            and not returned_by_renewal
        ):
            issues.append(_custody_issue(loan, item, "Customer-held collateral has no release document item."))
    return issues


def _principal_evidence_issues(loan, events, collateral):
    itemized = tuple(
        item for item in collateral if getattr(item, "allocated_principal", None) is not None
    )
    if not itemized:
        return []
    expected_ids = {item.pk for item in itemized}
    issues = []
    for event in events:
        if event.event_kind in {
            TransactionKind.RELEASE_RECEIPT.value,
            TransactionKind.RENEWAL_SETTLEMENT.value,
        }:
            if (
                event.event_kind == TransactionKind.RELEASE_RECEIPT.value
                and (event.payload.get("release") or {}).get("is_full_release")
                is False
            ):
                continue
            lines = _related_rows(event, "principal_closing_lines")
            expected = _original_principal(event)
            if not lines:
                issues.append(
                    _principal_issue(
                        loan,
                        event,
                        "MISSING_ITEM_PRINCIPAL_EVIDENCE",
                        "Itemized settlement has no immutable principal-closing lines.",
                    )
                )
            elif (
                {line.collateral_item_id for line in lines} != expected_ids
                or sum((line.principal_settled for line in lines), ZERO) != expected
                or any(line.balance_after != ZERO for line in lines)
            ):
                issues.append(
                    _principal_issue(
                        loan,
                        event,
                        "ITEM_PRINCIPAL_EVIDENCE_MISMATCH",
                        "Principal-closing lines do not reconcile to the itemized settlement.",
                    )
                )
        elif event.event_kind == TransactionKind.RENEWAL_OPENING.value:
            lines = _related_rows(event, "principal_opening_lines")
            expected = _original_principal(event)
            item_by_id = {item.pk: item for item in itemized}
            if not lines:
                issues.append(
                    _principal_issue(
                        loan,
                        event,
                        "MISSING_ITEM_PRINCIPAL_EVIDENCE",
                        "Itemized renewal opening has no immutable principal-opening lines.",
                    )
                )
            elif (
                {line.collateral_item_id for line in lines} != expected_ids
                or sum((line.principal_opened for line in lines), ZERO) != expected
                or any(
                    line.principal_opened
                    != item_by_id[line.collateral_item_id].allocated_principal
                    or line.monthly_interest_rate
                    != item_by_id[line.collateral_item_id].monthly_interest_rate
                    or line.predecessor_collateral_item_id
                    != getattr(item_by_id[line.collateral_item_id], "renewed_from_id", None)
                    for line in lines
                )
            ):
                issues.append(
                    _principal_issue(
                        loan,
                        event,
                        "ITEM_PRINCIPAL_EVIDENCE_MISMATCH",
                        "Principal-opening lines do not reconcile to successor collateral.",
                    )
                )
    return issues


def _original_principal(event):
    values = event.payload.get("values") or {}
    principal = Decimal(str(values.get("principal", "0")))
    capitalized = Decimal(
        str(values.get("capitalized_interest_principal", "0"))
    )
    return Decimal(
        str(values.get("original_principal", principal - capitalized))
    )


def _principal_issue(loan, event, code, message):
    return _issue(
        code,
        loan,
        message,
        event=event,
        action="Escalate for immutable item-principal evidence review.",
    )


def _related_rows(instance, name):
    relation = getattr(instance, name, None)
    return tuple(relation.all()) if relation is not None else ()


def _optional_related(instance, name):
    try:
        return getattr(instance, name)
    except (AttributeError, ObjectDoesNotExist):
        return None


def _custody_issue(loan, item, message):
    return _issue(
        "IMPOSSIBLE_CUSTODY",
        loan,
        message,
        collateral_item=item,
        action="Review release and custody history; correct only through reversal.",
    )


def _event_amount(event):
    values = event.payload.get("values") or {}
    kind = event.event_kind
    if kind == TransactionKind.REVERSAL.value:
        kind = (event.payload.get("reversal") or {}).get("original_event_kind")
    if kind == TransactionKind.DISBURSAL.value:
        keys = ("principal",)
    elif kind in {TransactionKind.REPAYMENT.value, TransactionKind.RELEASE_RECEIPT.value}:
        keys = ("principal", "interest", "fees")
    elif kind == TransactionKind.RENEWAL_SETTLEMENT.value:
        renewal = event.payload.get("renewal") or {}
        source_control = Decimal(
            str(renewal.get("source_control_principal", "0"))
        )
        successor_control = Decimal(
            str(renewal.get("successor_control_principal", "0"))
        )
        return abs(source_control - successor_control) + Decimal(
            str(values.get("interest", "0"))
        ) + Decimal(str(values.get("fees", "0"))) + Decimal(
            str(renewal.get("successor_advance_interest", "0"))
        ) + Decimal(str(renewal.get("successor_deducted_fees", "0")))
    elif kind == TransactionKind.RENEWAL_OPENING.value:
        return ZERO
    else:
        keys = ("interest",)
    return sum((Decimal(str(values.get(key, "0"))) for key in keys), ZERO)


def _portfolio_status(loan, balance):
    if loan.state != PawnLoanState.ACTIVE.value or not balance:
        return loan.state
    if balance.is_overdue:
        return "OVERDUE"
    if balance.closure_ready:
        return "CLOSURE_READY"
    return "ACTIVE"


def _event_report_row(event, *, as_of_date=None):
    reversal = event.payload.get("reversal") or {}
    values = event.payload.get("values") or {}
    sign = Decimal("-1") if event.event_kind == TransactionKind.REVERSAL.value else Decimal("1")
    if event.event_kind == TransactionKind.REVERSAL.value:
        original_kind = reversal.get("original_event_kind", "EVENT")
        activity = f"Reversal of {str(original_kind).replace('_', ' ').title()}"
        correction_status = "COMPENSATION"
        correction_event_id = event.reversal_of_id
        amount = -_report_event_amount(event, original_kind=original_kind)
    else:
        display = getattr(event, "get_event_kind_display", None)
        activity = (
            display()
            if display
            else str(event.event_kind).replace("_", " ").title()
        )
        try:
            reversed_by = event.reversed_by_event
        except (AttributeError, ObjectDoesNotExist):
            reversed_by = None
        if (
            reversed_by is not None
            and as_of_date is not None
            and reversed_by.effective_date > as_of_date
        ):
            reversed_by = None
        correction_status = "REVERSED" if reversed_by else "CURRENT"
        correction_event_id = reversed_by.pk if reversed_by else None
        amount = _report_event_amount(event)
    return PawnLoanEventReportRow(
        event=event,
        activity=activity,
        amount=amount,
        principal=sign * Decimal(str(values.get("principal", "0"))),
        interest=sign * Decimal(str(values.get("interest", "0"))),
        fees=sign * Decimal(str(values.get("fees", "0"))),
        correction_status=correction_status,
        correction_event_id=correction_event_id,
    )


def _report_event_amount(event, *, original_kind=None):
    kind = original_kind or event.event_kind
    values = event.payload.get("values") or {}
    if kind == TransactionKind.DISBURSAL.value:
        return Decimal(str(values.get("principal", "0")))
    if kind == TransactionKind.REPAYMENT.value:
        received = (event.payload.get("repayment") or {}).get("amount_received")
        if received is not None:
            return Decimal(str(received))
        return sum(
            (Decimal(str(values.get(key, "0"))) for key in ("principal", "interest", "fees")),
            ZERO,
        )
    return ZERO


def _optional_policy(loan):
    try:
        return loan.policy_snapshot
    except (AttributeError, ObjectDoesNotExist):
        return None


def _issue(code, loan, message, *, severity="ERROR", **kwargs):
    return PawnLoanReconciliationIssue(
        code=code,
        severity=severity,
        message=message,
        loan=loan,
        **kwargs,
    )


__all__ = [
    "PawnLoanPortfolioRow",
    "PawnLoanReconciliationIssue",
    "PawnLoanEventReportRow",
    "PawnLoanReportBundle",
    "LoanLicenseExpiryRow",
    "PawnPartyStatement",
    "build_pawn_loan_reports",
    "get_pawn_loan_reports",
    "get_pawn_party_statement",
]
