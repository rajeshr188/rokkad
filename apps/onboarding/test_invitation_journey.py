"""A fresh owner can invite a verified teammate without creating paid access."""
from io import StringIO
from unittest.mock import patch
import uuid

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings

from apps.onboarding.forms import CompanySetupForm
from apps.orgs.models import Membership, Role
from apps.orgs.services.control_plane import (
    accept_invitation, create_onboarding_workspace_from_form,
    send_onboarding_team_invitations,
)
from apps.orgs.services.workspace_roles import seed_workspace_roles
from apps.platform_mail.models import Attempt, Delivery
from apps.platform_mail.tests import MAIL_SETTINGS
from apps.subscriptions.access_policy import workspace_activity
from apps.subscriptions.models import Invoice, Payment, Subscription


@override_settings(**MAIL_SETTINGS, BILLING_CHECKOUT_ENABLED=False,
                   BILLING_RECURRING_ENABLED=False, BILLING_ALLOW_TRIAL_START=False)
class InvitationJourneyTests(TestCase):
    def test_fresh_workspace_invitation_dispatch_and_verified_acceptance(self):
        users = get_user_model()
        owner = users.objects.create_user(username="journey-owner", email="owner@example.com")
        teammate = users.objects.create_user(username="journey-teammate", email="team@example.com")
        EmailAddress.objects.create(user=teammate, email=teammate.email, verified=True, primary=True)
        Role.objects.get_or_create(name="Owner")
        Role.objects.get_or_create(name="Member")
        runtime_role = connection.ops.quote_name("invite_journey_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {runtime_role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {runtime_role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {runtime_role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {runtime_role}")
            cursor.execute(f"SET LOCAL ROLE {runtime_role}")

        request = RequestFactory().post("/onboarding/company/", HTTP_HOST="testserver")
        request.user = owner
        form = CompanySetupForm(data={"name": "New owner invitation journey"})
        self.assertTrue(form.is_valid(), form.errors)
        workspace, _ = create_onboarding_workspace_from_form(form=form, user=owner, request=request)
        seed_workspace_roles(workspace.pk)
        result = send_onboarding_team_invitations(
            email_addresses=[teammate.email], actor=owner, company=workspace, request=request)
        self.assertEqual(result["invited_count"], 1, result["failed"])
        invitation = result["invitations"][0]
        delivery = Delivery.objects.get(invitation=invitation)
        self.assertEqual(delivery.status, Delivery.Status.QUEUED)
        self.assertFalse(Membership.objects.filter(company=workspace, user=teammate).exists())

        with patch("apps.platform_mail.transport.send_ses", return_value="journey-provider-id") as send, \
                patch("apps.platform_mail.management.commands.dispatch_platform_mail.time.sleep"):
            call_command("dispatch_platform_mail", send=True, invitations_only=True,
                         limit=1, stdout=StringIO())
            call_command("dispatch_platform_mail", send=True, invitations_only=True,
                         limit=1, stdout=StringIO())
        send.assert_called_once()
        self.assertEqual(Attempt.objects.filter(delivery=delivery).count(), 1)
        request.user = teammate
        accept_invitation(invitation=invitation, user=teammate, request=request)
        self.assertTrue(Membership.objects.filter(company=workspace, user=teammate).exists())
        self.assertEqual(workspace_activity(workspace).mode, "recovery")
        self.assertFalse(Subscription.objects.filter(company=workspace).exists())
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(Payment.objects.exists())
