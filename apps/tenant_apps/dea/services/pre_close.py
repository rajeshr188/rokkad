from dataclasses import asdict, dataclass
from decimal import Decimal

from django.db.models import Q

from apps.tenant_apps.dea.models import JournalEntryVoucher, Ledger, Voucher, VoucherStatus


@dataclass
class CheckResult:
    key: str
    label: str
    status: str  # pass | warning | fail | info
    is_fatal: bool
    count: int
    status_text: str

    @property
    def ready(self) -> bool:
        return self.status in {"pass", "info"}

    def to_dict(self) -> dict:
        data = asdict(self)
        data["ready"] = self.ready
        return data


class PreCloseChecklist:
    """Build structured pre-close checks for a period close workflow."""

    def run(self, period, tenant=None) -> list[dict]:
        checks = [
            self._unposted_vouchers_check(period),
            self._interest_accrual_check(period),
            self._unreconciled_bank_items_check(period),
            self._depreciation_posted_check(period),
            self._prepaid_expired_check(period),
            self._balance_sheet_trial_check(period),
        ]
        return [check.to_dict() for check in checks]

    def _unposted_vouchers_check(self, period) -> CheckResult:
        draft_count = Voucher.objects.filter(
            journal_entries__period=period,
            status=VoucherStatus.DRAFT,
        ).distinct().count()
        if draft_count:
            return CheckResult(
                key="unposted_vouchers",
                label="Unposted vouchers",
                status="fail",
                is_fatal=True,
                count=draft_count,
                status_text=f"{draft_count} draft voucher(s) remain",
            )
        return CheckResult(
            key="unposted_vouchers",
            label="Unposted vouchers",
            status="pass",
            is_fatal=True,
            count=0,
            status_text="Ready",
        )

    def _interest_accrual_check(self, period) -> CheckResult:
        try:
            from apps.tenant_apps.girvi.models.loan_refactored import GivenLoan
        except ImportError:
            return CheckResult(
                key="interest_accrual",
                label="Interest accrual catch-up",
                status="info",
                is_fatal=False,
                count=0,
                status_text="Girvi app not installed; check skipped",
            )

        unreleased_loans = GivenLoan.objects.filter(release__isnull=True).count()
        if unreleased_loans:
            return CheckResult(
                key="interest_accrual",
                label="Interest accrual catch-up",
                status="warning",
                is_fatal=False,
                count=unreleased_loans,
                status_text=(
                    f"{unreleased_loans} active loan(s) require catch-up before close"
                ),
            )
        return CheckResult(
            key="interest_accrual",
            label="Interest accrual catch-up",
            status="pass",
            is_fatal=False,
            count=0,
            status_text="No active unreleased loans pending catch-up",
        )

    def _unreconciled_bank_items_check(self, period) -> CheckResult:
        return CheckResult(
            key="unreconciled_bank_items",
            label="Unreconciled bank items",
            status="info",
            is_fatal=False,
            count=0,
            status_text="Bank reconciliation checks will be enabled in Phase 2.4",
        )

    def _depreciation_posted_check(self, period) -> CheckResult:
        period_entries = period.journal_entries.count()
        if period_entries == 0:
            return CheckResult(
                key="depreciation_posted",
                label="Depreciation posted",
                status="info",
                is_fatal=False,
                count=0,
                status_text="No period activity yet; depreciation check not required",
            )

        count = JournalEntryVoucher.objects.filter(
            reference=f"PERIOD:{period.pk}",
            memo="PRE_CLOSE:DEPRECIATION",
        ).count()
        if count:
            return CheckResult(
                key="depreciation_posted",
                label="Depreciation posted",
                status="pass",
                is_fatal=False,
                count=count,
                status_text="Depreciation adjustment recorded",
            )
        return CheckResult(
            key="depreciation_posted",
            label="Depreciation posted",
            status="warning",
            is_fatal=False,
            count=0,
            status_text="Review depreciation journals before close",
        )

    def _prepaid_expired_check(self, period) -> CheckResult:
        period_entries = period.journal_entries.count()
        if period_entries == 0:
            return CheckResult(
                key="prepaid_expired",
                label="Prepaid expiry schedule",
                status="info",
                is_fatal=False,
                count=0,
                status_text="No period activity yet; prepaid check not required",
            )

        count = JournalEntryVoucher.objects.filter(
            reference=f"PERIOD:{period.pk}",
            memo__in=["PRE_CLOSE:PREPAID_EXPENSE", "PRE_CLOSE:ACCRUAL"],
        ).count()
        if count:
            return CheckResult(
                key="prepaid_expired",
                label="Prepaid expiry schedule",
                status="pass",
                is_fatal=False,
                count=count,
                status_text="Prepaid/accrual adjustments recorded",
            )
        return CheckResult(
            key="prepaid_expired",
            label="Prepaid expiry schedule",
            status="warning",
            is_fatal=False,
            count=0,
            status_text="Review prepaid and accrual schedules before close",
        )

    def _balance_sheet_trial_check(self, period) -> CheckResult:
        asset_total = Decimal("0.00")
        liability_total = Decimal("0.00")
        equity_total = Decimal("0.00")

        for ledger in Ledger.objects.select_related("AccountType").all():
            balance = ledger.calculate_balance("INR")
            account_type = (ledger.AccountType.AccountType or "").strip().lower()
            amount = Decimal(str(balance.amount))

            if account_type == "asset":
                asset_total += amount
            elif account_type == "liability":
                liability_total += amount
            elif account_type == "equity":
                equity_total += amount

        delta = asset_total - (liability_total + equity_total)
        if abs(delta) <= Decimal("0.01"):
            return CheckResult(
                key="balance_sheet_trial",
                label="Balance sheet trial (A = L + E)",
                status="pass",
                is_fatal=True,
                count=0,
                status_text="Balanced within 0.01 tolerance",
            )

        return CheckResult(
            key="balance_sheet_trial",
            label="Balance sheet trial (A = L + E)",
            status="fail",
            is_fatal=True,
            count=1,
            status_text=f"Out of balance by {delta}",
        )