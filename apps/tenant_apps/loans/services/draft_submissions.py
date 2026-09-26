"""One browser form intent creates one loan, including its uploaded photographs."""
from uuid import UUID, uuid4

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.orgs.models import Company
from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.models import PawnLoan
from .action_access import require_workspace_action
from .pawn_drafts import create_pawn_draft_with_photos


SALT = "loans.new-draft-submission.v1"


def _authorize(workspace, actor):
    if current_workspace_id() != workspace.pk:
        raise PermissionDenied("Draft submission requires the active Workspace.")
    require_workspace_action(workspace, actor, "data.create")


def new_draft_submission(*, workspace, actor):
    _authorize(workspace, actor)
    return signing.dumps({"workspace": workspace.pk, "actor": actor.pk,
        "submission": str(uuid4())}, salt=SALT)


def _submission_id(token, *, workspace, actor):
    _authorize(workspace, actor)
    try:
        values = signing.loads(token or "", salt=SALT)
        if values["workspace"] != workspace.pk or values["actor"] != actor.pk:
            raise PermissionDenied("This New loan form belongs to another workspace or signed-in user.")
        return UUID(values["submission"])
    except (signing.BadSignature, ValueError, KeyError, TypeError) as exc:
        raise ValueError("This form's save reference is missing or invalid. Check Loans for a recent save before opening a fresh New loan form.") from exc


def _existing(workspace, actor, submission_id):
    loan = PawnLoan.objects.filter(workspace=workspace, creation_submission_id=submission_id).first()
    if loan is not None and loan.created_by_id != actor.pk:
        raise PermissionDenied("This save reference belongs to another recording user.")
    return loan


def saved_draft_submission(*, workspace, actor, token):
    """Recover a completed save before revalidating now-stale form choices/files."""
    return _existing(workspace, actor, _submission_id(token, workspace=workspace, actor=actor))


@transaction.atomic
def submit_new_draft(command, *, actor, token, photos=()):
    if command.workspace_id != current_workspace_id():
        raise PermissionDenied("Draft submission requires the active Workspace.")
    # Lock before number allocation or storage writes. A second worker waits for
    # the first transaction, then sees its committed loan. Failed saves roll back
    # the number and identity together; existing photo compensation remains used.
    workspace = Company.objects.select_for_update().get(pk=command.workspace_id)
    submission_id = _submission_id(token, workspace=workspace, actor=actor)
    existing = _existing(workspace, actor, submission_id)
    if existing is not None:
        return existing, False
    loan = create_pawn_draft_with_photos(command, photos=photos, actor=actor, submission_id=submission_id)
    return loan, True
