"""Dated release evidence. Reads never approve actions or change source history."""
from collections import Counter
from datetime import date

from django.db.models import Count
from django.utils import timezone

from apps.tenant_apps.loans.models import HistoricalLoanEvidence, PawnLoan, current_tenant_workspace_id
from .continuation import resolve_loan_continuation
from .directory import unadmitted_historical_records
from .evidence_quality import loan_evidence_quality
from apps.tenant_apps.loans.services.servicing_eligibility import servicing_eligibility


def loan_release_inventory(*, as_of_date, summary_only=False):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("Release inventory requires an active Workspace context.")
    if type(as_of_date) is not date or as_of_date > timezone.localdate():
        raise ValueError("Release inventory requires a reporting date no later than today.")
    loans = PawnLoan.objects.filter(workspace_id=workspace_id)
    archives = HistoricalLoanEvidence.objects.filter(workspace_id=workspace_id)
    census = dict(ordinary_states={r["state"]: r["count"] for r in loans.values("state").annotate(count=Count("pk"))},
        archive_snapshots=archives.count(),
        unadmitted_archive_identities=unadmitted_historical_records(workspace_id).count())
    counts, rows = Counter(), []
    selected = loans.filter(state__in=("ACTIVE", "CLOSED")).select_related(
        "policy_snapshot", "product_version", "disbursal_snapshot", "risk_snapshot"
    ).prefetch_related("loan_events", "collateral_items", "transaction_reviews").order_by("pk")
    for loan in selected.iterator(chunk_size=100):
        row = dict(loan_id=loan.pk, number=loan.loan_number, state=loan.state)
        try:
            continuation = resolve_loan_continuation(loan, as_of_date=as_of_date)
        except ValueError as exc:
            row.update(calculation="UNAVAILABLE", blocker=str(exc))
            quality = loan_evidence_quality(loan, as_of_date=as_of_date,
                calculation_status="UNAVAILABLE", calculation_message=str(exc))
        else:
            contract = continuation.contract
            row.update(calculation="SUPPORTED", contract_profile=contract.profile,
                origin_kind=contract.origin_kind, financial_history_from=contract.financial_history_from,
                recorded_due=continuation.recorded_balance.total_due,
                collection_due=continuation.collection_balance.total_due,
                eligible_unposted_interest=(continuation.recognition.additional_interest
                    if continuation.recognition.collection_eligible else None),
                recognition_adapter=continuation.recognition.adapter,
                earlier_financial_history_available=contract.origin_kind != "MIGRATION_OPENING")
            quality = loan_evidence_quality(loan, as_of_date=as_of_date,
                calculation_status="SUPPORTED", financial_history_from=contract.financial_history_from,
                principal_history_basis="VERIFIED_TERMINAL_POSITION" if contract.profile in {"loan-terminal-position/1", "loan-closed-position/1"}
                    else "OPENING_CHECKPOINT" if contract.origin_kind == "MIGRATION_OPENING" else "ORIGINAL_PAYOUT")
        # Calculation, books and valuation are independent. No stored risk refresh.
        row["transactions"] = quality["transactions"]
        row["assessment"] = quality["assessment"]["status"]
        row["valuation"] = quality["valuation"]["status"]
        row["servicing_prerequisites"] = {}
        if loan.state == "ACTIVE" and row["calculation"] == "SUPPORTED":
            for operation in ("REPAYMENT", "FULL_RELEASE", "RENEWAL", "AUCTION"):
                result = servicing_eligibility(loan, operation=operation, purpose="CURRENT", effective_date=as_of_date)
                row["servicing_prerequisites"][operation] = dict(clear=result.ready,
                    blockers=[b.code for b in result.blockers])
        counts["calculation:" + row["calculation"]] += 1
        counts["contract:" + row.get("contract_profile", "UNAVAILABLE")] += 1
        counts["transactions:" + row["transactions"]["status"]] += 1
        counts["assessment:" + row["assessment"]] += 1
        counts["valuation:" + row["valuation"]] += 1
        if not summary_only:
            rows.append(row)
    return dict(format="loan-release-inventory/1", workspace_id=workspace_id, as_of_date=as_of_date,
        generated_at=timezone.now(), census=census, cohorts=dict(sorted(counts.items())), loans=rows,
        automatic_conversion=False, action_authorization=False, staff_acceptance=False,
        scope="Ordinary active/closed loan calculation and factual prerequisites; draft/approval states and retained archive identities are counted separately. Commands retain authorization, chronology, allocation, valuation, custody and legal checks.")
