"""Public consent, private catalog isolation and trial access boundaries."""
from datetime import timedelta
import uuid

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.onboarding.models import OnboardingProgress
from apps.orgs.models import Company, CompanyInvitation, Membership, Role
from apps.orgs.services.control_plane import (
    create_membership, send_onboarding_team_invitations, transfer_workspace_ownership,
)
from apps.orgs.services.workspace_roles import seed_workspace_roles
from apps.tenancy.context import workspace_context
from .access_policy import workspace_activity
from .entitlements import limit
from .models import (
    Invoice, Payment, Plan, RecurringAgreement, RecurringPlanBinding,
    Subscription, SubscriptionEvent, WorkspaceAccessDecision,
)
from .public_trial import PUBLIC_TRIAL_TERMS, start_public_trial


@override_settings(
    BILLING_ALLOW_TRIAL_START=True, BILLING_CHECKOUT_ENABLED=False,
    BILLING_RECURRING_ENABLED=False, PLATFORM_EMAIL_ENABLED=False,
    STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}},
)
class PublicTrialTests(TestCase):
    def setUp(self):
        # The HTTP and service journeys run under a non-bypass runtime role.
        role = connection.ops.quote_name("public_trial_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        self.owner = get_user_model().objects.create_user(username="public-owner", email="owner@example.com")
        EmailAddress.objects.create(user=self.owner, email=self.owner.email, verified=True, primary=True)
        self.workspace = Company.all_objects.create(name="Public trial", schema_name="public-trial",
                                                   owner=self.owner, creator=self.owner)
        Membership.objects.create(company=self.workspace, user=self.owner,
                                  role=Role.objects.get_or_create(name="Owner")[0])
        Role.objects.get_or_create(name="Member")
        seed_workspace_roles(self.workspace.pk)
        self.plan = Plan.objects.create(name="Rokkad 30-day trial", tier="starter", price=0,
                                       trial_days=30, max_users=6)
        self.private = Plan.objects.create(name="PRIVATE paid plan", tier="starter", price=1499,
                                          trial_days=14, max_users=5)
        selected = override_settings(BILLING_PUBLIC_TRIAL_PLAN_ID=self.plan.pk)
        selected.enable()
        self.addCleanup(selected.disable)
        self.client.force_login(self.owner)

    def url(self, name, **kwargs):
        return reverse("workspace_subscriptions:" + name,
                       kwargs={"workspace_slug": self.workspace.slug, **kwargs})

    def start(self, **kwargs):
        with workspace_context(self.workspace.pk):
            return start_public_trial(workspace=self.workspace, actor=kwargs.pop("actor", self.owner),
                plan_id=kwargs.pop("plan_id", self.plan.pk),
                accepted_terms=kwargs.pop("accepted_terms", PUBLIC_TRIAL_TERMS))

    def test_offer_and_post_hide_private_plans_and_require_current_consent(self):
        page = self.client.get(self.url("plan-list"))
        for text in ("30 days", "No automatic charge", "five staff", "1,499/month",
                     "One free trial Workspace per owner account"):
            self.assertContains(page, text)
        for text in (self.private.name, "/year", "/checkout/"):
            self.assertNotContains(page, text)
        self.assertEqual(list(page.context["plans"]), [])
        for plan_id, consent in ((self.private.pk, PUBLIC_TRIAL_TERMS), (self.plan.pk, ""),
                                 (self.plan.pk, "old-terms"),
                                 (self.plan.pk, "public-trial-30d-6members-20260929")):
            response = self.client.post(self.url("start-trial", plan_id=plan_id), {"accepted_terms": consent})
            self.assertEqual(response.status_code, 302)
            self.assertFalse(Subscription.objects.exists())
        self.assertEqual(self.client.get(self.url("start-trial", plan_id=self.plan.pk)).status_code, 405)

    def test_unselected_disabled_changed_or_bound_offer_fails_closed(self):
        for settings in ({"BILLING_PUBLIC_TRIAL_PLAN_ID": 0}, {"BILLING_ALLOW_TRIAL_START": False}):
            with override_settings(**settings):
                with self.assertRaises(ValidationError):
                    self.start()
                self.assertNotContains(self.client.get(self.url("plan-list")), "Start 30-day")
        for field, changed in (("max_users", 5), ("trial_days", 14), ("price", 1499), ("is_active", False)):
            original = getattr(self.plan, field)
            Plan.objects.filter(pk=self.plan.pk).update(**{field: changed})
            with self.assertRaises(ValidationError):
                self.start()
            Plan.objects.filter(pk=self.plan.pk).update(**{field: original})
        RecurringPlanBinding.objects.create(plan=self.plan, actor=self.owner, mode="test",
            provider_plan_id="plan_trial_denied", snapshot={}, reason="Test bound-plan rejection")
        with self.assertRaises(ValidationError):
            self.start()
        self.assertFalse(Subscription.objects.exists())

    def test_verified_canonical_owner_and_active_workspace_required(self):
        other = get_user_model().objects.create_user(username="other-owner", email="other@example.com")
        with self.assertRaises(PermissionDenied):
            self.start(actor=other)
        other.is_superuser = True
        other.is_staff = True
        other.save()
        with self.assertRaises(PermissionDenied):
            self.start(actor=other)
        EmailAddress.objects.filter(user=self.owner).update(verified=False)
        with self.assertRaisesMessage(ValidationError, "Verify"):
            self.start()
        EmailAddress.objects.filter(user=self.owner).update(verified=True)
        for state in ("SUSPENDED", "ARCHIVED", "DELETION_PENDING"):
            Company.all_objects.filter(pk=self.workspace.pk).update(lifecycle_state=state)
            with self.assertRaises((ValidationError, PermissionDenied)):
                self.start()
        self.assertFalse(Subscription.objects.exists())

    def test_trial_freezes_terms_dates_and_capacity_without_payment(self):
        sub = self.start()
        before = Subscription.objects.values().get(pk=sub.pk)
        self.assertAlmostEqual((sub.trial_end_date - sub.start_date).total_seconds(), 30 * 86400, delta=1)
        self.assertFalse(sub.auto_renew)
        self.assertIsNone(sub.razorpay_subscription_id)
        event = SubscriptionEvent.objects.get(subscription=sub)
        self.assertEqual(event.payload["accepted_terms"]["version"], PUBLIC_TRIAL_TERMS)
        self.assertEqual(event.payload["accepted_terms"]["max_trial_workspaces_per_owner"], 1)
        self.assertEqual(event.payload["actor_id"], self.owner.pk)
        self.assertEqual(event.payload["trial_end_date"], sub.trial_end_date.isoformat())
        with self.assertRaises(ValidationError):
            self.start()
        Plan.objects.filter(pk=self.plan.pk).update(trial_days=90, max_users=99)
        with workspace_context(self.workspace.pk):
            self.assertEqual(limit(self.workspace, "workspace.max_members"), 6)
        self.assertEqual(Subscription.objects.values().get(pk=sub.pk), before)
        self.assertEqual(workspace_activity(self.workspace, at=sub.trial_end_date - timedelta(seconds=1)).mode, "full")
        self.assertEqual(workspace_activity(self.workspace, at=sub.trial_end_date + timedelta(seconds=1)).mode, "grace")
        self.assertEqual(workspace_activity(self.workspace, at=sub.trial_end_date + timedelta(days=7)).mode, "read_only")
        dashboard = self.client.get(self.url("dashboard"))
        self.assertContains(dashboard, "Read-only access begins")
        self.assertNotContains(dashboard, "14 days free")
        self.assertEqual(SubscriptionEvent.objects.count(), 1)
        for model in (Invoice, Payment, RecurringAgreement):
            self.assertFalse(model.objects.exists())

    def test_owner_plus_five_pending_invites_fit_and_sixth_staff_is_refused(self):
        self.start()
        result = send_onboarding_team_invitations(actor=self.owner, company=self.workspace, request=None,
            email_addresses=[f"staff{i}@example.com" for i in range(6)])
        self.assertEqual(result["invited_count"], 5, result["failed"])
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(CompanyInvitation.pending_queryset().filter(company=self.workspace).count(), 5)

    def extra_workspace(self, name, owner=None):
        owner = owner or self.owner
        workspace = Company.all_objects.create(name=name, schema_name=name, owner=owner, creator=owner)
        Membership.objects.create(company=workspace, user=owner, role=Role.objects.get(name="Owner"))
        seed_workspace_roles(workspace.pk)
        return workspace

    def test_second_workspace_rejects_direct_post_and_hides_start_action(self):
        first = self.start()
        before = Subscription.objects.values().get(pk=first.pk)
        second = self.extra_workspace("second-trial")
        url = lambda name, **kw: reverse("workspace_subscriptions:" + name,
            kwargs={"workspace_slug": second.slug, **kw})
        page = self.client.get(url("plan-list"))
        self.assertContains(page, "already used its public trial")
        self.assertNotContains(page, "Start 30-day free trial")
        response = self.client.post(url("start-trial", plan_id=self.plan.pk),
            {"accepted_terms": PUBLIC_TRIAL_TERMS})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Subscription.objects.filter(company=second).exists())
        self.assertEqual(Subscription.objects.values().get(pk=first.pk), before)
        self.assertEqual(SubscriptionEvent.objects.count(), 1)

    def test_expiry_transfer_and_new_catalog_do_not_restore_original_owner_trial(self):
        sub = self.start()
        new_owner = get_user_model().objects.create_user(username="successor", email="successor@example.com")
        EmailAddress.objects.create(user=new_owner, email=new_owner.email, verified=True)
        Membership.objects.create(company=self.workspace, user=new_owner, role=Role.objects.get(name="Member"))
        transfer_workspace_ownership(workspace=self.workspace, new_owner=new_owner, actor=self.owner,
            previous_owner_role=Role.objects.get(name="Member"), reason="Trial ownership regression")
        Subscription.objects.filter(pk=sub.pk).update(status=Subscription.StatusChoices.EXPIRED,
            trial_end_date=timezone.now() - timedelta(days=8))
        replacement = Plan.objects.create(name="Replacement public offer", tier="starter", price=0,
            trial_days=30, max_users=6)
        second = self.extra_workspace("after-transfer")
        with override_settings(BILLING_PUBLIC_TRIAL_PLAN_ID=replacement.pk), workspace_context(second.pk):
            with self.assertRaisesMessage(ValidationError, "already used"):
                start_public_trial(workspace=second, actor=self.owner, plan_id=replacement.pk,
                    accepted_terms=PUBLIC_TRIAL_TERMS)
        # Receiving ownership does not consume the recipient's own trial allowance.
        third = self.extra_workspace("successor-trial", new_owner)
        with workspace_context(third.pk):
            start_public_trial(workspace=third, actor=new_owner, plan_id=self.plan.pk,
                accepted_terms=PUBLIC_TRIAL_TERMS)
        self.assertEqual(Subscription.objects.count(), 2)

    def test_earlier_public_terms_count_but_internal_trials_do_not(self):
        from .billing import start_trial
        other = self.extra_workspace("internal-history")
        with workspace_context(other.pk):
            internal = start_trial(workspace=other, plan=self.private, actor=self.owner)
        public = self.start()
        self.assertNotIn("accepted_terms", SubscriptionEvent.objects.get(subscription=internal).payload)
        event = SubscriptionEvent.objects.get(subscription=public)
        event.payload["accepted_terms"] = {"version": "public-trial-30d-6members-20260929"}
        event.save(update_fields=["payload"])  # Simulate retained pre-limit public evidence.
        second = self.extra_workspace("legacy-public-history")
        with workspace_context(second.pk), self.assertRaisesMessage(ValidationError, "already used"):
            start_public_trial(workspace=second, actor=self.owner, plan_id=self.plan.pk,
                accepted_terms=PUBLIC_TRIAL_TERMS)

    def test_rolled_back_start_does_not_consume_owner_allowance(self):
        with self.assertRaisesMessage(RuntimeError, "abort"):
            with transaction.atomic():
                self.start()
                raise RuntimeError("abort")
        self.assertFalse(SubscriptionEvent.objects.exists())
        self.start()
        self.assertEqual(SubscriptionEvent.objects.count(), 1)

    def test_existing_trial_or_access_history_is_unchanged(self):
        old = Subscription.objects.create(company=self.workspace, plan=self.private)
        before = Subscription.objects.values().get(pk=old.pk)
        with self.assertRaises(ValidationError):
            self.start()
        self.assertEqual(Subscription.objects.values().get(pk=old.pk), before)
        self.assertNotContains(self.client.get(self.url("plan-list")), "Start 30-day")
        old.delete()
        WorkspaceAccessDecision.objects.create(workspace=self.workspace, mode="full", actor=self.owner,
            reason="Existing access fixture", expires_at=timezone.now() + timedelta(days=1))
        with self.assertRaises(ValidationError):
            self.start()
        self.assertFalse(Subscription.objects.exists())

    def test_direct_member_addition_respects_reserved_seats_and_existing_member_retry(self):
        self.start()
        result = send_onboarding_team_invitations(actor=self.owner, company=self.workspace, request=None,
            email_addresses=[f"pending{i}@example.com" for i in range(5)])
        self.assertEqual(result["invited_count"], 5)
        member = get_user_model().objects.create_user(username="seventh-person")
        with self.assertRaisesMessage(ValidationError, "seat limit reached"):
            create_membership(user=member, company=self.workspace, role=Role.objects.get(name="Member"),
                              actor=self.owner, request=None)
        membership, created = create_membership(user=self.owner, company=self.workspace,
            role=Role.objects.get(name="Owner"), actor=self.owner, request=None)
        self.assertFalse(created)
        self.assertEqual(membership.user_id, self.owner.pk)

    def test_overcapacity_and_missing_workspace_context_cannot_start_trial(self):
        with self.assertRaises(PermissionDenied):
            start_public_trial(workspace=self.workspace, actor=self.owner, plan_id=self.plan.pk,
                               accepted_terms=PUBLIC_TRIAL_TERMS)
        for index in range(6):
            user = get_user_model().objects.create_user(username=f"existing-staff{index}")
            Membership.objects.create(company=self.workspace, user=user, role=Role.objects.get(name="Member"))
        with self.assertRaisesMessage(ValidationError, "five staff"):
            self.start()
        self.assertFalse(Subscription.objects.exists())

    def test_fresh_onboarding_routes_to_consent_then_team(self):
        self.owner.profile.set_workspace(self.workspace)
        progress, _ = OnboardingProgress.objects.update_or_create(user=self.owner,
            defaults={"profile_completed": True, "current_step": 2, "company_created": False})
        response = self.client.post(reverse("onboarding_company"), {"name": "Fresh trial onboarding"})
        fresh = Company.all_objects.get(name="Fresh trial onboarding")
        self.assertRedirects(response, reverse("workspace_subscriptions:plan-list",
            kwargs={"workspace_slug": fresh.slug}), fetch_redirect_response=False)
        self.assertFalse(Subscription.objects.filter(company=fresh).exists())
        response = self.client.post(reverse("workspace_subscriptions:start-trial",
            kwargs={"workspace_slug": fresh.slug, "plan_id": self.plan.pk}), {"accepted_terms": PUBLIC_TRIAL_TERMS})
        self.assertRedirects(response, reverse("onboarding_team"), fetch_redirect_response=False)
        self.assertEqual(Subscription.objects.get(company=fresh).plan_id, self.plan.pk)
        progress.refresh_from_db()
        self.assertTrue(progress.company_created)


@override_settings(BILLING_ALLOW_TRIAL_START=True, PLATFORM_EMAIL_ENABLED=False)
class ConcurrentPublicTrialTests(TransactionTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="concurrent-trial", email="owner@example.com")
        EmailAddress.objects.create(user=self.owner, email=self.owner.email, verified=True)
        self.workspace = Company.all_objects.create(name="Concurrent trial", schema_name="concurrent-trial",
            owner=self.owner, creator=self.owner)
        Membership.objects.create(company=self.workspace, user=self.owner,
            role=Role.objects.get_or_create(name="Owner")[0])
        Role.objects.get_or_create(name="Member")
        seed_workspace_roles(self.workspace.pk)
        self.plan = Plan.objects.create(name="Concurrent trial", tier="starter", price=0, trial_days=30, max_users=6)
        selected = override_settings(BILLING_PUBLIC_TRIAL_PLAN_ID=self.plan.pk)
        selected.enable()
        self.addCleanup(selected.disable)
        self.role = connection.ops.quote_name("trial_race_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {self.role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {self.role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {self.role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {self.role}")
        self.addCleanup(self.drop_role)

    def drop_role(self):
        with connection.cursor() as cursor:
            cursor.execute(f"DROP OWNED BY {self.role}")
            cursor.execute(f"DROP ROLE {self.role}")

    def race(self, action, *, workspaces=None):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections
        ready = Barrier(2)

        def run(index):
            close_old_connections()
            try:
                ready.wait(timeout=10)
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(f"SET LOCAL ROLE {self.role}")
                    workspace = workspaces[index] if workspaces else self.workspace
                    with workspace_context(workspace.pk):
                        return action(index)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run, range(2)))

    def test_concurrent_acceptance_creates_one_trial_then_reserves_one_last_seat(self):
        def accept(_):
            try:
                start_public_trial(workspace=self.workspace, actor=self.owner,
                    plan_id=self.plan.pk, accepted_terms=PUBLIC_TRIAL_TERMS)
                return "started"
            except ValidationError:
                return "rejected"

        self.assertCountEqual(self.race(accept), ["started", "rejected"])
        self.assertEqual(Subscription.objects.filter(company=self.workspace).count(), 1)
        self.assertEqual(SubscriptionEvent.objects.filter(event_type="trial.started").count(), 1)
        result = send_onboarding_team_invitations(actor=self.owner, company=self.workspace, request=None,
            email_addresses=[f"reserved{i}@example.com" for i in range(4)])
        self.assertEqual(result["invited_count"], 4)

        def invite(index):
            result = send_onboarding_team_invitations(actor=self.owner, company=self.workspace, request=None,
                email_addresses=[f"lastseat{index}@example.com"])
            return result["invited_count"]

        self.assertCountEqual(self.race(invite), [1, 0])
        self.assertEqual(CompanyInvitation.pending_queryset().filter(company=self.workspace).count(), 5)

    def test_concurrent_different_workspaces_consume_one_owner_trial(self):
        second = Company.all_objects.create(name="Competing trial", schema_name="competing-trial",
            owner=self.owner, creator=self.owner)
        Membership.objects.create(company=second, user=self.owner, role=Role.objects.get(name="Owner"))
        seed_workspace_roles(second.pk)
        workspaces = (self.workspace, second)

        def accept(index):
            workspace = workspaces[index]
            try:
                start_public_trial(workspace=workspace, actor=self.owner,
                    plan_id=self.plan.pk, accepted_terms=PUBLIC_TRIAL_TERMS)
                return "started"
            except ValidationError as exc:
                self.assertIn("already used", exc.messages[0])
                return "rejected"

        self.assertCountEqual(self.race(accept, workspaces=workspaces), ["started", "rejected"])
        self.assertEqual(Subscription.objects.count(), 1)
        self.assertEqual(SubscriptionEvent.objects.filter(event_type="trial.started").count(), 1)
        for model in (Invoice, Payment, RecurringAgreement):
            self.assertFalse(model.objects.exists())
