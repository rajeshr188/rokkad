"""Reviewed configuration changes; existing policy services remain the writers."""

from datetime import date
from decimal import Decimal
import hashlib
import json

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from apps.configuration.models import PreferenceAuditLog
from apps.orgs.models import Company
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.domain.origination_capabilities import capability_notes
from .action_access import require_setup_administration
from .economic_policies import (
    create_pawn_economic_configuration,
    create_pawn_series_interest_rates,
    resolve_pawn_loan_economic_policy,
    resolve_pawn_metal_interest_rate_policy,
    PawnEconomicPolicyError,
)
from .origination_summary import policy_source, calculation_terms

SALT = "loans.economic-policy-review.v1"
AUDIT_KEY = "loans.calculation.review"
MAX_AGE = 1800
RATE_FIELDS = {
    "gold_monthly_interest_rate": "GOLD",
    "silver_monthly_interest_rate": "SILVER",
    "bronze_monthly_interest_rate": "BRONZE",
}
POLICY_REVIEW_FIELDS = (
    "valuation_method",
    "maximum_ltv_ratio",
    "advance_interest_periods",
    "default_tenure_months",
    "default_entry_purpose",
    "interest_method",
    "partial_month_method",
    "partial_month_cutoff_days",
    "partial_month_lower_fraction",
    "minimum_first_month",
    "capitalization_interval_periods",
    "rounding_method",
    "currency_quantum",
    "effective_until",
)


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


def _authorize(workspace, actor):
    if m.current_tenant_workspace_id() != workspace.pk:
        raise PermissionDenied("Select the matching Workspace.")
    require_setup_administration(workspace.pk, actor)


def _values(values):
    return {
        key: (
            value.pk
            if hasattr(value, "pk")
            else str(value) if isinstance(value, (Decimal, date)) else value
        )
        for key, value in values.items()
    }


def _state(workspace):
    return _digest(
        {
            model.__name__: list(
                model.objects.filter(workspace=workspace).order_by("pk").values()
            )
            for model in (
                m.PawnLoanEconomicPolicy,
                m.PawnMetalInterestRatePolicy,
                m.PawnLoanFeePolicy,
                m.LoanLicense,
                m.LoanSeries,
            )
        }
    )


def _scope(workspace, values):
    series, license = values.get("series"), values.get("license")
    if series is not None:
        try:
            series = m.LoanSeries.objects.select_related("license").get(
                pk=series.pk, workspace=workspace
            )
        except m.LoanSeries.DoesNotExist:
            raise ValueError("Choose a series in this Workspace.") from None
        if license is not None and series.license_id != license.pk:
            raise ValueError("Choose a series under the selected licence.")
        license = series.license
    if (
        license is not None
        and not m.LoanLicense.objects.filter(
            pk=license.pk, workspace=workspace
        ).exists()
    ):
        raise ValueError("Choose a licence in this Workspace.")
    return license, series


def _candidate(model, *, workspace, actor, license, series, day, **fields):
    scope = dict(
        workspace=workspace, license=license, series=series, effective_from=day
    )
    revision_scope = dict(scope)
    if "metal" in fields:
        revision_scope["metal"] = fields["metal"]
    revision = (
        model.objects.filter(**revision_scope).aggregate(value=Max("revision"))["value"]
        or 0
    ) + 1
    row = model(created_by=actor, revision=revision, **scope, **fields)
    row.full_clean()
    return row


def preview_economic_change(*, workspace, actor, kind, values):
    _authorize(workspace, actor)
    if kind not in {"configuration", "series_rates"}:
        raise ValueError("Choose a supported configuration change.")
    license, series = _scope(workspace, values)
    if kind == "series_rates" and series is None:
        raise ValueError("Choose a series for this rate-only change.")
    day = values.get("effective_from")
    if type(day) is not date:
        raise ValueError("Choose an effective date.")
    end = values.get("effective_until")
    source_args = dict(
        workspace_id=workspace.pk,
        license_id=license.pk if license else None,
        series_id=series.pk if series else None,
        as_of_date=day,
    )
    changes = []
    if not any(values.get(field) is not None for field in RATE_FIELDS):
        raise ValueError("Enter at least one metal rate for the review.")
    if kind == "configuration":
        fields = {
            key: value
            for key, value in values.items()
            if key not in {*RATE_FIELDS, "license", "series", "effective_from"}
        }
        fields["default_entry_purpose"] = (
            fields.get("default_entry_purpose") or "INHERIT"
        )
        # The writer's current default differs from the legacy model default.
        fields.setdefault("minimum_first_month", True)
        candidate = _candidate(
            m.PawnLoanEconomicPolicy,
            workspace=workspace,
            actor=actor,
            license=license,
            series=series,
            day=day,
            **fields,
        )
        try:
            before = resolve_pawn_loan_economic_policy(**source_args)
        except PawnEconomicPolicyError:
            before = None
        for field in POLICY_REVIEW_FIELDS:
            old, new = getattr(before, field, None), getattr(candidate, field)
            if old != new:
                changes.append(
                    dict(
                        field=field.replace("_", " ").capitalize(),
                        before=str(old) if before is not None else "Not configured",
                        after=str(new),
                    )
                )
    for field, metal in RATE_FIELDS.items():
        value = values.get(field)
        if value is None:
            continue
        _candidate(
            m.PawnMetalInterestRatePolicy,
            workspace=workspace,
            actor=actor,
            license=license,
            series=series,
            day=day,
            effective_until=end,
            metal=metal,
            monthly_interest_rate=value,
        )
        try:
            prior = resolve_pawn_metal_interest_rate_policy(**source_args, metal=metal)
        except PawnEconomicPolicyError:
            prior = None
        changes.append(
            dict(
                field=f"{metal.title()} monthly interest",
                before=(
                    f"{prior.monthly_interest_rate}% — {policy_source(prior)}"
                    if prior
                    else "Not configured"
                ),
                after=f"{value}% — proposed scope below",
            )
        )
    loans = m.PawnLoan.objects.filter(workspace=workspace, loan_date__gte=day)
    if end:
        loans = loans.filter(loan_date__lte=end)
    if series:
        loans = loans.filter(series=series)
    elif license:
        loans = loans.filter(license=license)
    narrower = Q(pk__in=[])
    if series is None:
        narrower = Q(series__isnull=False) if license else Q(license__isnull=False)
    shadowing = []
    for model in (m.PawnLoanEconomicPolicy, m.PawnMetalInterestRatePolicy):
        rows = (
            model.objects.filter(workspace=workspace, is_active=True)
            .filter(narrower)
            .filter(Q(effective_until__isnull=True) | Q(effective_until__gte=day))
        )
        if license:
            rows = rows.filter(license=license)
        if end:
            rows = rows.filter(effective_from__lte=end)
        if model is m.PawnMetalInterestRatePolicy:
            rows = rows.filter(
                metal__in=[
                    metal
                    for field, metal in RATE_FIELDS.items()
                    if values.get(field) is not None
                ]
            )
        elif kind == "series_rates":
            continue
        for row in rows.select_related("license", "series").order_by("pk")[:21]:
            shadowing.append(
                dict(
                    label=(
                        row.metal.title() + " interest"
                        if hasattr(row, "metal")
                        else "Calculation rules"
                    ),
                    source=policy_source(row),
                )
            )
    warnings = (
        capability_notes(
            {
                key: getattr(candidate, key)
                for key in (
                    "interest_method",
                    "partial_month_method",
                    "advance_interest_periods",
                    "currency_quantum",
                )
            }
        )
        if kind == "configuration"
        else []
    )
    review = dict(
        kind=kind,
        scope=(
            f"Series {series.pawn_display_name} / {license.license_number}"
            if series
            else f"Licence {license.license_number}" if license else "Workspace default"
        ),
        effective_from=day,
        effective_until=end,
        changes=changes,
        shadowing=shadowing,
        drafts=loans.filter(state="DRAFT").count(),
        saved=loans.exclude(state__in=("DRAFT", "CANCELLED")).count(),
        warnings=warnings,
        full_override=kind == "configuration" and license is not None,
        current_source=(
            policy_source(before) if kind == "configuration" and before else None
        ),
        proposed_terms=(
            [
                row
                for row in calculation_terms(
                    {key: getattr(candidate, key) for key in POLICY_REVIEW_FIELDS}
                    | {"policy_version": 2}
                )
                if row[0] != "Capability limits"
            ]
            if kind == "configuration"
            else []
        ),
    )
    token = signing.dumps(
        dict(
            workspace=workspace.pk,
            actor=actor.pk,
            kind=kind,
            values=_values(values),
            state=_state(workspace),
            date=timezone.localdate().isoformat(),
        ),
        salt=SALT,
        compress=True,
    )
    return review, token


@transaction.atomic
def confirm_economic_change(
    *, workspace, actor, kind, values, token, acknowledged=False
):
    _authorize(workspace, actor)
    if acknowledged is not True:
        raise ValueError("Confirm the scope, effective date and changes shown.")
    try:
        signed = signing.loads(token or "", salt=SALT)
        if not isinstance(signed, dict) or (
            signed.get("workspace"),
            signed.get("actor"),
            signed.get("kind"),
            signed.get("values"),
        ) != (workspace.pk, actor.pk, kind, _values(values)):
            raise ValueError(
                "This review belongs to different values, scope or user. Preview again."
            )
    except (signing.BadSignature, TypeError) as exc:
        raise ValueError(
            "Review invalid or expired. Preview the change again."
        ) from exc
    Company.all_objects.select_for_update().get(pk=workspace.pk)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    previous = PreferenceAuditLog.objects.filter(
        workspace=workspace, key=f"{AUDIT_KEY}.{token_hash}", changed_by=actor
    ).first()
    if previous:
        return dict(
            already_saved=True, policy_ids=json.loads(previous.new_value)["policy_ids"]
        )
    try:
        signing.loads(token, salt=SALT, max_age=MAX_AGE)
    except signing.BadSignature as exc:
        raise ValueError("Review expired. Preview the change again.") from exc
    if (
        signed.get("state") != _state(workspace)
        or signed.get("date") != timezone.localdate().isoformat()
    ):
        raise ValueError(
            "Setup changed since review. Preview the current scope and terms again."
        )
    # Revalidate all candidates under the same lock used by the existing writers.
    preview_economic_change(workspace=workspace, actor=actor, kind=kind, values=values)
    if kind == "configuration":
        license, _ = _scope(workspace, values)
        result = create_pawn_economic_configuration(
            workspace=workspace, actor=actor, **(values | {"license": license})
        )
        ids = [
            row.pk
            for row in (
                result.economic_policy,
                result.gold_rate_policy,
                result.silver_rate_policy,
                result.bronze_rate_policy,
            )
            if row is not None
        ]
    else:
        result = create_pawn_series_interest_rates(
            workspace=workspace, actor=actor, **values
        )
        ids = [row.pk for row in result]
    PreferenceAuditLog.objects.create(
        scope="workspace",
        workspace=workspace,
        key=f"{AUDIT_KEY}.{token_hash}",
        changed_by=actor,
        old_value=json.dumps({"state": signed["state"]}),
        new_value=json.dumps(
            dict(
                review_hash=token_hash,
                kind=kind,
                values=signed["values"],
                policy_ids=ids,
            )
        ),
    )
    return dict(already_saved=False, policy_ids=ids)
