"""Existing accounts and tenant boundaries survive the guided handoffs."""
from uuid import uuid4
from urllib.parse import parse_qs, urlsplit

from allauth.account import app_settings
from allauth.account.models import EmailAddress, EmailConfirmationHMAC
from allauth.account.app_settings import LoginMethod
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from apps.orgs.middleware_v2 import SecureWorkspaceMiddleware
from apps.orgs.models import Company, Domain
from apps.onboarding.services.account_journey import account_journey, owner_setup_workspace
from apps.subscriptions.models import Invoice, Payment, Plan, Subscription
from apps.subscriptions.public_trial import PUBLIC_TRIAL_TERMS


@override_settings(
    ACCOUNT_EMAIL_ENABLED=False, PLATFORM_EMAIL_ENABLED=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    BILLING_ALLOW_TRIAL_START=True, BILLING_CHECKOUT_ENABLED=False,
    BILLING_RECURRING_ENABLED=False,
    ALLOWED_HOSTS=["testserver", "owned.example.test"],
    STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
)
class AccountJourneyTests(TestCase):
    def setUp(self):
        cache.clear()
        role = connection.ops.quote_name("account_journey_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        self.password = "Fictional-Counter-Password-8174!"
        self.owner = get_user_model().objects.create_user(username="existing-counter-owner",
            email="owner@example.test", password=self.password)
        self.address = EmailAddress.objects.create(user=self.owner, email=self.owner.email, primary=True)
        self.plan = Plan.objects.create(name="Journey public trial", tier="starter", price=0,
            yearly_price=0, trial_days=30, max_users=6)
        self.enterContext(override_settings(BILLING_PUBLIC_TRIAL_PLAN_ID=self.plan.pk))

    def business(self, name="Journey first business"):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("app_workspace_create"), {"name":name, "theme":""})
        self.assertEqual(response.status_code, 302)
        workspace = Company.all_objects.get(name=name)
        self.assertEqual(response.url, reverse("workspace_slug_settings_setup", args=[workspace.slug]))
        self.owner.refresh_from_db()
        return workspace

    def trial_url(self, workspace, name="start-trial"):
        kwargs = {"workspace_slug": workspace.slug}
        if name == "start-trial":
            kwargs["plan_id"] = self.plan.pk
        return reverse("workspace_subscriptions:" + name, kwargs=kwargs)

    def test_email_and_username_signin_preserve_existing_account_and_safe_next(self):
        self.assertEqual(set(app_settings.LOGIN_METHODS), {LoginMethod.EMAIL, LoginMethod.USERNAME})
        for identifier in (self.owner.username, self.owner.email, self.owner.email.upper()):
            with self.subTest(identifier=identifier):
                client = Client()
                response = client.post(reverse("account_login"), {"login":identifier,
                    "password":self.password, "next":reverse("app_workspaces")})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, reverse("app_workspaces"))
                self.assertEqual(int(client.session["_auth_user_id"]), self.owner.pk)
        response = Client().post(reverse("account_login"), {"login":self.owner.email,
            "password":self.password, "next":"https://evil.invalid/"})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("evil.invalid", response.url)
        self.assertFalse(Company.all_objects.exists())
        self.assertFalse(Subscription.objects.exists())

    def test_inactive_account_and_wrong_password_still_cannot_sign_in(self):
        response = self.client.post(reverse("account_login"), {"login":self.owner.email,"password":"wrong"})
        self.assertNotIn("_auth_user_id", self.client.session)
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.client.post(reverse("account_login"), {"login":self.owner.username,"password":self.password})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_public_contact_is_exact_and_does_not_make_tenant_domain_public(self):
        for authenticated in (False, True):
            if authenticated:
                self.client.force_login(self.owner)
            response = self.client.get(reverse("contact"))
            self.assertContains(response, "support@rokkad.com", msg_prefix=f"auth={authenticated} path={reverse('contact')} location={response.get('Location')}")
            self.assertIsNone(response.wsgi_request.workspace)
        middleware = SecureWorkspaceMiddleware(lambda request: None)
        self.assertTrue(middleware._requires_workspace("/contact/private/"))
        workspace = self.business()
        Domain.objects.create(domain="owned.example.test", tenant=workspace)
        response = Client().get(reverse("contact"), HTTP_HOST="owned.example.test")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("account_login")))

    def test_signup_has_verification_next_step_without_starting_trial(self):
        response = self.client.post(reverse("account_signup"), {"username":"new-owner",
            "email":"new-owner@example.test", "password1":self.password}, follow=True)
        self.assertContains(response,"Verify your account email")
        self.assertContains(response,"Set up your first business")
        self.assertNotContains(response,"mgmt-summary-tile")
        self.assertNotContains(response,"Account overview")
        self.assertContains(response, reverse("app_invitations"))
        self.assertFalse(EmailAddress.objects.get(email="new-owner@example.test").verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(Subscription.objects.exists())
        self.assertFalse(Company.all_objects.exists())

    def test_unverified_trial_offer_has_recovery_link_and_server_still_refuses(self):
        workspace = self.business()
        page = self.client.get(self.trial_url(workspace,"plan-list"))
        self.assertContains(page,"Verify email or re-send the link")
        self.assertContains(page,"setup_workspace=" + workspace.slug)
        self.assertNotContains(page,'id="accept-public-trial"')
        self.client.post(self.trial_url(workspace),{"accepted_terms":PUBLIC_TRIAL_TERMS})
        self.assertFalse(Subscription.objects.exists())

    def test_verification_returns_to_requested_owned_business_despite_preference_change(self):
        first = self.business("First journey business")
        second = self.business("Second journey business")
        response = self.client.post(reverse("account_email"), {"email":self.owner.email,
            "action_send":"", "setup_workspace":first.slug})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.client.session["onboarding_verification_return"]["workspace_id"],first.pk)
        key = EmailConfirmationHMAC(self.address).key
        response = self.client.post(reverse("account_confirm_email",args=[key]))
        self.assertEqual(response.url,reverse("workspace_slug_settings_setup",args=[first.slug]))
        self.assertNotIn("onboarding_verification_return",self.client.session)
        self.address.refresh_from_db()
        self.assertTrue(self.address.verified)
        self.owner.profile.refresh_from_db()
        self.assertEqual(self.owner.profile.workspace_id,second.pk)

    def test_anonymous_confirmation_requires_login_before_business_return(self):
        workspace = self.business()
        response = Client().post(reverse("account_confirm_email",args=[EmailConfirmationHMAC(self.address).key]))
        parts = urlsplit(response.url)
        self.assertEqual(parts.path,reverse("account_login"))
        self.assertEqual(parse_qs(parts.query)["next"],[reverse("workspace_slug_settings_setup",args=[workspace.slug])])

    def test_navigation_hints_cannot_choose_another_owners_or_suspended_business(self):
        workspace = self.business()
        other = get_user_model().objects.create_user(username="other-owner",email="other@example.test")
        self.assertIsNone(owner_setup_workspace(other,slug=workspace.slug))
        self.assertIsNone(owner_setup_workspace(other,remembered={"user_id":other.pk,"workspace_id":workspace.pk}))
        self.assertIsNone(owner_setup_workspace(self.owner,slug="https://evil.invalid"))
        Company.all_objects.filter(pk=workspace.pk).update(lifecycle_state="SUSPENDED")
        self.assertIsNone(owner_setup_workspace(self.owner,remembered={"user_id":self.owner.pk,"workspace_id":workspace.pk}))

    def test_trial_keeps_consent_scope_and_returns_to_guided_review_without_payment(self):
        workspace = self.business()
        self.address.verified = True
        self.address.save(update_fields=["verified"])
        markers = {"setup_step":"review","setup_path":"paper","next":"https://evil.invalid"}
        response = self.client.post(self.trial_url(workspace),markers)
        self.assertFalse(Subscription.objects.exists())
        self.assertIn("setup_step=review",response.url)
        response = self.client.post(self.trial_url(workspace),{**markers,"accepted_terms":PUBLIC_TRIAL_TERMS})
        self.assertEqual(response.url,reverse("workspace_slug_settings_setup",args=[workspace.slug])+"?step=review&path=paper")
        self.assertEqual(Subscription.objects.count(),1)
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(Payment.objects.exists())

    def test_existing_workspace_manager_and_password_recovery_remain_available(self):
        workspace = self.business()
        page = self.client.get(reverse("app_workspaces"))
        self.assertContains(page,"mgmt-summary-tile")
        self.assertContains(page,"Archived Workspaces")
        self.assertContains(page,workspace.name)
        response = Client().post(reverse("account_reset_password"),{"email":self.owner.email},follow=True)
        self.assertContains(response,"Check your email")
        self.assertEqual(len(mail.outbox),1)
        self.assertFalse(Subscription.objects.exists())
