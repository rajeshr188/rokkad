from dataclasses import dataclass
from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.loans.integrations.notice_delivery import (
    PawnNoticeDeliveryReceipt,
    create_operational_notice_job,
    deliver_pawn_notice_job,
    get_pawn_notice_delivery_states,
)
from apps.tenant_apps.loans.models import (
    LoanLicense,
    LoanOperationalNotice,
    PawnPhysicalVerificationObservation,
    PawnPhysicalVerificationSession,
    current_tenant_workspace_id,
)


class LoanOperationalNoticeError(ValueError):
    pass


@dataclass(frozen=True)
class LoanOperationalNoticeDispatchResult:
    notice: LoanOperationalNotice
    delivery: PawnNoticeDeliveryReceipt


@transaction.atomic
def create_license_expiry_notice(
    license_id,
    *,
    request_key,
    scheduled_for=None,
    actor=None,
    dispatch_due=True,
):
    workspace_id = _workspace_id()
    license = LoanLicense.objects.select_for_update().select_related("workspace__owner").get(
        pk=license_id, workspace_id=workspace_id
    )
    today = timezone.localdate()
    days_remaining = (license.expires_on - today).days
    if days_remaining > 30:
        raise LoanOperationalNoticeError(
            "License expiry alerts are available within 30 days of expiry."
        )
    payload = {
        "event_key": LoanOperationalNotice.Kind.LICENSE_EXPIRY,
        "license": {
            "id": license.pk,
            "name": license.name,
            "number": license.license_number,
            "issuing_authority": license.issuing_authority,
            "expires_on": license.expires_on.isoformat(),
            "days_remaining": days_remaining,
        },
        "generated_at": timezone.now().isoformat(),
    }
    return _create(
        workspace=license.workspace,
        kind=LoanOperationalNotice.Kind.LICENSE_EXPIRY,
        request_key=request_key,
        scheduled_for=scheduled_for,
        payload=payload,
        source_license=license,
        actor=actor,
        dispatch_due=dispatch_due,
    )


@transaction.atomic
def create_verification_discrepancy_notice(
    observation_id,
    *,
    request_key,
    scheduled_for=None,
    actor=None,
    dispatch_due=True,
):
    workspace_id = _workspace_id()
    observation = PawnPhysicalVerificationObservation.objects.select_for_update().get(
        pk=observation_id, session__workspace_id=workspace_id
    )
    if observation.session.status != PawnPhysicalVerificationSession.Status.COMPLETED:
        raise LoanOperationalNoticeError(
            "Complete the verification session before sending a discrepancy alert."
        )
    if observation.classification == PawnPhysicalVerificationObservation.Classification.FOUND:
        raise LoanOperationalNoticeError("Found collateral does not require a discrepancy alert.")
    payload = {
        "event_key": LoanOperationalNotice.Kind.VERIFICATION_DISCREPANCY,
        "verification": {
            "session_id": str(observation.session.public_id),
            "classification": observation.classification,
            "scope": observation.session.scope_location.path_label,
            "observed_location": (
                observation.observed_location.path_label
                if observation.observed_location_id else ""
            ),
            "notes": observation.notes,
        },
        "collateral": {
            "item_id": str(observation.collateral_item.public_id),
            "description": observation.collateral_item.description,
            "loan_number": observation.collateral_item.loan.loan_number,
        },
        "generated_at": timezone.now().isoformat(),
    }
    return _create(
        workspace=observation.session.workspace,
        kind=LoanOperationalNotice.Kind.VERIFICATION_DISCREPANCY,
        request_key=request_key,
        scheduled_for=scheduled_for,
        payload=payload,
        source_verification_observation=observation,
        actor=actor,
        dispatch_due=dispatch_due,
    )


def dispatch_operational_notice(notice_id, *, delivery_handler=None, as_of=None):
    workspace_id = _workspace_id()
    notice = LoanOperationalNotice.objects.get(pk=notice_id, workspace_id=workspace_id)
    as_of = as_of or timezone.now()
    if notice.scheduled_for > as_of:
        raise LoanOperationalNoticeError("This operational notice is scheduled for later.")
    state = get_pawn_notice_delivery_states((notice.notification_job_id,)).get(
        notice.notification_job_id
    )
    if state is None:
        raise LoanOperationalNoticeError("The linked Notify delivery job is missing.")
    if state.status == "SENT":
        return LoanOperationalNoticeDispatchResult(notice, state)
    if state.status == "CANCELLED":
        raise LoanOperationalNoticeError("A cancelled notice cannot be delivered.")
    receipt = (delivery_handler or deliver_pawn_notice_job)(notice.notification_job_id)
    return LoanOperationalNoticeDispatchResult(notice, receipt)


def dispatch_due_operational_notices(*, as_of=None, limit=100):
    workspace_id = _workspace_id()
    as_of = as_of or timezone.now()
    candidates = tuple(
        LoanOperationalNotice.objects.filter(
            workspace_id=workspace_id, scheduled_for__lte=as_of
        ).order_by("scheduled_for", "pk").values_list("pk", "notification_job_id")
    )
    states = get_pawn_notice_delivery_states(job for _, job in candidates)
    due = tuple(
        notice_id for notice_id, job_id in candidates
        if states.get(job_id) and states[job_id].status == "QUEUED"
    )[:limit]
    sent = failed = 0
    for notice_id in due:
        result = dispatch_operational_notice(notice_id, as_of=as_of)
        sent += result.delivery.status == "SENT"
        failed += result.delivery.status == "FAILED"
    return len(due), sent, failed


def _create(
    *, workspace, kind, request_key, scheduled_for, payload,
    source_license=None, source_verification_observation=None,
    actor, dispatch_due,
):
    request_key = str(request_key or "").strip()
    if not request_key or len(request_key) > 120:
        raise LoanOperationalNoticeError("A notice request key of at most 120 characters is required.")
    owner = workspace.owner
    recipient_email = (owner.email or "").strip()
    if not recipient_email:
        raise LoanOperationalNoticeError(
            "The workspace Owner needs an email address for operational alerts."
        )
    scheduled_for = scheduled_for or timezone.now()
    if timezone.is_naive(scheduled_for):
        scheduled_for = timezone.make_aware(scheduled_for)
    existing = LoanOperationalNotice.objects.filter(
        workspace=workspace, request_key=request_key
    ).first()
    if existing:
        source_matches = (
            existing.notice_kind == kind
            and existing.source_license_id == getattr(source_license, "pk", None)
            and existing.source_verification_observation_id
            == getattr(source_verification_observation, "pk", None)
        )
        if not source_matches:
            raise LoanOperationalNoticeError(
                "This operational notice request key was already used differently."
            )
        return existing
    notice = LoanOperationalNotice.objects.create(
        workspace=workspace,
        notice_kind=kind,
        request_key=request_key,
        scheduled_for=scheduled_for,
        recipient_name=owner.get_full_name() or owner.get_username(),
        recipient_email=recipient_email,
        payload_snapshot=payload,
        source_license=source_license,
        source_verification_observation=source_verification_observation,
        created_by=actor,
    )
    reference = create_operational_notice_job(notice)
    LoanOperationalNotice.objects.filter(pk=notice.pk).update(
        notification_event_id=reference.event_id,
        notification_job_id=reference.job_id,
    )
    notice.notification_event_id = reference.event_id
    notice.notification_job_id = reference.job_id
    if dispatch_due and scheduled_for <= timezone.now():
        transaction.on_commit(lambda: dispatch_operational_notice(notice.pk))
    return notice


def _workspace_id():
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise LoanOperationalNoticeError("Operational notices require an active tenant schema.")
    return workspace_id


__all__ = [
    "LoanOperationalNoticeDispatchResult",
    "LoanOperationalNoticeError",
    "create_license_expiry_notice",
    "create_verification_discrepancy_notice",
    "dispatch_due_operational_notices",
    "dispatch_operational_notice",
]
