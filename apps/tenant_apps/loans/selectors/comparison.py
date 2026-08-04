"""Deterministic, read-only Girvi/Loans coexistence comparison."""

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal

from apps.tenant_apps.girvi import facade as girvi_facade
from apps.tenant_apps.loans.selectors.coexistence import (
    UnifiedLoanReadRow,
    build_unified_loan_portfolio,
    get_loans_coexistence_rows,
)


ZERO = Decimal("0")


@dataclass(frozen=True)
class LoanComparisonSourceSummary:
    source_system: str
    row_count: int
    active_count: int
    closed_count: int
    pending_count: int
    cancelled_count: int
    original_principal: Decimal
    principal_outstanding: Decimal
    interest_outstanding: Decimal
    total_due: Decimal
    collateral_count: int
    custody_counts: tuple[tuple[str, int], ...]
    release_counts: tuple[tuple[str, int], ...]
    dea_visibility_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class LoanComparisonMismatch:
    category: str
    source_system: str
    metric: str
    expected: object
    actual: object
    source_key: str = ""


@dataclass(frozen=True)
class LoanCoexistenceComparison:
    as_of_date: date
    expected: tuple[LoanComparisonSourceSummary, ...]
    actual: tuple[LoanComparisonSourceSummary, ...]
    mismatches: tuple[LoanComparisonMismatch, ...]

    @property
    def mismatch_count(self):
        return len(self.mismatches)

    @property
    def is_match(self):
        return not self.mismatches

    def as_dict(self):
        return {
            "as_of_date": self.as_of_date.isoformat(),
            "is_match": self.is_match,
            "mismatch_count": self.mismatch_count,
            "expected": [_json_safe(asdict(item)) for item in self.expected],
            "actual": [_json_safe(asdict(item)) for item in self.actual],
            "mismatches": [_json_safe(asdict(item)) for item in self.mismatches],
        }


def get_loan_coexistence_comparison(*, as_of_date: date):
    """Compare source projections with the unified contract without writing data."""
    girvi_source = girvi_facade.get_loan_coexistence_rows(as_of_date=as_of_date)
    adapted_girvi = tuple(
        _adapt_girvi_row(row) for row in girvi_source
    )
    loans_source = get_loans_coexistence_rows(as_of_date=as_of_date)
    portfolio = build_unified_loan_portfolio(
        girvi_rows=adapted_girvi,
        loans_rows=loans_source,
        as_of_date=as_of_date,
    )
    return build_loan_coexistence_comparison(
        expected_rows=girvi_source + loans_source,
        actual_rows=portfolio.rows,
        as_of_date=as_of_date,
    )


def build_loan_coexistence_comparison(*, expected_rows, actual_rows, as_of_date):
    expected_rows = tuple(expected_rows)
    actual_rows = tuple(actual_rows)
    sources = tuple(
        sorted({row.source_system for row in expected_rows + actual_rows})
    )
    expected = tuple(
        _summarize(source, expected_rows) for source in sources
    )
    actual = tuple(_summarize(source, actual_rows) for source in sources)
    mismatches = []
    for expected_summary, actual_summary in zip(expected, actual, strict=True):
        mismatches.extend(_summary_mismatches(expected_summary, actual_summary))
    mismatches.extend(_row_mismatches(expected_rows, actual_rows))
    return LoanCoexistenceComparison(
        as_of_date=as_of_date,
        expected=expected,
        actual=actual,
        mismatches=tuple(mismatches),
    )


def _adapt_girvi_row(row):
    return UnifiedLoanReadRow(
        source_system="GIRVI",
        source_label="Girvi",
        owner_app="girvi",
        **{
            field: getattr(row, field)
            for field in UnifiedLoanReadRow.__dataclass_fields__
            if field not in {"source_system", "source_label", "owner_app"}
        },
    )


def _summarize(source, rows):
    selected = tuple(row for row in rows if row.source_system == source)
    buckets = Counter(row.lifecycle_bucket for row in selected)
    return LoanComparisonSourceSummary(
        source_system=source,
        row_count=len(selected),
        active_count=buckets["ACTIVE"],
        closed_count=buckets["CLOSED"],
        pending_count=buckets["PENDING"],
        cancelled_count=buckets["CANCELLED"],
        original_principal=sum((row.original_principal for row in selected), ZERO),
        principal_outstanding=sum(
            (row.principal_outstanding for row in selected), ZERO
        ),
        interest_outstanding=sum(
            (row.interest_outstanding for row in selected), ZERO
        ),
        total_due=sum((row.total_due for row in selected), ZERO),
        collateral_count=sum(row.collateral_count for row in selected),
        custody_counts=_counter_tuple(row.custody_summary for row in selected),
        release_counts=_counter_tuple(row.release_status for row in selected),
        dea_visibility_counts=_counter_tuple(row.dea_visibility for row in selected),
    )


SUMMARY_CATEGORIES = {
    "row_count": "COUNT",
    "active_count": "LIFECYCLE",
    "closed_count": "LIFECYCLE",
    "pending_count": "LIFECYCLE",
    "cancelled_count": "LIFECYCLE",
    "original_principal": "MONEY",
    "principal_outstanding": "MONEY",
    "interest_outstanding": "MONEY",
    "total_due": "MONEY",
    "collateral_count": "CUSTODY",
    "custody_counts": "CUSTODY",
    "release_counts": "RELEASE",
    "dea_visibility_counts": "DEA_VISIBILITY",
}

ROW_CATEGORIES = {
    "lifecycle_bucket": "LIFECYCLE",
    "original_principal": "MONEY",
    "principal_outstanding": "MONEY",
    "interest_outstanding": "MONEY",
    "total_due": "MONEY",
    "collateral_count": "CUSTODY",
    "custody_summary": "CUSTODY",
    "release_status": "RELEASE",
    "dea_visibility": "DEA_VISIBILITY",
    "financial_data_available": "DEA_VISIBILITY",
}


def _summary_mismatches(expected, actual):
    mismatches = []
    for metric, category in SUMMARY_CATEGORIES.items():
        expected_value = getattr(expected, metric)
        actual_value = getattr(actual, metric)
        if expected_value != actual_value:
            mismatches.append(
                LoanComparisonMismatch(
                    category=category,
                    source_system=expected.source_system,
                    metric=metric,
                    expected=expected_value,
                    actual=actual_value,
                )
            )
    return mismatches


def _row_mismatches(expected_rows, actual_rows):
    expected = {row.source_key: row for row in expected_rows}
    actual = {row.source_key: row for row in actual_rows}
    mismatches = []
    for source_key in sorted(expected.keys() - actual.keys()):
        row = expected[source_key]
        mismatches.append(
            LoanComparisonMismatch(
                "COUNT", row.source_system, "missing_row", source_key, None, source_key
            )
        )
    for source_key in sorted(actual.keys() - expected.keys()):
        row = actual[source_key]
        mismatches.append(
            LoanComparisonMismatch(
                "COUNT", row.source_system, "unexpected_row", None, source_key, source_key
            )
        )
    for source_key in sorted(expected.keys() & actual.keys()):
        expected_row = expected[source_key]
        actual_row = actual[source_key]
        for metric, category in ROW_CATEGORIES.items():
            expected_value = getattr(expected_row, metric)
            actual_value = getattr(actual_row, metric)
            if expected_value != actual_value:
                mismatches.append(
                    LoanComparisonMismatch(
                        category,
                        expected_row.source_system,
                        metric,
                        expected_value,
                        actual_value,
                        source_key,
                    )
                )
    return mismatches


def _counter_tuple(values):
    return tuple(sorted(Counter(values).items()))


def _json_safe(value):
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Decimal):
        return str(value)
    return value


__all__ = [
    "LoanCoexistenceComparison",
    "LoanComparisonMismatch",
    "LoanComparisonSourceSummary",
    "build_loan_coexistence_comparison",
    "get_loan_coexistence_comparison",
]
