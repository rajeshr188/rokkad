"""Read-only destination setup checks for the complete-history import workflow."""
import hashlib
import uuid
from datetime import date

from .portability_validation import PortabilityValidationError, MALFORMED_DATA, MISSING_EVIDENCE, OPERATIONAL_READINESS, HISTORICAL_INCONSISTENCY

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.orgs.access import resolve_workspace_access
from apps.orgs.models import Company
from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.models import (
    LoanLicenseRevision, LoanSeries, LoanProductVersion, LoanNumberSequence,
    PawnLoan, PawnLoanRelease,
)


class HistorySetupError(PortabilityValidationError):
    pass


def require_history_setup_access(workspace_id, actor, *, read_only=False):
    if current_workspace_id() != workspace_id or not workspace_id:
        raise PermissionDenied("Historical setup requires the matching Workspace context.")
    workspace = Company.all_objects.get(pk=workspace_id)
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    if not access.platform_override and (not access.membership or workspace.owner_id != getattr(actor, "pk", None)):
        raise PermissionDenied("Historical Loans preparation requires the Workspace owner.")
    for action in ("data.view", "data.import", "workspace.settings.manage"):
        access.require(action)
    if not read_only:
        from apps.subscriptions.access_policy import require_business_write
        require_business_write(workspace)
    if workspace.lifecycle_state != Company.LifecycleState.ACTIVE:
        raise PermissionDenied("Historical Loans preparation requires an active Workspace.")
    return workspace


def _text(value, label, maximum=120):
    if not isinstance(value, str) or not value.strip() or value != value.strip() or len(value) > maximum:
        raise HistorySetupError(
            f"{label} must be nonempty text without surrounding spaces (up to {maximum} characters).",
            category=MISSING_EVIDENCE if value is None or value == "" else MALFORMED_DATA,
            code="SETUP_TEXT",
        )
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise HistorySetupError(f"{label} contains control characters.", category=MALFORMED_DATA, code="SETUP_TEXT")
    return value


def _number(namespace, source_id, kind):
    digest = hashlib.sha256((kind + "\0" + source_id).encode("utf-8")).hexdigest()[:20]
    return f"H/{namespace.hex}/{digest}"


def _check_number(workspace_id, number, kind):
    model, field = (PawnLoan, "loan_number") if kind == "PAWN_LOAN" else (PawnLoanRelease, "release_number")
    if model.objects.filter(workspace_id=workspace_id, **{field: number}).exists():
        raise HistorySetupError(
            "A proposed historical number already exists. Source-identity replay must be resolved before import.",
            category=OPERATIONAL_READINESS,
            code="NUMBER_COLLISION",
        )
    sequences = list(LoanNumberSequence.objects.filter(workspace_id=workspace_id, document_kind=kind).order_by("pk")[:1001])
    if len(sequences) > 1000:
        raise HistorySetupError(
            "Too many numbering sequences for this bounded preparation check.",
            category=OPERATIONAL_READINESS,
            code="NUMBERING_LIMIT",
        )
    for sequence in sequences:
        if not number.startswith(sequence.prefix):
            continue
        suffix = number[len(sequence.prefix):]
        if len(suffix) >= sequence.width and suffix.isascii() and suffix.isdigit():
            value = int(suffix)
            if sequence.next_number <= value <= sequence.maximum_number and f"{value:0{sequence.width}d}" == suffix:
                raise HistorySetupError(
                    "The proposed historical number overlaps a configured future numbering range.",
                    category=OPERATIONAL_READINESS,
                    code="NUMBER_RANGE_COLLISION",
                )


def preview_history_setup(*, workspace_id, actor, revision_id, series_id, product_version_id,
                          source_namespace, source_loan_id, source_loan_number, source_license_number,
                          disbursed_on, tenure_months, calculation_contract_version, operational_grace_days,
                          source_release_id="", source_release_number="", legacy_license_evidence=None,
                          local_loan_number=None):
    require_history_setup_access(workspace_id, actor)
    try:
        namespace = uuid.UUID(str(source_namespace))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HistorySetupError(
            "Use a stable source namespace UUID.",
            category=MALFORMED_DATA,
            code="SOURCE_NAMESPACE",
        ) from exc
    for value, label, maximum in ((source_loan_id, "Source loan ID", 120),
                                  (source_loan_number, "Source loan number", 120),
                                  (source_license_number, "Source licence number", 100),
                                  (calculation_contract_version, "Calculation contract", 40)):
        _text(value, label, maximum)
    if type(disbursed_on) is not date or disbursed_on > timezone.localdate():
        raise HistorySetupError(
            "The original disbursal date must be today or earlier.",
            category=HISTORICAL_INCONSISTENCY,
            code="DISBURSAL_DATE",
        )
    if type(tenure_months) is not int or tenure_months < 1 or type(operational_grace_days) is not int or not 0 <= operational_grace_days <= 30:
        raise HistorySetupError(
            "Tenure and operational grace must be valid whole numbers.",
            category=MALFORMED_DATA,
            code="TENURE_GRACE",
        )
    if bool(source_release_id) != bool(source_release_number):
        raise HistorySetupError(
            "Provide both the source release ID and release number, or neither.",
            category=MISSING_EVIDENCE,
            code="RELEASE_IDENTITY",
        )
    if source_release_id:
        _text(source_release_id, "Source release ID")
        _text(source_release_number, "Source release number")
    try:
        revision = LoanLicenseRevision.objects.select_related("license").get(workspace_id=workspace_id, pk=revision_id)
        series = LoanSeries.objects.get(workspace_id=workspace_id, pk=series_id, license_id=revision.license_id)
        product = LoanProductVersion.objects.select_related("product").get(workspace_id=workspace_id, pk=product_version_id)
    except (LoanLicenseRevision.DoesNotExist, LoanSeries.DoesNotExist, LoanProductVersion.DoesNotExist, ValueError, ValidationError) as exc:
        raise HistorySetupError(
            "Select a licence revision, matching series and product version from this Workspace.",
            category=OPERATIONAL_READINESS,
            code="DESTINATION_SETUP",
        ) from exc
    legacy = revision.kind == "LEGACY_REFERENCE"
    if legacy_license_evidence is not None:
        _text(legacy_license_evidence, "Legacy licence evidence", 255)
        if not legacy or not revision.license.is_legacy_reference or revision.license.is_active:
            raise HistorySetupError(
                "Unknown source validity must map to an inactive legacy reference.",
                category=OPERATIONAL_READINESS,
                code="LEGACY_REFERENCE",
            )
    elif legacy or revision.license.is_legacy_reference:
        raise HistorySetupError(
            "A legacy reference requires explicit opening evidence; complete history requires verified licence validity.",
            category=MISSING_EVIDENCE,
            code="LICENCE_VALIDITY_EVIDENCE",
        )
    if revision.license_number != source_license_number or (not legacy and not revision.issued_on <= disbursed_on <= revision.expires_on):
        raise HistorySetupError(
            "The selected licence revision must match the source licence number and cover the original disbursal date.",
            category=OPERATIONAL_READINESS,
            code="LICENCE_MAPPING",
        )
    expected = ("FLEXIBLE_PARTIAL_PAYMENT", "NONE", "FLEXIBLE", "REDUCE_PRINCIPAL")
    actual = (product.repayment_structure, product.amortisation_method, product.payment_frequency, product.extra_payment_rule)
    if actual != expected or product.status not in {"ACTIVE", "RETIRED"}:
        raise HistorySetupError(
            "Select an active or retired flexible partial-payment product version with no amortisation and principal reduction.",
            category=OPERATIONAL_READINESS,
            code="PRODUCT_SUPPORT",
        )
    if not product.minimum_tenor_months <= tenure_months <= product.maximum_tenor_months:
        raise HistorySetupError(
            "The original tenure is outside the selected product version's bounds.",
            category=OPERATIONAL_READINESS,
            code="PRODUCT_TENURE",
        )
    if product.calculation_contract_version != calculation_contract_version or product.operational_grace_days != operational_grace_days:
        raise HistorySetupError(
            "Source calculation contract and grace days must match the selected frozen product version.",
            category=OPERATIONAL_READINESS,
            code="PRODUCT_CONTRACT",
        )
    if (product.available_from and disbursed_on < product.available_from) or (product.available_until and disbursed_on > product.available_until):
        raise HistorySetupError(
            "The product version was unavailable on the original disbursal date.",
            category=OPERATIONAL_READINESS,
            code="PRODUCT_DATE",
        )
    if local_loan_number is not None:
        _text(local_loan_number, "Destination loan number", 64)
    numbers = [{"kind": "PAWN_LOAN", "source_id": source_loan_id, "source_number": source_loan_number,
                "local_number": local_loan_number if local_loan_number is not None else _number(namespace, source_loan_id, "PAWN_LOAN")}]
    if source_release_id:
        numbers.append({"kind": "PAWN_LOAN_RELEASE", "source_id": source_release_id,
                        "source_number": source_release_number,
                        "local_number": _number(namespace, source_release_id, "PAWN_LOAN_RELEASE")})
    for item in numbers:
        _check_number(workspace_id, item["local_number"], item["kind"])
    return {"revision": revision, "series": series, "product": product, "numbers": numbers,
            "source_namespace": str(namespace), "disbursed_on": disbursed_on}
