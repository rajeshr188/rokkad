"""Source-backed completion of a newer nonfinancial opening projection."""
from django.db import transaction

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.tenant_apps.loans import models as m
from .history_contract import digest
from .action_access import require_setup_administration, require_workspace_action
from .opening_evidence import read_opening_evidence, OpeningEvidenceError
from .opening_import import PROFILE


@transaction.atomic
def restore_opening_quantities(*, workspace_id, actor, origin_id, expected_sha256):
    """Fill only unknown quantities from matching immutable origin/event evidence.

    Works after servicing; never changes money, custody, events or issued PDFs.
    Replays make no write. Any contradictory non-null value stops the entire loan.
    """
    require_setup_administration(workspace_id, actor)
    workspace = Company.objects.get(pk=workspace_id)
    require_workspace_action(workspace, actor, 'data.import')
    origin = m.HistoricalLoanImport.objects.get(pk=origin_id, workspace_id=workspace_id)
    loan = m.PawnLoan.objects.select_for_update().get(pk=origin.loan_id, workspace_id=workspace_id)
    if (origin.document.get('profile') != PROFILE or origin.source_sha256 != expected_sha256
            or digest(origin.document) != expected_sha256):
        raise OpeningEvidenceError('The accepted opening fingerprint must match the reviewed correction.')
    event = loan.loan_events.get(event_kind='MIGRATION_OPENING')
    opening = read_opening_evidence(loan, event)
    if (opening['review'] != origin.document['review']
            or opening['item_mapping'] != origin.references['items']):
        raise OpeningEvidenceError('Origin and financial opening evidence disagree.')
    items = {i.pk: i for i in loan.collateral_items.select_for_update().all()}
    if set(items) != set(opening['item_mapping'].values()):
        raise OpeningEvidenceError('Opening collateral identities changed; review before correction.')
    changes = []
    for row in opening['review']['collateral']:
        quantity = row['quantity']
        if type(quantity) is not int or not 1 <= quantity <= 10000:
            raise OpeningEvidenceError('Source quantity is not a supported whole piece count.')
        item = items[opening['item_mapping'][row['id']]]
        if item.quantity is not None and item.quantity != quantity:
            raise OpeningEvidenceError('A current quantity contradicts the source; no values were overwritten.')
        if item.quantity is None:
            changes.append((item, row['id'], quantity))
    for item, source_id, quantity in changes:
        item.quantity = quantity
        item.save(update_fields=['quantity'])
    if changes:
        AuditLog.log('DATA_IMPORT', user=actor, company=workspace, content_object=loan,
            description='Completed missing collateral quantities from accepted opening evidence.',
            data={'operation': 'RESTORE_OPENING_QUANTITIES', 'origin_id': origin.pk,
                  'source_sha256': expected_sha256, 'changes': [
                      {'item_id': item.pk, 'source_id': source_id, 'before': None, 'after': quantity}
                      for item, source_id, quantity in changes]})
    return len(changes)
