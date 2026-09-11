from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.orgs.models import Membership
from .models import OnboardingChoice, OnboardingProgress


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class TourPreferenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="tour-owner")
        self.progress, _ = OnboardingProgress.objects.get_or_create(user=self.user)
        self.progress.company_created = True
        self.progress.save(update_fields=["company_created"])
        self.old = OnboardingChoice.objects.create(progress=self.progress, step=4,
            choice_key="interested_features", choice_value="girvi,dea,contact")
        self.client.force_login(self.user)

    def test_current_choices_render_without_retired_product_promises(self):
        response = self.client.get("/onboarding/tour/")
        self.assertEqual(response.status_code, 200)
        for text in ("Loans and Collateral", "Borrower Profiles", "Reference Rates", "Notifications and Reminders"):
            self.assertContains(response, text)
        for text in ("Accounting/Ledger", "Loan/Girvi", "Sales &amp; Invoicing", "Purchase Management"):
            self.assertNotContains(response, text)

    def test_new_preferences_preserve_history_and_do_not_grant_roles(self):
        response = self.client.post("/onboarding/tour/", {
            "primary_role": "staff", "interested_features": ["loans", "party", "rates", "notify_v2"],
        })
        self.assertEqual(response.status_code, 302)
        self.progress.refresh_from_db()
        self.assertTrue(self.progress.tour_completed)
        self.old.refresh_from_db()
        self.assertEqual(self.old.choice_value, "girvi,dea,contact")
        self.assertTrue(OnboardingChoice.objects.filter(progress=self.progress, choice_value="loans,party,rates,notify_v2").exists())
        self.assertFalse(Membership.objects.filter(user=self.user).exists())

    def test_retired_submission_requires_new_selection_without_losing_history(self):
        response = self.client.post("/onboarding/tour/", {"interested_features": ["dea"]})
        self.assertEqual(response.status_code, 200)
        self.progress.refresh_from_db()
        self.assertFalse(self.progress.tour_completed)
        self.assertEqual(OnboardingChoice.objects.filter(progress=self.progress).count(), 1)
