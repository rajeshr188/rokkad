"""Frozen row contract for loan-opening-export/1; no model metadata dependencies.

Wire names and nullable values belong to this version. Model refactors must adapt
the exporter/writers, never reinterpret an existing archive.
"""
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from uuid import UUID

from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from .history_contract import HistoryError

PROFILE = "loan-opening-export/1"
MAX_RECORDS = 10000
MANIFEST_FIELDS = {'financial_history_from', 'coverage', 'as_of', 'sha256', 'restore_supported', 'history_before_cutover', 'reference_scope', 'exclusions', 'profile'}
EXTRA_FIELDS = {'interest_conceded', 'recorded_balance', 'collection_preview', 'source_verifications'}

# field name: (wire type, nullable). Source references are positive integers.
# JSON sections retain their versioned nested evidence; semantic validation follows.
ROW_FIELDS = {
    'loan': {
        'id': ('reference', False),
        'workspace_id': ('reference', False),
        'license_id': ('reference', False),
        'license_revision_id': ('reference', True),
        'series_id': ('reference', False),
        'borrower_id': ('reference', False),
        'product_version_id': ('reference', False),
        'loan_number': ('text', False),
        'state': ('text', False),
        'principal_amount': ('decimal', False),
        'monthly_interest_rate': ('decimal', False),
        'loan_date': ('date', False),
        'tenure_months': ('integer', False),
        'created_at': ('timestamp', False),
        'updated_at': ('timestamp', False),
        'created_by_id': ('reference', True),
        'updated_by_id': ('reference', True),
    },
    'origin': {
        'id': ('reference', False),
        'public_id': ('uuid', False),
        'source_namespace': ('uuid', False),
        'source_id': ('text', False),
        'source_sha256': ('text', False),
        'document': ('json', False),
        'references': ('json', False),
        'imported_by_id': ('reference', False),
        'imported_at': ('timestamp', False),
    },
    'policy': {
        'id': ('reference', False),
        'policy_version': ('integer', False),
        'interest_method': ('text', False),
        'partial_month_method': ('text', False),
        'partial_month_cutoff_days': ('integer', False),
        'partial_month_lower_fraction': ('decimal', False),
        'capitalization_interval_periods': ('integer', False),
        'valuation_method': ('text', False),
        'maximum_ltv_ratio': ('decimal', False),
        'rounding_method': ('text', False),
        'currency_quantum': ('decimal', False),
        'created_at': ('timestamp', False),
    },
    'items': {
        'id': ('reference', False),
        'public_id': ('uuid', False),
        'description': ('text', False),
        'metal': ('text', False),
        'gross_weight': ('decimal', True),
        'net_weight': ('decimal', False),
        'purity_percentage': ('decimal', False),
        'latest_appraised_value': ('decimal', True),
        'allocated_principal': ('decimal', True),
        'monthly_interest_rate': ('decimal', True),
        'custody_state': ('text', False),
        'created_at': ('timestamp', False),
        'updated_at': ('timestamp', False),
    },
    'events': {
        'id': ('reference', False),
        'event_kind': ('text', False),
        'effective_date': ('date', False),
        'payload': ('json', False),
        'payload_fingerprint': ('text', False),
        'idempotency_key': ('text', False),
        'reversal_of_id': ('reference', True),
        'created_by_id': ('reference', True),
        'created_at': ('timestamp', False),
    },
    'accruals': {
        'id': ('reference', False),
        'period_number': ('integer', False),
        'period_start': ('date', False),
        'period_end': ('date', False),
        'period_fraction': ('decimal', False),
        'calculation_base': ('decimal', False),
        'unrounded_interest': ('decimal', False),
        'recognized_interest': ('decimal', False),
        'loan_event_id': ('reference', True),
        'finalized_by_id': ('reference', True),
        'finalized_at': ('timestamp', False),
    },
    'accrual_lines': {
        'id': ('reference', False),
        'accrual_id': ('reference', False),
        'collateral_item_id': ('reference', False),
        'principal_base': ('decimal', False),
        'monthly_interest_rate': ('decimal', False),
        'period_fraction': ('decimal', False),
        'unrounded_interest': ('decimal', False),
        'calculated_interest': ('decimal', False),
        'advance_interest_applied': ('decimal', False),
        'recognized_interest': ('decimal', False),
    },
    'releases': {
        'id': ('reference', False),
        'release_number': ('text', False),
        'request_key': ('text', False),
        'effective_date': ('date', False),
        'is_full_release': ('boolean', False),
        'settlement_amount': ('decimal', False),
        'principal_amount': ('decimal', False),
        'interest_amount': ('decimal', False),
        'fee_amount': ('decimal', False),
        'valuation_snapshot': ('json', False),
        'loan_event_id': ('reference', False),
        'catch_up_accrual_id': ('reference', True),
        'created_by_id': ('reference', True),
        'created_at': ('timestamp', False),
    },
    'release_items': {
        'id': ('reference', False),
        'release_id': ('reference', False),
        'collateral_item_id': ('reference', False),
        'valuation_snapshot': ('json', False),
        'returned_at': ('timestamp', False),
    },
    'release_reversals': {
        'id': ('reference', False),
        'release_id': ('reference', False),
        'loan_event_id': ('reference', False),
        'catch_up_reversal_event_id': ('reference', True),
        'reason': ('text', False),
        'created_by_id': ('reference', True),
        'created_at': ('timestamp', False),
    },
    'closing_lines': {
        'id': ('reference', False),
        'loan_event_id': ('reference', False),
        'collateral_item_id': ('reference', False),
        'allocation_order': ('integer', False),
        'monthly_interest_rate': ('decimal', False),
        'balance_before': ('decimal', False),
        'principal_settled': ('decimal', False),
        'balance_after': ('decimal', False),
    },
    'custody_events': {
        'id': ('reference', False),
        'collateral_item_id': ('reference', False),
        'release_id': ('reference', True),
        'release_reversal_id': ('reference', True),
        'from_state': ('text', False),
        'to_state': ('text', False),
        'effective_date': ('date', False),
        'actor_id': ('reference', True),
        'created_at': ('timestamp', False),
    },
    'schedules': {
        'id': ('reference', False),
        'source_event_id': ('reference', False),
        'version': ('integer', False),
        'contract_version': ('text', False),
        'fingerprint': ('text', False),
        'disbursed_on': ('date', False),
        'maturity_date': ('date', False),
        'principal': ('decimal', False),
        'contractual_interest': ('decimal', False),
        'rounding_adjustment': ('decimal', False),
        'supersedes_id': ('reference', True),
        'created_at': ('timestamp', False),
        'created_by_id': ('reference', True),
    },
    'obligations': {
        'id': ('reference', False),
        'schedule_version_id': ('reference', False),
        'sequence': ('integer', False),
        'due_date': ('date', False),
        'principal_due': ('decimal', False),
        'interest_due': ('decimal', False),
        'opening_principal': ('decimal', False),
        'closing_principal': ('decimal', False),
        'created_at': ('timestamp', False),
    },
    'schedule_changes': {
        'id': ('reference', False),
        'schedule_version_id': ('reference', False),
        'source_event_id': ('reference', False),
        'kind': ('text', False),
        'effective_date': ('date', False),
        'reason': ('text', False),
        'reversal_of_id': ('reference', True),
        'created_at': ('timestamp', False),
        'created_by_id': ('reference', True),
    },
    'allocations': {
        'id': ('reference', False),
        'source_event_id': ('reference', False),
        'obligation_id': ('reference', False),
        'component': ('text', False),
        'amount': ('decimal', False),
        'allocation_order': ('integer', False),
        'reversal_of_id': ('reference', True),
        'created_at': ('timestamp', False),
        'created_by_id': ('reference', True),
    },
    'appraisals': {
        'id': ('reference', False),
        'collateral_item_id': ('reference', False),
        'version': ('integer', False),
        'effective_at': ('timestamp', False),
        'appraised_value': ('decimal', False),
        'status': ('text', False),
        'method': ('text', False),
        'evidence_reference': ('text', False),
        'review_notes': ('text', False),
        'valuation_context': ('json', False),
        'supersedes_id': ('reference', True),
        'created_at': ('timestamp', False),
        'created_by_id': ('reference', True),
    },
    'change_log': {
        'id': ('reference', False),
        'event_kind': ('text', False),
        'from_state': ('text', False),
        'to_state': ('text', False),
        'reason': ('text', False),
        'metadata': ('json', False),
        'actor_id': ('reference', True),
        'created_at': ('timestamp', False),
    },
}

# Retain the existing public field inventory for callers of opening_export.FIELDS.
FIELDS = {kind: " ".join(fields) for kind, fields in ROW_FIELDS.items()}

# Version 1 remains frozen. Version 2 adds the actual per-item payment evidence.
PAYMENT_PROFILE = "loan-opening-export/2"
ROW_FIELDS_V2 = {**ROW_FIELDS, "repayment_lines": {
    "id": ("reference", False), "loan_event_id": ("reference", False),
    "collateral_item_id": ("reference", False), "allocation_order": ("integer", False),
    "monthly_interest_rate": ("decimal", False), "balance_before": ("decimal", False),
    "principal_applied": ("decimal", False), "balance_after": ("decimal", False),
}}
FIELDS_V2 = {kind: " ".join(fields) for kind, fields in ROW_FIELDS_V2.items()}


def _decode_row(kind, row, *, profile=PROFILE):
    """Decode v1 values; financial and graph admission remain the writer's job.

    Preserve v1's existing date/UUID spellings and decimal precision. In particular,
    this does not apply today's model validators, defaults, choices or nullability.
    """
    if profile not in {PROFILE, PAYMENT_PROFILE}:
        raise HistoryError("Unsupported opening row profile.")
    fields = (ROW_FIELDS_V2 if profile == PAYMENT_PROFILE else ROW_FIELDS)[kind]
    if type(row) is not dict or set(row) != set(fields):
        raise HistoryError("Unexpected opening evidence fields: " + kind)
    result = {}
    for name, (wire_type, nullable) in fields.items():
        value = row[name]
        if value is None:
            if not nullable:
                raise HistoryError("Required source value is missing: " + name)
            result[name] = None
            continue
        if wire_type == "reference":
            if type(value) is not int or value <= 0:
                raise HistoryError("Invalid source reference: " + name)
        elif wire_type in {"text", "integer", "boolean"}:
            expected = {"text": str, "integer": int, "boolean": bool}[wire_type]
            if type(value) is not expected:
                raise HistoryError("Invalid source value type: " + name)
        elif wire_type == "decimal":
            if type(value) is not str:
                raise HistoryError("Financial evidence must use finite decimal strings.")
            value = Decimal(value)
            if not value.is_finite():
                raise HistoryError("Financial evidence must use finite decimal strings.")
        elif wire_type == "date":
            value = parse_date(value)
            if value is None:
                raise HistoryError("Invalid source date: " + name)
        elif wire_type == "timestamp":
            value = parse_datetime(value)
            if value is None or not timezone.is_aware(value) or value > timezone.now():
                raise HistoryError("Source timestamps must be aware and not in the future.")
        elif wire_type == "uuid":
            # Older v1 decoding also accepted UUID hex spellings and integer values.
            value = UUID(int=value) if isinstance(value, int) else UUID(hex=value)
        elif wire_type != "json":
            raise HistoryError("Unsupported opening wire type: " + wire_type)
        result[name] = value
    result["pk"] = result["id"]
    return SimpleNamespace(**result)


def decode_row(kind, row, *, profile=PROFILE):
    try:
        return _decode_row(kind, row, profile=profile)
    except HistoryError:
        raise
    except (ValueError, TypeError, AttributeError, InvalidOperation, OverflowError) as exc:
        raise HistoryError("Invalid opening evidence value: " + str(exc)) from exc
