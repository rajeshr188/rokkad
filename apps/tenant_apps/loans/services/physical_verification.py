from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.orgs.access import resolve_workspace_access
from apps.tenant_apps.loans.access import LOANS_OWNER_ACTION
from apps.tenant_apps.loans.domain import CollateralCustodyState
from apps.tenant_apps.loans.models import (
    PawnCollateralItem,
    PawnCollateralStorageMovement,
    PawnPhysicalVerificationExpectation,
    PawnPhysicalVerificationObservation,
    PawnPhysicalVerificationResolution,
    PawnPhysicalVerificationSession,
    PawnStorageLocation,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.services.storage_operations import (
    remove_collateral_from_storage,
)


class PawnPhysicalVerificationError(ValueError):
    pass


class PawnPhysicalVerificationBlockerError(PawnPhysicalVerificationError):
    pass


def unresolved_physical_verification_item_ids(item_ids):
    item_ids = tuple(int(value) for value in item_ids)
    if not item_ids:
        return ()
    rows = (
        PawnPhysicalVerificationObservation.objects.filter(
            collateral_item_id__in=item_ids,
            classification__in=(
                PawnPhysicalVerificationObservation.Classification.MISSING,
                PawnPhysicalVerificationObservation.Classification.MISPLACED,
                PawnPhysicalVerificationObservation.Classification.UNEXPECTED,
            ),
        )
        .filter(Q(resolution__isnull=True) | Q(resolution__outcome="DAMAGED"))
        .values_list("collateral_item_id", flat=True)
        .distinct()
    )
    return tuple(sorted(rows))


def assert_physical_verification_clear(item_ids, *, operation):
    blocked = unresolved_physical_verification_item_ids(item_ids)
    if blocked:
        raise PawnPhysicalVerificationBlockerError(
            f"{operation} is blocked by unresolved physical-verification evidence "
            f"for collateral item(s): {', '.join(map(str, blocked))}."
        )


@transaction.atomic
def start_physical_verification(*, scope_location_id, actor):
    workspace_id = _workspace_id()
    scope = PawnStorageLocation.objects.select_for_update().get(
        pk=scope_location_id, workspace_id=workspace_id, is_active=True
    )
    _require_owner(scope.workspace, actor)
    if scope.level == PawnStorageLocation.Level.BRANCH:
        raise PawnPhysicalVerificationError(
            "Physical verification must start at a Vault or selected descendant."
        )
    location_ids = _descendant_ids(scope)
    items = tuple(
        PawnCollateralItem.objects.select_for_update()
        .select_related("loan")
        .filter(
            loan__workspace_id=workspace_id,
            current_storage_location_id__in=location_ids,
            custody_state=CollateralCustodyState.IN_VAULT.value,
        )
        .order_by("pk")
    )
    if not items:
        raise PawnPhysicalVerificationError(
            "The selected storage scope contains no in-vault collateral to verify."
        )
    session = PawnPhysicalVerificationSession.objects.create(
        workspace_id=workspace_id,
        scope_location=scope,
        started_by=actor,
    )
    PawnPhysicalVerificationExpectation.objects.bulk_create(
        [
            PawnPhysicalVerificationExpectation(
                workspace_id=workspace_id,
                session=session,
                collateral_item=item,
                expected_location_id=item.current_storage_location_id,
                custody_state_snapshot=item.custody_state,
                loan_number_snapshot=item.loan.loan_number,
                item_description_snapshot=item.description,
            )
            for item in items
        ]
    )
    return session


@transaction.atomic
def record_physical_verification_observation(
    session_id,
    *,
    collateral_item_id,
    classification,
    observed_location_id=None,
    notes="",
    actor,
):
    workspace_id = _workspace_id()
    session = PawnPhysicalVerificationSession.objects.select_for_update().select_related(
        "workspace", "scope_location"
    ).get(pk=session_id, workspace_id=workspace_id)
    _require_owner(session.workspace, actor)
    if session.status != PawnPhysicalVerificationSession.Status.OPEN:
        raise PawnPhysicalVerificationError("Completed verification sessions cannot change.")
    item = PawnCollateralItem.objects.select_for_update().get(
        pk=collateral_item_id, loan__workspace_id=workspace_id
    )
    expectation = session.expectations.filter(collateral_item=item).first()
    try:
        classification = PawnPhysicalVerificationObservation.Classification(classification)
    except ValueError as exc:
        raise PawnPhysicalVerificationError("Unknown verification classification.") from exc
    observed = None
    if observed_location_id:
        observed = PawnStorageLocation.objects.get(
            pk=observed_location_id, workspace_id=workspace_id, is_active=True
        )
    if classification == PawnPhysicalVerificationObservation.Classification.UNEXPECTED:
        if expectation is not None or observed is None:
            raise PawnPhysicalVerificationError(
                "Unexpected observations require an item outside the frozen scope and an observed location."
            )
        if observed.pk not in _descendant_ids(session.scope_location):
            raise PawnPhysicalVerificationError(
                "Unexpected collateral must be observed inside the frozen location scope."
            )
    else:
        if expectation is None:
            raise PawnPhysicalVerificationError("The item was not expected in this verification scope.")
        if classification == PawnPhysicalVerificationObservation.Classification.FOUND:
            observed = observed or expectation.expected_location
            if observed.pk != expectation.expected_location_id:
                raise PawnPhysicalVerificationError("Use Misplaced when the observed location differs.")
        elif classification == PawnPhysicalVerificationObservation.Classification.MISSING:
            if observed is not None:
                raise PawnPhysicalVerificationError("A missing item cannot have an observed location.")
        elif classification == PawnPhysicalVerificationObservation.Classification.MISPLACED:
            if observed is None or observed.pk == expectation.expected_location_id:
                raise PawnPhysicalVerificationError("Misplaced evidence requires a different observed location.")
    return PawnPhysicalVerificationObservation.objects.create(
        session=session,
        expectation=expectation,
        collateral_item=item,
        classification=classification,
        observed_location=observed,
        notes=str(notes or "").strip(),
        recorded_by=actor,
    )


@transaction.atomic
def complete_physical_verification(session_id, *, actor):
    workspace_id = _workspace_id()
    session = PawnPhysicalVerificationSession.objects.select_for_update().select_related(
        "workspace"
    ).get(pk=session_id, workspace_id=workspace_id)
    _require_owner(session.workspace, actor)
    if session.status == PawnPhysicalVerificationSession.Status.COMPLETED:
        return session
    missing_count = session.expectations.filter(observation__isnull=True).count()
    if missing_count:
        raise PawnPhysicalVerificationError(
            f"Record an observation for all frozen items; {missing_count} remain."
        )
    session.status = PawnPhysicalVerificationSession.Status.COMPLETED
    session.completed_by = actor
    session.completed_at = timezone.now()
    session.save(update_fields=["status", "completed_by", "completed_at"])
    return session


@transaction.atomic
def resolve_physical_verification_discrepancy(
    observation_id,
    *,
    outcome,
    reason,
    current_market_value=None,
    agreed_compensation=None,
    compensation_reference="",
    actor,
):
    workspace_id = _workspace_id()
    observation = PawnPhysicalVerificationObservation.objects.select_for_update().get(
        pk=observation_id, session__workspace_id=workspace_id
    )
    _require_owner(observation.session.workspace, actor)
    if observation.session.status != PawnPhysicalVerificationSession.Status.COMPLETED:
        raise PawnPhysicalVerificationError("Complete the verification session before resolution.")
    if observation.classification == PawnPhysicalVerificationObservation.Classification.FOUND:
        raise PawnPhysicalVerificationError("Found observations do not require resolution.")
    if hasattr(observation, "resolution"):
        return observation.resolution
    try:
        outcome = PawnPhysicalVerificationResolution.Outcome(outcome)
    except ValueError as exc:
        raise PawnPhysicalVerificationError("Unknown discrepancy resolution outcome.") from exc
    reason = str(reason or "").strip()
    if not reason:
        raise PawnPhysicalVerificationError("A reason is required for discrepancy resolution.")
    market = _money_or_none(current_market_value)
    agreed = _money_or_none(agreed_compensation)
    reference = str(compensation_reference or "").strip()
    if outcome == PawnPhysicalVerificationResolution.Outcome.LOST_COMPENSATED:
        if observation.classification != PawnPhysicalVerificationObservation.Classification.MISSING:
            raise PawnPhysicalVerificationError("Only a missing item can be classified as lost.")
        if market is None or market <= 0 or agreed is None or agreed <= 0 or not reference:
            raise PawnPhysicalVerificationError(
                "Lost collateral requires market value, negotiated compensation, and cash-settlement reference."
            )
    elif any(value is not None for value in (market, agreed)) or reference:
        raise PawnPhysicalVerificationError("Compensation evidence is only valid for lost collateral.")
    if outcome == PawnPhysicalVerificationResolution.Outcome.LOCATION_CORRECTED:
        if observation.observed_location_id is None:
            raise PawnPhysicalVerificationError("Location correction requires an observed location.")
        _correct_location(observation, actor=actor)
    if outcome == PawnPhysicalVerificationResolution.Outcome.CONFIRMED_FOUND:
        if observation.classification not in {
            PawnPhysicalVerificationObservation.Classification.MISSING,
            PawnPhysicalVerificationObservation.Classification.MISPLACED,
            PawnPhysicalVerificationObservation.Classification.UNEXPECTED,
        }:
            raise PawnPhysicalVerificationError("This discrepancy cannot be confirmed found.")
    if outcome == PawnPhysicalVerificationResolution.Outcome.LOST_COMPENSATED:
        remove_collateral_from_storage(
            observation.collateral_item,
            workflow_source="VERIFICATION_LOSS",
            source_reference=str(observation.pk),
            actor=actor,
        )
    return PawnPhysicalVerificationResolution.objects.create(
        observation=observation,
        outcome=outcome,
        reason=reason,
        current_market_value=market,
        agreed_compensation=agreed,
        compensation_reference=reference,
        resolved_by=actor,
    )


def _correct_location(observation, *, actor):
    item = observation.collateral_item
    destination = PawnStorageLocation.objects.select_for_update().get(
        pk=observation.observed_location_id
    )
    if destination.capacity is not None:
        occupied = destination.current_collateral_items.exclude(pk=item.pk).count()
        if occupied >= destination.capacity:
            raise PawnPhysicalVerificationError("The observed location is at capacity.")
    movement = PawnCollateralStorageMovement.objects.create(
        collateral_item=item,
        from_location=item.current_storage_location,
        to_location=destination,
        kind=(
            PawnCollateralStorageMovement.Kind.TRANSFER
            if item.current_storage_location_id
            else PawnCollateralStorageMovement.Kind.PLACEMENT
        ),
        reason="Physical-verification discrepancy correction.",
        workflow_source="VERIFICATION_RESOLUTION",
        source_reference=str(observation.pk),
        moved_by=actor,
    )
    item.current_storage_location = destination
    item.save(update_fields=["current_storage_location", "updated_at"])
    return movement


def _descendant_ids(scope):
    ids = {scope.pk}
    frontier = {scope.pk}
    while frontier:
        children = set(
            PawnStorageLocation.objects.filter(
                workspace_id=scope.workspace_id, parent_id__in=frontier
            ).values_list("pk", flat=True)
        )
        frontier = children - ids
        ids.update(children)
    return tuple(ids)


def _workspace_id():
    value = current_tenant_workspace_id()
    if value is None:
        raise PawnPhysicalVerificationError("Physical verification requires an active tenant schema.")
    return value


def _require_owner(workspace, actor):
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    if not access.can(LOANS_OWNER_ACTION):
        raise PawnPhysicalVerificationError(
            "Only the workspace Owner may conduct physical verification during the pilot."
        )


def _money_or_none(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PawnPhysicalVerificationError("Compensation amounts must be valid currency values.") from exc


__all__ = [
    "PawnPhysicalVerificationBlockerError",
    "PawnPhysicalVerificationError",
    "assert_physical_verification_clear",
    "complete_physical_verification",
    "record_physical_verification_observation",
    "resolve_physical_verification_discrepancy",
    "start_physical_verification",
    "unresolved_physical_verification_item_ids",
]
