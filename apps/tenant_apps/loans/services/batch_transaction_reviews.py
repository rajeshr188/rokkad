"""One signed worksheet, with ordinary immutable reviews for each loan."""
from django.core import signing
from django.db import transaction
from apps.tenant_apps.loans import models as m
from .action_access import require_workspace_action
from .transaction_reviews import _loan, preview_transaction_review, confirm_transaction_review
from .recorded_history import _digest

SALT = "loans.batch-transaction-review.v1"
COHORT_SALT = 'loans.cohort-transaction-review.v1'


def _loans(loan_ids, actor):
    if not isinstance(loan_ids, (list, tuple)) or not 1 <= len(loan_ids) <= 50 or any(type(pk) is not int or pk <= 0 for pk in loan_ids):
        raise ValueError("Select between one and fifty loan records.")
    if len(set(loan_ids)) != len(loan_ids):
        raise ValueError("Select each loan once.")
    return [_loan(pk, actor) for pk in sorted(loan_ids)]


def _binding(loans, actor, data):
    facts = dict(data, through_date=data["through_date"].isoformat())
    return dict(actor=actor.pk, workspace=loans[0].workspace_id, loans=[loan.pk for loan in loans], facts=facts)


@transaction.atomic
def preview_batch_transaction_review(loan_ids, *, actor, **data):
    loans = _loans(loan_ids, actor)
    binding = _binding(loans, actor, data)
    rows, tokens = [], []
    for loan in loans:
        review, token = preview_transaction_review(loan.pk, actor=actor, **data)
        history_from = next((row['effective_date'] for row in review['events']
            if row['event_kind']=='MIGRATION_OPENING'),loan.loan_date.isoformat() if loan.loan_date else None)
        rows.append(dict(review, number=loan.loan_number,history_from=history_from))
        tokens.append(token)
    token = signing.dumps(dict(binding=binding, tokens=tokens), salt=SALT, compress=True)
    return rows, token


@transaction.atomic
def confirm_batch_transaction_review(loan_ids, *, actor, review_token, acknowledged, **data):
    loans = _loans(loan_ids, actor)
    if acknowledged is not True:
        raise ValueError("Confirm that you checked every selected loan against the source records.")
    try:
        signed = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except signing.BadSignature as exc:
        raise ValueError("Batch review expired or changed; preview again.") from exc
    if _digest(signed.get("binding")) != _digest(_binding(loans, actor, data)) or len(signed.get("tokens", [])) != len(loans):
        raise ValueError("Batch selection or review facts changed; preview again.")
    return [confirm_transaction_review(loan.pk, actor=actor, **data,
        review_token=token, acknowledged=True) for loan, token in zip(loans, signed["tokens"], strict=True)]


def _cohort(workspace, actor, series, source_namespace, after_loan_id):
    from uuid import UUID
    if m.current_tenant_workspace_id() != workspace.pk or series.workspace_id != workspace.pk:
        raise ValueError('Select the cohort series in the active Workspace.')
    require_workspace_action(workspace,actor,'data.edit')
    if type(after_loan_id) is not int or after_loan_id < 0:
        raise ValueError('Use a nonnegative cohort cursor.')
    namespace = str(UUID(str(source_namespace)))
    rows = list(m.PawnLoan.objects.filter(workspace=workspace,series=series,state='ACTIVE',
        historical_import__source_namespace=namespace,pk__gt=after_loan_id).select_related('historical_import').order_by('pk')[:51])
    selected = rows[:50]
    if not selected:
        raise ValueError('No further active loans match this source cohort and series.')
    binding = dict(workspace=workspace.pk, actor=actor.pk, series=series.pk, namespace=namespace,
        after=after_loan_id, members=[dict(loan=row.pk, import_id=row.historical_import.pk,
            source_sha256=row.historical_import.source_sha256) for row in selected])
    return selected, binding, len(rows)>50


def _cohort_facts(binding, data):
    values=dict(data)
    values['source_reference'] = f"Source cohort {binding['namespace']}, series {binding['series']}: {data['source_reference']}"
    if len(values['source_reference'])>500:
        raise ValueError('Shorten the supporting source reference to leave room for cohort identity.')
    return values


@transaction.atomic
def preview_cohort_transaction_review(*, workspace, actor, series, source_namespace, after_loan_id=0, **data):
    loans,binding,more = _cohort(workspace,actor,series,source_namespace,after_loan_id)
    values = _cohort_facts(binding,data)
    eligible, exceptions = [], []
    for loan in loans:
        try:
            preview_transaction_review(loan.pk,actor=actor,**values)
        except ValueError as exc:
            exceptions.append(dict(loan=loan.pk,number=loan.loan_number,reason=str(exc)))
        else:
            eligible.append(loan.pk)
    rows, batch_token = preview_batch_transaction_review(eligible,actor=actor,**values) if eligible else ([], '')
    review = dict(rows=rows,exceptions=exceptions,more=more,next_cursor=loans[-1].pk,
        selected=len(loans),eligible=len(eligible))
    token=signing.dumps(dict(binding=binding,data=_digest(dict(values,through_date=values['through_date'].isoformat())),
        eligible=eligible,batch_token=batch_token,review=review),salt=COHORT_SALT,compress=True)
    return review,token


@transaction.atomic
def confirm_cohort_transaction_review(*, workspace, actor, series, source_namespace, review_token,
        acknowledged, after_loan_id=0, **data):
    loans,binding,_ = _cohort(workspace,actor,series,source_namespace,after_loan_id)
    values=_cohort_facts(binding,data)
    try:
        signed=signing.loads(review_token or '',salt=COHORT_SALT,max_age=3600)
    except signing.BadSignature as exc:
        raise ValueError('Cohort review expired or changed. Preview again.') from exc
    if (signed.get('binding')!=binding or signed.get('data')!=_digest(dict(values,
            through_date=values['through_date'].isoformat()))):
        raise ValueError('Cohort membership or review facts changed. Preview again.')
    if acknowledged is not True:
        raise ValueError('Confirm the source records for each eligible loan; exceptions remain unresolved.')
    if not signed['eligible']:
        raise ValueError('No eligible loans in this batch. Resolve the listed exceptions.')
    result=confirm_batch_transaction_review(signed['eligible'],actor=actor,
        review_token=signed['batch_token'],acknowledged=True,**values)
    return result,signed['review']
