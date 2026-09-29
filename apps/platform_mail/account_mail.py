"""Allauth account intents; links exist only while rendering for dispatch."""
import json
from datetime import timedelta

from allauth.account import app_settings
from allauth.account.models import EmailAddress, EmailConfirmationHMAC
from allauth.account.utils import user_pk_to_url_str
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import AccountEmail, Delivery


def check_link_configuration():
    if (not app_settings.EMAIL_CONFIRMATION_HMAC
            or app_settings.EMAIL_VERIFICATION_BY_CODE_ENABLED
            or app_settings.PASSWORD_RESET_BY_CODE_ENABLED):
        raise ValidationError("Queued account mail requires allauth's HMAC confirmation and link-based reset flows.")


def state_fingerprint(source, recipient):
    user, address = source.user, source.email_address
    state = [source.kind, user.pk, user.is_active, user.email, recipient,
             address.pk if address else None, address.email if address else None,
             address.verified if address else None]
    if source.kind == AccountEmail.Kind.PASSWORD_RESET:
        state.extend([user.password, str(user.last_login)])
    # Verification is queued before signup logs the user in. That login must not
    # invalidate verification; reset intents do bind to password and login state.
    return salted_hmac("platform-mail-account-state", json.dumps(state), algorithm="sha256").hexdigest()


@transaction.atomic
def enqueue_account_email(*, user, email, kind, email_address=None):
    check_link_configuration()
    if kind not in AccountEmail.Kind.values:
        raise ValidationError("Unsupported account email kind.")
    user = get_user_model().objects.select_for_update().get(pk=user.pk)
    if email_address is not None:
        address = EmailAddress.objects.filter(pk=email_address.pk, user=user, email__iexact=email).first()
        if address is None:
            return None
    else:
        address = EmailAddress.objects.filter(user=user, email__iexact=email).first()
    if not user.is_active:
        return None
    if kind == AccountEmail.Kind.VERIFICATION and (address is None or address.verified):
        return None
    if address is None and user.email.casefold() != email.casefold():
        return None
    source = AccountEmail(user=user, email_address=address, kind=kind)
    digest = state_fingerprint(source, email)
    existing = Delivery.objects.filter(
        account_email__user=user, account_email__kind=kind,
        source_fingerprint=digest, expires_at__gt=timezone.now(),
        status__in=[Delivery.Status.QUEUED, Delivery.Status.SENDING, Delivery.Status.UNKNOWN],
    ).first()
    if existing:
        return existing
    source.save()
    return Delivery.objects.create(
        key=f"account:{source.pk}", account_email=source, recipient=email,
        source_fingerprint=digest,
        expires_at=timezone.now() + timedelta(seconds=min(1800, settings.PASSWORD_RESET_TIMEOUT)),
    )


def account_source_problem(row):
    source = row.account_email
    if not source.user.is_active:
        return "account_inactive"
    if source.kind == AccountEmail.Kind.VERIFICATION:
        if source.email_address is None or source.email_address.verified:
            return "verification_no_longer_needed"
    elif source.kind != AccountEmail.Kind.PASSWORD_RESET:
        return "invalid_account_email_kind"
    if not constant_time_compare(state_fingerprint(source, row.recipient), row.source_fingerprint):
        return "account_state_changed"
    return ""


def render_account_email(row, origin):
    check_link_configuration()
    source = row.account_email
    if source.kind == AccountEmail.Kind.VERIFICATION:
        key = EmailConfirmationHMAC(source.email_address).key
        path = reverse("account_confirm_email", kwargs={"key": key})
        subject = "Verify your Rokkad email address"
        action = "Verify email address"
        purpose = "Confirm this email address to use your Rokkad account."
    elif source.kind == AccountEmail.Kind.PASSWORD_RESET:
        key = app_settings.PASSWORD_RESET_TOKEN_GENERATOR().make_token(source.user)
        path = reverse("account_reset_password_from_key", kwargs={
            "uidb36": user_pk_to_url_str(source.user), "key": key})
        subject = "Reset your Rokkad password"
        action = "Reset password"
        purpose = "A password reset was requested for your Rokkad account."
    else:
        raise ValidationError("Unsupported account email kind.")
    context = {"subject": subject, "purpose": purpose, "action": action, "action_url": origin + path}
    return (subject, render_to_string("platform_mail/account.html", context),
            render_to_string("platform_mail/account.txt", context))
