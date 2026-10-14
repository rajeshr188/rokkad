"""Private, dated pilot inputs and conservative atomic count/spend capacity."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import connection
from django.db.models import Q
from django.utils import timezone

from apps.tenancy.context import current_workspace_id
from .intents import fingerprint
from .models import BudgetDay, ContactDay, Reservation, CostEvidence, ProviderReceipt
from .services import digest

ZONE = ZoneInfo("Asia/Kolkata")
CATEGORIES = {"utility", "marketing", "authentication", "authentication_international", "service"}
PURPOSES = {"setup", "trial", "paid", "ending", "service"}


def money(value):
    if not isinstance(value, str):
        raise ValidationError("dated_pilot_pricing_required")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValidationError("dated_pilot_pricing_required") from exc
    if not number.is_finite() or number < 0 or number >= Decimal("100000000") or number.as_tuple().exponent < -6:
        raise ValidationError("dated_pilot_pricing_required")
    return number


def pilot(*, at=None):
    at = at or timezone.now()
    value = getattr(settings, "PLATFORM_WHATSAPP_PILOT", {})
    try:
        if not isinstance(value, dict) or set(value) != {"version", "starts_at", "ends_at", "cohort", "purposes",
            "platform_limit", "contact_limit", "daily_spend_inr", "tariff"}:
            raise ValueError
        if not isinstance(value["version"], str) or not 1 <= len(value["version"]) <= 64:
            raise ValueError
        start, end = datetime.fromisoformat(value["starts_at"]), datetime.fromisoformat(value["ends_at"])
        if timezone.is_naive(start) or timezone.is_naive(end) or not start <= at < end:
            raise ValueError
        for key, upper in (("platform_limit", 100), ("contact_limit", 5)):
            if type(value[key]) is not int or not 1 <= value[key] <= upper:
                raise ValueError
        if money(value["daily_spend_inr"]) <= 0:
            raise ValueError
        cohort = value["cohort"]
        if not isinstance(cohort, list) or not 1 <= len(cohort) <= 100:
            raise ValueError
        for pair in cohort:
            if not isinstance(pair, dict) or set(pair) != {"workspace_id", "owner_id"} or any(type(v) is not int or v <= 0 for v in pair.values()):
                raise ValueError
        if len({p["workspace_id"] for p in cohort}) != len(cohort):
            raise ValueError
        if (not isinstance(value["purposes"], list) or not value["purposes"] or
            len(set(value["purposes"])) != len(value["purposes"]) or not set(value["purposes"]) <= PURPOSES):
            raise ValueError
        tariff = value["tariff"]
        if not isinstance(tariff, dict) or set(tariff) != {"revision", "effective_from", "effective_until", "source_url", "currency", "market", "rates"}:
            raise ValueError
        source = urlsplit(tariff["source_url"])
        if (source.scheme != "https" or source.hostname not in {"developers.facebook.com", "whatsappbusiness.com", "business.whatsapp.com"}
            or source.username or source.password or source.fragment or source.port not in (None, 443)
            or tariff["currency"] != "INR" or tariff["market"] != "IN" or not isinstance(tariff["revision"], str)
            or not 1 <= len(tariff["revision"]) <= 64 or set(tariff["rates"]) != CATEGORIES):
            raise ValueError
        first, last = date.fromisoformat(tariff["effective_from"]), date.fromisoformat(tariff["effective_until"])
        if not first <= at.astimezone(ZONE).date() <= last or last < first or max(money(v) for v in tariff["rates"].values()) <= 0:
            raise ValueError
    except (KeyError, TypeError, ValueError, AttributeError, ValidationError):
        raise ValidationError("dated_pilot_controls_required")
    return value


def in_cohort(workspace, purpose, *, at=None):
    value = pilot(at=at)
    return purpose in value["purposes"] and {"workspace_id": workspace.pk, "owner_id": workspace.owner_id} in value["cohort"]


def capture_only(workspace, purpose, *, source_at, now):
    if not getattr(settings, "PLATFORM_WHATSAPP_INTENTS_ENABLED", False):
        return True
    try:
        value = pilot(at=now)
        # Enabling a pilot cannot replay an earlier source; only new records qualify.
        return source_at < datetime.fromisoformat(value["starts_at"]) or not in_cohort(workspace, purpose, at=now)
    except ValidationError:
        return True


def estimate(value):
    # Reserve the largest configured category, including provider reclassification.
    return max(money(v) for v in value["tariff"]["rates"].values())


def gate(row, *, at=None):
    at = at or timezone.now()
    value = pilot(at=at)
    if (BudgetDay.objects.filter(pricing_hold=True).exists() or ProviderReceipt.objects.filter(
        phone_id=settings.PLATFORM_WHATSAPP_PHONE_ID, waba_id=settings.PLATFORM_WHATSAPP_WABA_ID,
        status__in=("delivered", "read")).filter(Q(pricing_category="unknown") | Q(pricing_model="unknown")).exists()):
        raise ValidationError("unreconciled_pricing_hold")
    if (not in_cohort(row.workspace, row.purpose, at=at) or
        row.source_recorded_at < datetime.fromisoformat(value["starts_at"])):
        raise ValidationError("outside_named_pilot")
    # This initial tariff is only accepted for normalized Indian mobile numbers.
    if not row.recipient_phone.startswith("+91") or len(row.recipient_phone) != 13:
        raise ValidationError("recipient_market_unpriced")
    local = at.astimezone(ZONE)
    urgent = row.purpose == "service" and row.announcement_target.announcement.urgent
    if not urgent and not time(9) <= local.time().replace(tzinfo=None) < time(18):
        raise ValidationError("quiet_hours")
    return value


def next_window(row, *, at=None, capacity=False):
    at = at or timezone.now()
    local = at.astimezone(ZONE)
    tomorrow = local.date() + timedelta(days=1)
    if not capacity and local.time().replace(tzinfo=None) < time(9):
        tomorrow = local.date()
    candidate = datetime.combine(tomorrow, time(9), tzinfo=ZONE)
    return candidate if candidate < row.expires_at else None


def reserve(row, attempt_id, *, at):
    if not connection.in_atomic_block or current_workspace_id() != row.workspace_id:
        raise ValidationError("scoped_reservation_transaction_required")
    value = gate(row, at=at)
    day = at.astimezone(ZONE).date()
    budget, _ = BudgetDay.objects.get_or_create(day=day, defaults={"policy_fingerprint": fingerprint(value),
        "platform_limit": value["platform_limit"], "contact_limit": value["contact_limit"],
        "spend_limit": money(value["daily_spend_inr"])})
    budget = BudgetDay.objects.select_for_update().get(pk=budget.pk)
    if budget.policy_fingerprint != fingerprint(value) or budget.pricing_hold:
        raise ValidationError("daily_pricing_or_policy_hold")
    amount = estimate(value)
    phone_hash = digest(row.recipient_phone)
    contact, _ = ContactDay.objects.get_or_create(budget=budget, phone_hash=phone_hash)
    if (budget.reserved_count >= budget.platform_limit or contact.reserved_count >= budget.contact_limit
        or budget.reserved_amount + amount > budget.spend_limit):
        raise ValidationError("daily_capacity_unavailable")
    # The DB trigger increments both aggregates under the same budget lock.
    return Reservation.objects.create(workspace_id=row.workspace_id, delivery=row, attempt_id=attempt_id,
        budget=budget, phone_hash=phone_hash, amount=amount, tariff=value["tariff"], created_at=at)


def check_reservation(attempt):
    value = gate(attempt.delivery)
    reservation = Reservation.objects.select_related("budget").filter(attempt=attempt).first()
    if not reservation:
        raise ValidationError("reservation_required")
    if (reservation.budget.policy_fingerprint != fingerprint(value) or reservation.budget.pricing_hold
        or reservation.budget.day != timezone.now().astimezone(ZONE).date()):
        raise ValidationError("reservation_or_pricing_changed")


def reconcile_cost(attempt, receipt):
    if receipt.status not in {"delivered", "read"}:
        return
    reservation = Reservation.objects.filter(attempt=attempt).first()
    if not reservation:
        return  # Retained PW-03 evidence predates reservations.
    # Read callbacks often omit pricing already provided with delivery. Omission
    # adds no contradictory charge facts; it cannot erase a known observation.
    if (receipt.billable is None and not receipt.pricing_model and not receipt.pricing_category
        and reservation.cost_evidence.filter(known=True).exists()):
        return
    tariff = reservation.tariff
    local_date = receipt.provider_at.astimezone(ZONE).date().isoformat()
    known = (type(receipt.billable) is bool and receipt.pricing_model == "PMP" and
        receipt.pricing_category in tariff["rates"] and tariff["effective_from"] <= local_date <= tariff["effective_until"])
    amount = (money(tariff["rates"][receipt.pricing_category]) if receipt.billable else Decimal(0)) if known else None
    CostEvidence.objects.get_or_create(receipt=receipt, defaults={"workspace_id": attempt.workspace_id,
        "reservation": reservation, "known": known, "amount": amount})
