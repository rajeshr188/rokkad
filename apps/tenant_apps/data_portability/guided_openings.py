"""Owner-reviewed workbook staging, atomic admission and safe replay."""
from decimal import Decimal
from datetime import date
import hashlib
import re

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError, ObjectDoesNotExist
from django.db import transaction, IntegrityError
from django.utils import timezone

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.party.services.creation import create_party_from_form
from apps.tenant_apps.loans import models as loans
from apps.tenant_apps.loans.services.history_contract import digest
from apps.tenant_apps.loans.services.history_setup import require_history_setup_access, require_history_preparation_access, validate_preparation_mapping
from apps.tenant_apps.loans.services.opening_import import commit_opening_import, PROFILE as OPENING_PROFILE
from apps.tenant_apps.loans.services.closed_position import preview_closed_position, admit_closed_position
from apps.tenant_apps.loans.domain.monthly_contract import RULE as MONTHLY_RULE
from apps.tenant_apps.loans.services.product_catalog import create_product_version_draft, activate_product_version, retire_product_version
from .contracts import party_form, semantic, source_digest
from .models import GuidedOpeningBatch, PartyIdentity, SourceIdentity
from .parsers import parse_source, PortabilityError
from . import opening_register as register
from .position_register import closed_document

SALT = 'guided-outstanding-register-v1'


def get_batch(*, workspace_id, actor, batch_id, lock=False):
    require_history_preparation_access(workspace_id, actor, read_only=not lock)
    query = GuidedOpeningBatch.objects.filter(workspace_id=workspace_id)
    if lock:
        query = query.select_for_update()
    try:
        return query.get(public_id=batch_id)
    except (GuidedOpeningBatch.DoesNotExist, ValueError, ValidationError):
        raise PermissionDenied('This import is unavailable in this Workspace.') from None


@transaction.atomic
def stage(*, workspace_id, actor, source_key, content, filename):
    workspace = require_history_preparation_access(workspace_id, actor)
    Company.all_objects.select_for_update().get(pk=workspace_id)
    if not isinstance(source_key, str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,47}', source_key):
        raise PortabilityError('Use a stable register key of lowercase letters, numbers and hyphens (up to 48 characters).')
    name, kind, headers, rows = parse_source(content, filename)
    profile = next((key for key, columns in register.TEMPLATES.items() if set(headers) == set(columns)), None)
    if kind not in {'xlsx', 'csv'} or profile is None:
        raise PortabilityError('Use a supported active-position or closed-loan template with all its headers. XLSX and CSV are supported; arbitrary loan sheets need mapping first.')
    register.groups(rows)
    register.borrowers(rows)
    sha = hashlib.sha256(content).hexdigest()
    existing = GuidedOpeningBatch.objects.filter(workspace_id=workspace_id, source_key=source_key,
        source_sha256=sha).exclude(state='CANCELLED').first()
    if existing:
        return existing
    if GuidedOpeningBatch.objects.filter(workspace_id=workspace_id, state__in=['STAGED', 'READY']).count() >= 20:
        raise PortabilityError('Finish or cancel an unfinished register import before uploading more (limit 20).')
    batch = GuidedOpeningBatch.objects.create(workspace_id=workspace_id, source_key=source_key,
        source_name=name, source_sha256=sha, created_by=actor,
        document={'profile': profile, 'rows': rows})
    AuditLog.log('DATA_IMPORT', company=workspace, user=actor, content_object=batch,
        description='Staged an outstanding loan register for owner review.', data={'phase': 'GUIDED_STAGE', 'sha256': sha})
    return batch


def _product(workspace_id, actor, grace, profile=register.PROFILE):
    """Reuse catalog commands; only a retired servicing definition is retained."""
    expected = dict(repayment_structure='FLEXIBLE_PARTIAL_PAYMENT', amortisation_method='NONE',
        payment_frequency='FLEXIBLE', minimum_tenor_months=1, maximum_tenor_months=1200,
        operational_grace_days=grace, extra_payment_rule='REDUCE_PRINCIPAL',
        calculation_contract_version=MONTHLY_RULE if profile == register.CHECKPOINT_PROFILE else register.AGGREGATE_RULE,
        available_from=None, available_until=None)
    prefix = 'IMPORT-MONTHLY' if profile == register.CHECKPOINT_PROFILE else 'IMPORT-UPFRONT'
    product, created = loans.LoanProduct.objects.get_or_create(workspace_id=workspace_id, code=f'{prefix}-{grace}',
        defaults={'name': f"Imported {'monthly-checkpoint' if profile == register.CHECKPOINT_PROFILE else 'upfront-interest'} loans ({grace} grace days)", 'created_by': actor, 'updated_by': actor})
    if created:
        version = create_product_version_draft(product.pk, actor=actor, **expected)
        activate_product_version(version.pk, actor=actor)
        return retire_product_version(version.pk, actor=actor)
    version = product.versions.order_by('-version').first()
    if not version or version.status != 'RETIRED' or any(getattr(version, k) != v for k, v in expected.items()):
        raise PortabilityError('The import servicing product differs from the supported profile. Review Loan setup before importing.')
    return version


def _bind_borrower(batch, ref, values, choice, workspace_id, actor):
    record = {'name': values['name'], 'kind': 'INDIVIDUAL', 'status': 'ACTIVE',
              'credit_hold': False, 'primary_phone': values['phone'] or None}
    system = register.source_system(workspace_id, batch.source_key)
    source = SourceIdentity.objects.select_related('identity__party').filter(workspace_id=workspace_id,
        source_system=system, external_id=ref).first()
    if source:
        party = Party.objects.select_for_update().get(pk=source.identity.party_id, workspace_id=workspace_id)
        if not _eligible_customer(batch, party):
            raise PortabilityError('The previously matched customer is not active or eligible for this profile. Review their profile before importing.')
        if choice != party.party_code or source.accepted_digest != source_digest(record):
            raise PortabilityError('This borrower reference is already bound to a customer. Keep that match; changed source details need review.')
        return party, {'mode': 'bound', 'party_id': party.pk, 'fingerprint': digest(semantic(party))}
    if choice == 'NEW':
        # Explicit selection; no name-based merging. Same-name creation is disclosed.
        form = party_form(record)
        if not form.is_valid():
            raise PortabilityError('New customer details are invalid: ' + '; '.join(f'{k}: {", ".join(v)}' for k, v in form.errors.items()))
        party = create_party_from_form(form=form, workspace_id=workspace_id, actor=actor)
        binding = {'mode': 'new', 'party_id': None, 'fingerprint': digest(semantic(party))}
    else:
        try:
            party = Party.objects.select_for_update().get(workspace_id=workspace_id, party_code=choice)
        except Party.DoesNotExist:
            raise PortabilityError('Choose NEW or an existing customer code from this Workspace.') from None
        if not _eligible_customer(batch, party):
            raise PortabilityError('The selected customer is not active or eligible for this profile. Review their profile before importing.')
        binding = {'mode': 'existing', 'party_id': party.pk, 'fingerprint': digest(semantic(party))}
    identity, _ = PartyIdentity.objects.get_or_create(workspace_id=workspace_id, party=party)
    SourceIdentity.objects.create(workspace_id=workspace_id, source_system=system, external_id=ref,
        identity=identity, accepted_digest=source_digest(record), local_digest=digest(semantic(party)))
    return party, binding


def _eligible_customer(batch, party):
    return party.status != 'ARCHIVED' if batch.document['profile'] == register.CLOSED_PROFILE else party.status == 'ACTIVE'


def _prepared_settings(mapping, workspace_id, profile=register.PROFILE):
    if not isinstance(mapping, dict) or not isinstance(mapping.get('settings'), dict) or not isinstance(mapping.get('borrowers'), dict):
        raise PortabilityError('Review destination settings and customer matches before importing.')
    settings, choices = mapping['settings'], mapping['borrowers']
    closed = profile == register.CLOSED_PROFILE
    fields = {'series_id', 'cutover', 'reference', 'rule_confirmed'} if closed else {'revision_id', 'series_id', 'cutover', 'grace_days', 'reference', 'rule_confirmed'}
    if set(settings) != fields:
        raise PortabilityError('Supply the complete destination and handover settings.')
    if any(type(settings[k]) is not int or settings[k] <= 0 for k in (('series_id',) if closed else ('revision_id', 'series_id'))) or (not closed and type(settings['grace_days']) is not int):
        raise PortabilityError('Select a valid licence, series and original grace period.')
    if not isinstance(settings['reference'], str) or not 1 <= len(settings['reference'].strip()) <= 180:
        raise PortabilityError('Supply a source / reconciliation reference (up to 180 characters).')
    if settings.get('rule_confirmed') is not True:
        raise PortabilityError('Confirm the supported source position and rules before importing.')
    if not closed and not 0 <= settings['grace_days'] <= 30:
        raise PortabilityError('Grace days must be between 0 and 30.')
    from datetime import date
    try:
        cutoff = date.fromisoformat(settings['cutover'])
    except (ValueError, TypeError):
        raise PortabilityError('Supply a valid handover date.') from None
    if cutoff >= timezone.localdate():
        raise PortabilityError('Use a completed handover date before today. Rokkad servicing starts on the following day.')
    if closed:
        if not loans.LoanSeries.objects.filter(workspace_id=workspace_id, pk=settings['series_id']).exists():
            raise PortabilityError('Choose a destination series from this Workspace.')
    else:
        revision = validate_preparation_mapping(workspace_id, revision_id=settings['revision_id'], series_id=settings['series_id'])
        settings = {**settings, 'license_number': revision.license_number, 'legacy_reference': revision.kind == 'LEGACY_REFERENCE'}
    return settings, choices


@transaction.atomic
def prepare(*, workspace_id, actor, batch_id, mapping):
    require_history_preparation_access(workspace_id, actor)
    Company.all_objects.select_for_update().get(pk=workspace_id)
    batch = get_batch(workspace_id=workspace_id, actor=actor, batch_id=batch_id, lock=True)
    if batch.state not in {'STAGED', 'READY'}:
        raise PortabilityError('Only unfinished imports can be prepared.')
    settings, choices = _prepared_settings(mapping, workspace_id, batch.document['profile'])
    customers = register.borrowers(batch.document['rows'])
    if set(choices) != set(customers):
        raise PortabilityError('Match every source borrower before preparing the loans.')
    for choice in choices.values():
        query = Party.objects.filter(workspace_id=workspace_id, party_code=choice)
        query = query.exclude(status='ARCHIVED') if batch.document['profile'] == register.CLOSED_PROFILE else query.filter(status='ACTIVE')
        if choice != 'NEW' and not query.exists():
            raise PortabilityError('Choose NEW or an existing active customer in this Workspace.')
    batch.mapping, batch.state, batch.approval_digest = mapping, 'STAGED', ''
    batch.preview = {'profile': 'loan-import-preparation/1', 'prepared_by': actor.pk,
        'financial_admission_reviewed': False, 'source_sha256': batch.source_sha256,
        'loans': len(register.groups(batch.document['rows'])), 'borrowers': len(customers)}
    batch.save(update_fields=['mapping', 'preview', 'state', 'approval_digest'])
    return batch


def _evaluate(batch, mapping, workspace_id, actor):
    """Caller either rolls back every write or commits the complete reviewed graph."""
    profile = batch.document['profile']
    if profile not in register.TEMPLATES:
        raise PortabilityError('Unsupported source register profile.')
    settings, choices = _prepared_settings(mapping, workspace_id, profile)
    product = None if profile == register.CLOSED_PROFILE else _product(workspace_id, actor, settings['grace_days'], profile)
    customers = register.borrowers(batch.document['rows'])
    if set(choices) != set(customers):
        raise PortabilityError('Match every source borrower before reviewing the loans.')
    parties, bindings, issues, rows, results = {}, {}, [], [], []
    for ref, values in customers.items():
        try:
            with transaction.atomic():
                party, binding = _bind_borrower(batch, ref, values, choices[ref], workspace_id, actor)
                parties[ref], bindings[ref] = party, binding
        except (PortabilityError, ValidationError) as exc:
            issues.append({'reference': f'Borrower {ref}', 'message': str(exc)})
        except IntegrityError:
            issues.append({'reference': f'Borrower {ref}', 'message': 'The customer or source match conflicts with existing data. Review this match again.'})
    totals = {key: Decimal('0') for key in ('principal', 'interest', 'fees')}
    for ref, source_rows in register.groups(batch.document['rows']).items():
        first = source_rows[0][1]
        party = parties.get(first['borrower_ref'].strip())
        if party is None:
            continue
        try:
            with transaction.atomic():
                if profile == register.CLOSED_PROFILE:
                    document = closed_document(batch=batch, ref=ref, rows=source_rows, settings=settings, workspace_id=workspace_id)
                    args = dict(workspace_id=workspace_id, actor=actor, document=document, borrower_id=party.pk, series_id=settings['series_id'])
                    summary, token = preview_closed_position(**args)
                    loan, _ = admit_closed_position(**args, review_token=token, confirmed=True)
                    result = loan.historical_import
                    rows.append(dict(reference=ref, number=loan.loan_number, borrower=party.display_name,
                        original_date=date.fromisoformat(document['loan']['original_date']).strftime('%d/%m/%Y') if document['loan']['original_date'] else None,
                        closed_on=document['loan']['closed_on'], items=None, balance=summary['balances'],
                        known_details=document['loan'], missing_original_details=summary['missing_original_details'], state='CLOSED'))
                    results.append(dict(origin_id=result.pk, loan_id=loan.pk, number=loan.loan_number, source_sha256=result.source_sha256))
                    continue
                inputs = register.loan_inputs(batch=batch, ref=ref, rows=source_rows, settings=settings,
                    borrower_id=party.pk, product_id=product.pk, workspace_id=workspace_id)
                document = {'profile': OPENING_PROFILE, **inputs}
                result, summary = commit_opening_import(workspace_id=workspace_id, actor=actor, **inputs,
                    expected_sha256=digest(document), confirmed=True)
                rows.append({'reference': ref, 'number': summary['loan_number'], 'borrower': summary['borrower_name'],
                    'original_date': date.fromisoformat(inputs['review']['terms']['original_date']).strftime('%d/%m/%Y'),
                    'maturity_date': date.fromisoformat(inputs['review']['terms']['maturity_date']).strftime('%d/%m/%Y'),
                    'tenure_months': inputs['setup']['tenure_months'],
                    'collateral': inputs['review']['collateral'], 'items': summary['collateral'],
                    'balance': summary['balance'], 'checkpoint': inputs['review']['continuation'] if profile == register.CHECKPOINT_PROFILE else None,
                    'monthly_interest': str(sum(Decimal(i['remaining_principal'] if profile == register.CHECKPOINT_PROFILE else i['original_principal']) * Decimal(i['monthly_rate']) / 100 for i in inputs['review']['collateral']))})
                for key in totals:
                    totals[key] += Decimal(summary['balance'][key])
                results.append({'origin_id': result.pk, 'loan_id': result.loan_id, 'number': summary['loan_number'], 'source_sha256': result.source_sha256})
        except (ValueError, ValidationError, ObjectDoesNotExist) as exc:
            issues.append({'reference': f'Loan {ref} (rows {", ".join(str(n) for n, _ in source_rows)})', 'message': str(exc)})
        except IntegrityError:
            issues.append({'reference': f'Loan {ref}', 'message': 'A customer, source identity or loan number conflicts with existing data. Refresh the review; nothing in this batch has been imported.'})
    return {'rows': rows, 'issues': issues, 'borrowers': bindings,
        'totals': {k: format(v, 'f') for k, v in totals.items()}, 'loans': len(rows)}, results


def _fingerprint(batch):
    return digest({'source': batch.source_sha256, 'document': batch.document,
                   'mapping': batch.mapping, 'preview': batch.preview})


@transaction.atomic
def preview(*, workspace_id, actor, batch_id, mapping):
    Company.all_objects.select_for_update().get(pk=require_history_setup_access(workspace_id, actor).pk)
    batch = get_batch(workspace_id=workspace_id, actor=actor, batch_id=batch_id, lock=True)
    if batch.state not in {'STAGED', 'READY'}:
        raise PortabilityError('This import is already finished.')
    with transaction.atomic():
        report, _ = _evaluate(batch, mapping, workspace_id, actor)
        transaction.set_rollback(True)
    batch.mapping, batch.preview = mapping, report
    batch.state = 'STAGED' if report['issues'] else 'READY'
    batch.approval_digest = _fingerprint(batch)
    batch.save(update_fields=['mapping', 'preview', 'state', 'approval_digest'])
    return batch, signing.dumps({'workspace': workspace_id, 'actor': actor.pk,
        'batch': str(batch.public_id), 'digest': batch.approval_digest}, salt=SALT) if batch.state == 'READY' else None


@transaction.atomic
def commit(*, workspace_id, actor, batch_id, approval, confirmed=False):
    workspace = require_history_setup_access(workspace_id, actor)
    if confirmed is not True:
        raise PortabilityError('Confirm the handover, balances, customer matches, custody and supported terms before importing.')
    try:
        token = signing.loads(approval, salt=SALT, max_age=3600)
    except signing.BadSignature:
        raise PortabilityError('This approval expired or changed. Review the import again.') from None
    if token.get('workspace') != workspace_id or token.get('actor') != actor.pk or token.get('batch') != str(batch_id):
        raise PermissionDenied('Approval belongs to another user, Workspace or import.')
    Company.all_objects.select_for_update().get(pk=workspace_id)
    batch = get_batch(workspace_id=workspace_id, actor=actor, batch_id=batch_id, lock=True)
    if batch.state not in {'READY', 'COMPLETED'} or token.get('digest') != batch.approval_digest or _fingerprint(batch) != batch.approval_digest:
        raise PortabilityError('The reviewed import changed. Generate a fresh preview.')
    if batch.state == 'COMPLETED':
        return batch
    report, results = _evaluate(batch, batch.mapping, workspace_id, actor)
    if report['issues'] or report != batch.preview:
        raise PortabilityError('The destination or source matches changed after review. Nothing was imported; review again.')
    batch.results, batch.state = results, 'COMPLETED'
    batch.committed_by, batch.committed_at = actor, timezone.now()
    batch.save(update_fields=['results', 'state', 'committed_by', 'committed_at'])
    AuditLog.log('DATA_IMPORT', company=workspace, user=actor, content_object=batch,
        description='Imported a reviewed outstanding register without historical disbursals.',
        data={'phase': 'GUIDED_COMMIT', 'sha256': batch.source_sha256, 'loans': len(results), 'totals': report['totals']})
    return batch


@transaction.atomic
def cancel(*, workspace_id, actor, batch_id, confirmed=False):
    workspace = require_history_setup_access(workspace_id, actor)
    Company.all_objects.select_for_update().get(pk=workspace_id)
    batch = get_batch(workspace_id=workspace_id, actor=actor, batch_id=batch_id, lock=True)
    if confirmed is not True or batch.state == 'COMPLETED':
        raise PortabilityError('Confirm cancellation of an unfinished import. Completed imports are retained.')
    if batch.state == 'CANCELLED':
        return batch
    batch.document, batch.mapping, batch.preview, batch.approval_digest, batch.state = {}, {}, {}, '', 'CANCELLED'
    batch.save(update_fields=['document', 'mapping', 'preview', 'approval_digest', 'state'])
    AuditLog.log('DATA_IMPORT', company=workspace, user=actor, content_object=batch,
        description='Cancelled outstanding-register staging; no loans imported.', data={'phase': 'GUIDED_CANCEL'})
    return batch
