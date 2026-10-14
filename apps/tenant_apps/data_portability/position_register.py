"""Explicit essential-position adapters; prior financial transactions are unknown."""
from datetime import datetime, date, timedelta
from decimal import Decimal

from apps.tenant_apps.loans.domain.monthly_contract import RULE, charge_count, period_dates, item_monthly_interest
from apps.tenant_apps.loans.services.opening_checkpoint import PROFILE as CHECKPOINT_REVIEW
from apps.tenant_apps.loans.services.closed_position_contract import PROFILE as CLOSED_POSITION, validate_document
from . import opening_register as register
from .parsers import PortabilityError


def apply_checkpoint(review, rows, first, policy):
    quantum = first['interest_quantum'].strip()
    if quantum not in {'1', '0.01'}:
        raise PortabilityError('interest_quantum: enter 1 for whole rupees or 0.01 for paise, according to the source agreement.')
    if Decimal(register.amount(first['future_advance_interest'].strip(), 'Future advance interest')) != 0:
        raise PortabilityError('This register supports current-period advance only. Future advance coverage needs the explicit per-period opening review; do not omit it.')
    original = date.fromisoformat(review['terms']['original_date'])
    cutoff = date.fromisoformat(review['cutover']['date'])
    number = charge_count(original, cutoff) + 1
    start, end = period_dates(original, number)
    bases = [dict(item_id=row['item_ref'].strip(), principal_base=register.amount(
        row['period_principal_base'].strip(), f'Row {n} current-period principal base')) for n, row in rows]
    by_id = {row['item_id']: row['principal_base'] for row in bases}
    expected = sum((item_monthly_interest(by_id[item['id']], item['monthly_rate'], quantum)
                    for item in review['collateral']), Decimal('0'))
    advance = register.amount(first['current_period_advance_interest'].strip(), 'Current-period advance interest')
    reference = review['review_reference']
    review['profile'] = CHECKPOINT_REVIEW
    review['terms'].update(rule_id=RULE, interest_basis='OUTSTANDING_AT_PERIOD_START',
        partial_rule='FULL_MONTH', rounding_scope='PER_ITEM', rounding_mode='HALF_UP', interest_quantum=quantum)
    review['continuation'] = dict(covered_through=cutoff.isoformat(), additional_months=number - 1,
        period_number=number, period_start=start.isoformat(), period_end=end.isoformat(), bases=bases,
        expected_period_interest=str(expected),
        recognized_interest=register.amount(first['recognized_interest'].strip(), 'Cumulative recognized interest'),
        recognized_unpaid_interest=review['balances']['interest'],
        current_period_recognized_interest=register.amount(first['current_period_recognized_interest'].strip(), 'Current-period recognized interest'),
        current_period_unpaid_interest=register.amount(first['current_period_unpaid_interest'].strip(), 'Current-period unpaid interest'),
        advance_coverage=[dict(period_number=number, interest=advance, evidence_reference=reference)] if Decimal(advance) else [],
        next_increase_on=(end + timedelta(days=1)).isoformat(), evidence_reference=reference)
    policy.update(policy_version=2, interest_method='SIMPLE', partial_month_method='FULL_MONTH', currency_quantum=quantum)


def optional_day(value, label):
    if not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), '%d/%m/%Y').date().isoformat()
    except ValueError:
        raise PortabilityError(f'{label}: use DD/MM/YYYY date text, or leave blank when unknown.') from None


def closed_document(*, batch, ref, rows, settings, workspace_id):
    if len(rows) != 1:
        raise PortabilityError('Closed registers use exactly one row per loan. Do not repeat its original total as collateral rows.')
    number, row = rows[0]
    for key in ('outstanding_principal', 'unpaid_interest', 'unpaid_fees'):
        if Decimal(register.amount(row[key].strip(), f'Row {number} {key}')) != 0:
            raise PortabilityError('A closed position requires explicitly confirmed zero principal, interest and fees.')
    if row['collateral_returned'].strip().lower() != 'yes':
        raise PortabilityError('Confirm collateral was returned to the borrower. Closed debt alone does not establish returned custody.')
    system = register.source_system(workspace_id, batch.source_key)
    document = dict(profile=CLOSED_POSITION,
        source=dict(namespace=str(register.source_namespace(workspace_id, batch.source_key)), system=system, loan_id=ref),
        loan=dict(number=row['loan_number'].strip(), borrower_reference=dict(system=system, id=row['borrower_ref'].strip()),
            original_date=optional_day(row['original_date'], 'Original date'), closed_on=optional_day(row['closed_on'], 'Closure date'),
            original_principal=register.amount(row['original_principal'].strip(), 'Original principal', positive=True) if row['original_principal'].strip() else None,
            monthly_rate=register.amount(row['monthly_rate_percent'].strip(), 'Monthly rate', places=6, maximum=Decimal('100')) if row['monthly_rate_percent'].strip() else None,
            tenure_months=register.integer(row['tenure_months'].strip(), 'Original tenure', 1200) if row['tenure_months'].strip() else None),
        position=dict(state='CLOSED', as_of=settings['cutover'], currency='INR', principal='0', interest='0', fees='0',
            custody='RETURNED_TO_BORROWER', basis='OWNER_CLOSED_POSITION',
            evidence_reference=f"{settings['reference']}; closed-register/1 file {batch.source_sha256}; loan {ref}"),
        earlier_history='UNAVAILABLE', retained_evidence=None)
    return validate_document(document)
