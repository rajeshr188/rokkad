"""One signed worksheet, with ordinary immutable reviews for each loan."""
from django.core import signing
from django.db import transaction
from .transaction_reviews import _loan, preview_transaction_review, confirm_transaction_review
from .recorded_history import _digest

SALT = "loans.batch-transaction-review.v1"


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
        rows.append(dict(review, number=loan.loan_number))
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
