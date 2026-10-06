"""Explicit outstanding-register/1 adapter. No database writes or guessed terms."""
from collections import OrderedDict
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from uuid import UUID, uuid5
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta

from apps.tenant_apps.loans.domain import resolve_policy, LicensePolicyOverrides, ValuationMethod
from apps.tenant_apps.loans.services.history_contract import digest
from apps.tenant_apps.loans.services.legacy_interest import AGGREGATE_RULE, aggregate_collection_interest
from apps.tenant_apps.loans.services.opening_validation import COLLECTION_PROFILE
from .parsers import PortabilityError

PROFILE = 'outstanding-register/1'
MAX_LOANS, MAX_ROWS = 20, 200
COLUMNS = (
    'loan_ref', 'loan_number', 'borrower_ref', 'borrower_name', 'borrower_phone',
    'original_date', 'tenure_months', 'item_ref', 'description', 'metal', 'quantity',
    'gross_weight_g', 'net_weight_g', 'purity_percent', 'original_principal',
    'outstanding_principal', 'monthly_rate_percent', 'unpaid_interest', 'unpaid_fees',
    'first_month_paid', 'in_vault',
)
LOAN_FIELDS = ('loan_number', 'borrower_ref', 'borrower_name', 'borrower_phone',
               'original_date', 'tenure_months', 'unpaid_interest', 'unpaid_fees', 'first_month_paid')


def source_namespace(workspace_id, source_key):
    return uuid5(UUID('ff7763c3-7775-4ab7-ab1b-23bed176c2c0'), f'{workspace_id}:{source_key}')


def source_system(workspace_id, source_key):
    return f'legacy:{source_namespace(workspace_id, source_key).hex}:register'


def groups(rows):
    result = OrderedDict()
    for number, row in rows:
        ref = row.get('loan_ref', '').strip()
        if not ref or len(ref) > 64:
            raise PortabilityError(f'Row {number}: supply a stable loan_ref of at most 64 characters.')
        result.setdefault(ref, []).append((number, row))
    if not 1 <= len(result) <= MAX_LOANS or len(rows) > MAX_ROWS:
        raise PortabilityError('Use at most 20 loans and 200 collateral rows per upload. Split a larger register into batches.')
    return result


def borrowers(rows):
    result = OrderedDict()
    for number, row in rows:
        ref, name = row.get('borrower_ref', '').strip(), row.get('borrower_name', '').strip()
        if not ref or len(ref) > 64 or not name or len(name) > 255:
            raise PortabilityError(f'Row {number}: supply borrower_ref (up to 64 characters) and borrower_name.')
        value = {'name': name, 'phone': row.get('borrower_phone', '').strip()}
        if ref in result and result[ref] != value:
            raise PortabilityError(f'Row {number}: this borrower_ref has inconsistent name or phone details.')
        result[ref] = value
    return result


def amount(value, label, *, positive=False, places=2, maximum=Decimal('999999999999')):
    try:
        # Ordinary decimal text only; no formula/scientific or locale guessing.
        if not isinstance(value, str) or not value or any(c not in '0123456789.' for c in value):
            raise ValueError()
        result = Decimal(value)
        if not result.is_finite() or result < 0 or result > maximum or (positive and not result):
            raise ValueError()
        if result != result.quantize(Decimal(1).scaleb(-places)):
            raise ValueError()
        return format(result, 'f')
    except (ValueError, InvalidOperation):
        raise PortabilityError(f'{label}: supply a valid {"positive" if positive else "nonnegative"} number with at most {places} decimals. Blank is unknown, not zero.') from None


def integer(value, label, maximum):
    if not isinstance(value, str) or not value.isascii() or not value.isdigit() or not 1 <= int(value) <= maximum:
        raise PortabilityError(f'{label}: supply a whole number from 1 to {maximum}.')
    return int(value)


def loan_inputs(*, batch, ref, rows, settings, borrower_id, product_id, workspace_id):
    """Translate reviewed rows to the unchanged Loans v2 opening contract."""
    first = rows[0][1]
    if any(any(row.get(key, '').strip() != first.get(key, '').strip() for key in LOAN_FIELDS) for _, row in rows):
        raise PortabilityError('Repeat identical loan and borrower details on every collateral row for this loan.')
    if len(rows) > 20:
        raise PortabilityError('A loan supports at most 20 distinct collateral items.')
    if first['first_month_paid'].strip().lower() != 'yes':
        raise PortabilityError('This profile requires evidence that the first month was paid upfront. Other interest rules need a separate review.')
    try:
        original = datetime.strptime(first['original_date'].strip(), '%d/%m/%Y').date()
    except ValueError:
        raise PortabilityError('Original date: use text in DD/MM/YYYY format, for example 25/09/2026.') from None
    tenure = integer(first['tenure_months'].strip(), 'Original tenure in months', 1200)
    try:
        maturity = original + relativedelta(months=tenure)
    except (ValueError, OverflowError):
        raise PortabilityError('Original date and tenure exceed the supported calendar.') from None
    cutoff = datetime.strptime(settings['cutover'], '%Y-%m-%d').date()
    if original > cutoff:
        raise PortabilityError('The original loan date cannot be after the handover date.')
    items, seen = [], set()
    for number, row in rows:
        item_id = row['item_ref'].strip()
        if not item_id or len(item_id) > 64 or item_id in seen:
            raise PortabilityError(f'Row {number}: item_ref must be present and unique within this loan (up to 64 characters).')
        seen.add(item_id)
        if row['in_vault'].strip().lower() != 'yes':
            raise PortabilityError(f'Row {number}: confirm this collateral is in your vault. Released/repledged items need a separate review.')
        original_p = amount(row['original_principal'].strip(), f'Row {number} original principal', positive=True)
        remaining = amount(row['outstanding_principal'].strip(), f'Row {number} outstanding principal', positive=True)
        if Decimal(original_p) != Decimal(remaining):
            raise PortabilityError(f'Row {number}: principal has changed. This first profile cannot admit a reduced-principal opening.')
        items.append({'id': item_id, 'description': row['description'].strip(),
            'quantity': integer(row['quantity'].strip(), f'Row {number} quantity', 10000),
            'metal': row['metal'].strip().upper(),
            'gross_weight': amount(row['gross_weight_g'].strip(), 'Gross weight', positive=True, places=3) if row['gross_weight_g'].strip() else None,
            'net_weight': amount(row['net_weight_g'].strip(), 'Net weight', positive=True, places=3),
            'purity': amount(row['purity_percent'].strip(), 'Purity', positive=True, places=2, maximum=Decimal('100')),
            'original_principal': original_p, 'remaining_principal': remaining,
            'monthly_rate': amount(row['monthly_rate_percent'].strip(), 'Monthly rate', places=6, maximum=Decimal('100')),
            'weight_reference': settings['reference'], 'custody_reference': settings['reference'],
            'valuation': {'status': 'UNVERIFIED', 'source_amount': None, 'source_date': None, 'evidence_reference': 'No dated appraisal supplied in outstanding-register/1'}})
    principal = sum(Decimal(i['remaining_principal']) for i in items)
    unpaid = amount(first['unpaid_interest'].strip(), 'Unpaid interest')
    fees = amount(first['unpaid_fees'].strip(), 'Unpaid fees')
    monthly = sum(Decimal(i['original_principal']) * Decimal(i['monthly_rate']) / 100 for i in items)
    checkpoint = aggregate_collection_interest(original, cutoff, monthly)
    if Decimal(unpaid) > Decimal(checkpoint['additional_interest']):
        raise PortabilityError('Unpaid interest exceeds the supported charge through handover. Check the date, rate, paid coverage or choose an assisted review.')
    namespace = str(source_namespace(workspace_id, batch.source_key))
    review = {
        'profile': COLLECTION_PROFILE,
        'source': {'namespace': namespace, 'schema': 'register', 'loan_id': ref,
            'number': first['loan_number'].strip(), 'loan_timestamp': datetime.combine(original, time(), ZoneInfo('Asia/Kolkata')).isoformat(),
            'borrower_id': first['borrower_ref'].strip(), 'item_ids': [i['id'] for i in items],
            'archive_sha256': batch.source_sha256, 'selection_sha256': digest(batch.document),
            'loan_sha256': digest(rows), 'state': 'UNRELEASED', 'excluded': False, 'errors': []},
        'cutover': {'date': cutoff.isoformat(), 'timezone': 'Asia/Kolkata', 'evidence_reference': settings['reference']},
        'mapping': {'workspace_id': workspace_id, 'borrower_id': borrower_id,
            'borrower_source_system': source_system(workspace_id, batch.source_key),
            'borrower_external_id': first['borrower_ref'].strip(), 'licence_revision_id': settings['revision_id'],
            'series_id': settings['series_id'], 'product_version_id': product_id, 'evidence_reference': settings['reference']},
        'balances': {'principal': str(principal), 'interest': unpaid, 'fees': fees, 'evidence_reference': settings['reference']},
        'terms': {'original_date': original.isoformat(), 'maturity_date': maturity.isoformat(),
            'billing_anchor': original.isoformat(), 'grace_days': settings['grace_days'], 'rule_id': AGGREGATE_RULE,
            'period_rule': 'ORIGINAL_ANNIVERSARY', 'interest_basis': 'ORIGINAL_PRINCIPAL', 'partial_rule': 'INCLUSIVE_UPFRONT',
            'partial_cutoff_days': None, 'partial_lower_fraction': None, 'rounding_scope': 'AGGREGATE',
            'rounding_mode': 'HALF_EVEN', 'interest_quantum': '1', 'evidence_reference': settings['reference']},
        'collateral': items,
        'obligations': [{'id': 'maturity', 'due': maturity.isoformat(), 'principal': str(principal),
            'interest': unpaid, 'recognized_interest': unpaid, 'evidence_reference': settings['reference']}],
        'continuation': {'covered_through': cutoff.isoformat(), 'additional_months': checkpoint['additional_months'],
            'recognized_interest': checkpoint['additional_interest'], 'recognized_unpaid_interest': unpaid,
            'first_month_paid': True, 'evidence_reference': settings['reference']},
        'review_reference': settings['reference'],
    }
    policy = resolve_policy(license_overrides=LicensePolicyOverrides(valuation_method=ValuationMethod.LATEST_APPRAISAL)).to_disbursal_snapshot().to_dict()
    # This register explicitly retains the original review/2 calculation rule.
    # Changing today's defaults must not relabel that older evidence contract.
    policy['policy_version'] = 1
    setup = {'tenure_months': tenure, 'source_license_number': settings['license_number'],
             'local_loan_number': first['loan_number'].strip(), 'policy': policy}
    if settings.get('legacy_reference'):
        setup['legacy_license_evidence'] = settings['reference']
    return {'review': review, 'setup': setup}
