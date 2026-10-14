"""Fictional dated policy only; never supplies live tariffs or transport credentials."""
from datetime import timedelta
from django.utils import timezone


def fixture_pilot(fixture, **changes):
    now = timezone.now()
    value = {"version": "fictional-pw04-1", "starts_at": (now-timedelta(days=1)).isoformat(),
        "ends_at": (now+timedelta(days=30)).isoformat(),
        "cohort": [{"workspace_id": fixture.ws.pk, "owner_id": fixture.owner.pk},
            {"workspace_id": fixture.foreign.pk, "owner_id": fixture.other.pk},
            # Exact future fictional IDs for PW-03's second-owner-Workspace regression.
            {"workspace_id": fixture.foreign.pk+1, "owner_id": fixture.owner.pk}],
        "purposes": ["setup", "trial", "paid", "ending", "service"], "platform_limit": 100,
        "contact_limit": 5, "daily_spend_inr": "100.000000",
        "tariff": {"revision": "fictional-not-a-provider-rate", "effective_from": (now-timedelta(days=1)).date().isoformat(),
            "effective_until": (now+timedelta(days=30)).date().isoformat(),
            "source_url": "https://whatsappbusiness.com/products/platform-pricing/", "currency": "INR", "market": "IN",
            "rates": {"utility": "0.100000", "marketing": "0.300000", "authentication": "0.200000",
                "authentication_international": "0.400000", "service": "0.000000"}}}
    return {**value, **changes}

from copy import deepcopy
from datetime import datetime, time
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command, CommandError
from django.db import DatabaseError, transaction
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from apps.orgs.models import Company
from apps.subscriptions.models import Plan, Subscription, SubscriptionEvent, WorkspaceAccessDecision
from apps.subscriptions.access_policy import record_access_decision
from apps.tenancy.context import workspace_context
from .test_dispatch import DispatchFixture
from .test_transport import SEND
from .test_intents import STORAGE
from .test_receipts import status_payload, status_fact
from .models import Delivery, TrialReminder, Announcement, AnnouncementTarget, BudgetDay, ContactDay, Reservation, CostEvidence, Attempt
from .intents import confirm_setup, review_setup, _capture_trial_started, preview_delivery, TEMPLATE_REVISION
from .controls import gate, pilot, next_window, ZONE
from .reminders import queue_trial_reminder
from .announcements import review_announcement, confirm_announcement
from .services import change_contact

SEND4 = {**SEND, "PLATFORM_WHATSAPP_TEMPLATES": {**SEND["PLATFORM_WHATSAPP_TEMPLATES"],
    **{p: {"name": "fictional_"+p, "language": "en", "revision": TEMPLATE_REVISION, "approved": True} for p in ("ending", "service")}}}


@override_settings(**SEND4, STORAGES=STORAGE)
class ControlTests(DispatchFixture, TransactionTestCase):
    def selected(self, **changes):
        return override_settings(PLATFORM_WHATSAPP_PILOT=fixture_pilot(self, **changes))

    def second(self):
        workspace = self.make_workspace("pw04-other-owned", self.owner)
        self.consent(self.contact, workspace=workspace)
        return self.source(workspace=workspace)

    def trial(self, days=2):
        from apps.subscriptions.billing import start_trial
        from apps.subscriptions.public_trial import PUBLIC_TRIAL_TERMS
        plan = Plan.objects.create(name="Fictional reminder",tier="starter",price=0,trial_days=days,max_users=6)
        sub = start_trial(workspace=self.ws,plan=plan,actor=self.owner,accepted_terms=PUBLIC_TRIAL_TERMS)
        event = SubscriptionEvent.objects.get(subscription=sub,event_type="trial.started")
        return sub,event

    def spec(self, **changes):
        now = timezone.now()
        return {"purpose": "maintenance", "text": "Rokkad will undergo scheduled service maintenance.",
            "revision": "fictional-notice-1", "impact_start": (now+timedelta(hours=1)).isoformat(),
            "impact_end": (now+timedelta(hours=4)).isoformat(), "expires_at": (now+timedelta(hours=3)).isoformat(),
            "urgent": False, "workspace_ids": [self.ws.pk], **changes}

    def notice(self, **changes):
        self.consent(self.contact,service=True)
        review = review_announcement(actor=self.admin,spec=self.spec(**changes))
        source = confirm_announcement(actor=self.admin,token=review["token"])
        with workspace_context(self.ws.pk):
            return source,Delivery.objects.select_related("announcement_target__announcement", "workspace__owner").get(announcement_target__announcement=source)

    def test_private_pilot_inputs_are_strict_dated_and_bounded(self):
        for changes in ({"platform_limit": 101}, {"contact_limit": 6}, {"platform_limit": True},
            {"daily_spend_inr": "NaN"}, {"daily_spend_inr": "0"}, {"cohort": []},
            {"purposes": ["collection"]}, {"ends_at": (timezone.now()-timedelta(seconds=1)).isoformat()}):
            with self.subTest(changes=changes),self.selected(**changes),self.assertRaises(ValidationError):
                pilot()
        values=fixture_pilot(self)
        values["tariff"]["rates"].pop("marketing")
        with override_settings(PLATFORM_WHATSAPP_PILOT=values),self.assertRaises(ValidationError):
            pilot()

    def test_new_intents_require_separate_enable_and_never_promote_captures(self):
        row=self.source(capture=True)
        with override_settings(PLATFORM_WHATSAPP_INTENTS_ENABLED=True):
            repeat=confirm_setup(actor=self.owner,token=review_setup(actor=self.owner,workspace_slug=self.ws.slug)["token"])
            second_ws=self.make_workspace("pw04-next",self.owner)
            self.consent(self.contact,workspace=second_ws)
            new=confirm_setup(actor=self.owner,token=review_setup(actor=self.owner,workspace_slug=second_ws.slug)["token"])
        self.assertTrue(repeat.capture_only)
        self.assertFalse(new.capture_only)
        with workspace_context(row.workspace_id):
            row.refresh_from_db()
        self.assertTrue(row.capture_only)

    def test_named_pilot_and_purpose_rechecked_before_reservation(self):
        row=self.source()
        for changes in ({"cohort": [{"workspace_id": self.ws.pk,"owner_id": self.other.pk}]}, {"purposes": ["paid"]}):
            with self.selected(**changes),self.assertRaises(ValidationError):
                self.dispatch(row)
        self.assertFalse(BudgetDay.objects.exists())
        self.send.assert_not_called()

    def test_sources_before_pilot_start_cannot_become_new_live_intents(self):
        row=self.source()
        with self.selected(starts_at=(timezone.now()+timedelta(seconds=1)).isoformat()),self.assertRaises(ValidationError):
            self.dispatch(row)
        self.assertFalse(self.attempts(row))

    def test_quiet_hours_are_local_inclusive_nine_exclusive_eighteen(self):
        row=self.source()
        self.quiet_gate.stop()
        day=timezone.now().astimezone(ZONE).date()+timedelta(days=1)
        for hour,allowed in ((8,False),(9,True),(17,True),(18,False),(23,False)):
            at=datetime.combine(day,time(hour),tzinfo=ZONE)
            with self.subTest(hour=hour):
                if allowed:
                    gate(row,at=at)
                else:
                    with self.assertRaisesMessage(ValidationError,"quiet_hours"):
                        gate(row,at=at)
        self.send.assert_not_called()

    def race(self,first,second):
        def invoke():
            # Give each parallel turn its own distinct candidate.
            import threading
            with self.pick_lock:
                row=self.pick.pop()
            try:
                return self.dispatch(row)
            except ValidationError:
                return "blocked"
        from threading import Lock
        self.pick_lock=Lock();self.pick=[first,second]
        return self.concurrent(invoke)

    def test_contact_count_is_atomic_across_two_workspaces(self):
        first=self.source();second=self.second()
        with self.selected(contact_limit=1):
            result=self.race(first,second)
        self.assertEqual(self.send.call_count,1)
        self.assertEqual(BudgetDay.objects.get().reserved_count,1)
        self.assertEqual(ContactDay.objects.get().reserved_count,1)
        self.assertIn("accepted",result)
        self.assertTrue(set(result) & {"deferred", "expired"})

    def test_spend_reservation_is_atomic_and_uses_largest_category(self):
        first=self.source();second=self.second()
        with self.selected(daily_spend_inr="0.400000"):
            self.race(first,second)
        day=BudgetDay.objects.get()
        self.assertEqual(day.reserved_amount,Decimal("0.400000"))
        self.assertEqual(day.reserved_count,1)
        self.assertEqual(self.send.call_count,1)

    def test_global_count_is_atomic_across_distinct_owners(self):
        first=self.source()
        contact,code=self.enroll(actor=self.other,phone="+919876543211")
        self.consent(contact,actor=self.other,workspace=self.foreign)
        self.post_payload(self.payload(code,phone="919876543211"))
        review=review_setup(actor=self.other,workspace_slug=self.foreign.slug)
        with override_settings(PLATFORM_WHATSAPP_INTENTS_ENABLED=True):
            second=confirm_setup(actor=self.other,token=review["token"])
        with self.selected(platform_limit=1):
            self.race(first,second)
        self.assertEqual(self.send.call_count,1)
        self.assertEqual(BudgetDay.objects.get().reserved_count,1)

    def test_unknown_acceptance_retains_reservation_and_never_resends(self):
        from .transport import TransportFailure
        row=self.source();self.send.side_effect=TransportFailure("provider_connection_uncertain")
        self.assertEqual(self.dispatch(row),"unknown")
        self.assertEqual(self.dispatch(row),"unknown")
        self.assertEqual(BudgetDay.objects.get().reserved_count,1)
        with workspace_context(self.ws.pk):
            self.assertEqual(Reservation.objects.get().amount,Decimal("0.4"))
        self.send.assert_called_once()

    def test_priced_delivery_retains_estimate_without_releasing_reserve(self):
        row=self.source();self.dispatch(row)
        self.post_payload(status_payload(status_fact(message_id="wamid.accepted_fixture",
            pricing={"category":"utility","pricing_model":"PMP","billable":True})))
        self.reconcile(row)
        with workspace_context(self.ws.pk):
            self.assertEqual(CostEvidence.objects.get().amount,Decimal("0.1"))
        day=BudgetDay.objects.get()
        self.assertEqual(day.reserved_amount,Decimal("0.4"));self.assertFalse(day.pricing_hold)

    def test_missing_or_conflicting_pricing_holds_future_sends(self):
        row=self.source();second=self.second();self.dispatch(row)
        self.post_payload(status_payload(status_fact(message_id="wamid.accepted_fixture")))
        self.reconcile(row)
        self.assertTrue(BudgetDay.objects.get().pricing_hold)
        with self.assertRaisesMessage(ValidationError,"unreconciled_pricing_hold"):
            self.dispatch(second)
        self.send.assert_called_once()

    def test_capacity_evidence_is_immutable_and_cannot_be_decremented(self):
        row=self.source();self.dispatch(row)
        with workspace_context(self.ws.pk):
            for mutate in (lambda: Reservation.objects.update(amount=0),lambda:Reservation.objects.all().delete(),
                lambda: BudgetDay.objects.update(reserved_count=0),lambda:ContactDay.objects.update(reserved_count=0)):
                with self.assertRaises(DatabaseError),transaction.atomic():
                    mutate()
        with workspace_context(self.foreign.pk):
            self.assertFalse(Reservation.objects.exists())
        self.assertFalse(Reservation.objects.exists())

    def test_direct_claim_without_reservation_is_database_rejected(self):
        row=self.source()
        with workspace_context(self.ws.pk),self.assertRaises(DatabaseError),transaction.atomic():
            Attempt.objects.create(workspace=self.ws,delivery=row,number=1,phone_id="12345",waba_id="67890",
                sender_fingerprint=row.sender_fingerprint,transport_fingerprint="a"*64,
                content_fingerprint="b"*64,template_name="fictional_setup",language="en")

    def test_changed_policy_after_claim_cancels_without_releasing_capacity(self):
        row=self.source()
        from .dispatch import _before_request
        def changed(*args):
            with self.selected(version="changed"):
                return _before_request(*args)
        with patch("apps.platform_whatsapp.dispatch._before_request",side_effect=changed):
            self.assertEqual(self.dispatch(row),"cancelled")
        self.send.assert_not_called();self.assertEqual(BudgetDay.objects.get().reserved_count,1)

    def test_no_defer_beyond_source_expiry(self):
        row=self.source()
        self.assertIsNone(next_window(row,at=row.expires_at,capacity=True))

    def test_reminder_is_unique_and_does_not_change_subscription(self):
        sub,event=self.trial()
        before=(sub.trial_end_date,sub.status)
        row=queue_trial_reminder(workspace_id=self.ws.pk)
        repeat=queue_trial_reminder(workspace_id=self.ws.pk)
        self.assertEqual(row.pk,repeat.pk);self.assertTrue(row.capture_only)
        sub.refresh_from_db();self.assertEqual(before,(sub.trial_end_date,sub.status))
        with workspace_context(self.ws.pk):
            self.assertEqual(TrialReminder.objects.count(),1)
        self.send.assert_not_called()

    def test_reminder_has_exact_three_local_days_and_no_late_catch_up(self):
        sub,event=self.trial(days=4)
        self.assertIsNone(queue_trial_reminder(workspace_id=self.ws.pk))
        with patch("apps.platform_whatsapp.reminders.timezone.now",return_value=timezone.now()+timedelta(days=1)):
            self.assertIsNotNone(queue_trial_reminder(workspace_id=self.ws.pk))
        with patch("apps.platform_whatsapp.reminders.timezone.now",return_value=sub.trial_end_date):
            self.assertIsNone(queue_trial_reminder(workspace_id=self.ws.pk))

    def test_paid_conversion_and_admin_override_cancel_reminder(self):
        sub,event=self.trial()
        with override_settings(PLATFORM_WHATSAPP_INTENTS_ENABLED=True):
            row=queue_trial_reminder(workspace_id=self.ws.pk)
        record_access_decision(workspace=self.ws,actor=self.admin,mode="full",expires_at=timezone.now()+timedelta(days=10),reason="Fictional access decision")
        with self.assertRaises(ValidationError):
            self.dispatch(row)
        self.assertIsNone(queue_trial_reminder(workspace_id=self.ws.pk))
        record_access_decision(workspace=self.ws,actor=self.admin,mode="default",reason="Return to trial policy")
        Subscription.objects.filter(pk=sub.pk).update(status="active")
        self.assertIsNone(queue_trial_reminder(workspace_id=self.ws.pk))
        self.send.assert_not_called()

    def test_changed_trial_end_never_creates_another_reminder(self):
        sub,event=self.trial()
        with override_settings(PLATFORM_WHATSAPP_INTENTS_ENABLED=True):
            row=queue_trial_reminder(workspace_id=self.ws.pk)
        Subscription.objects.filter(pk=sub.pk).update(trial_end_date=sub.trial_end_date+timedelta(days=1))
        self.assertIsNone(queue_trial_reminder(workspace_id=self.ws.pk))
        with self.assertRaises(ValidationError):
            self.dispatch(row)
        self.send.assert_not_called()

    def test_reminder_command_requires_explicit_bounded_scope_and_never_sends(self):
        self.trial();output=StringIO()
        call_command("queue_platform_whatsapp_reminders",workspace_ids=[self.ws.pk],stdout=output)
        self.assertIn("Workspace",output.getvalue())
        for ids in ([0],[self.ws.pk]*2,list(range(1,102))):
            with self.assertRaises(CommandError):
                call_command("queue_platform_whatsapp_reminders",workspace_ids=ids,stdout=output)
        with transaction.atomic(),self.assertRaises(PermissionDenied):
            queue_trial_reminder(workspace_id=self.ws.pk)
        self.send.assert_not_called()

    def test_announcement_review_get_and_review_are_read_only(self):
        self.client.force_login(self.admin)
        url=reverse("platform_whatsapp_announcements")
        response=self.client.get(url)
        self.assertEqual(response.status_code,200);self.assertIn("no-store",response["Cache-Control"])
        review_announcement(actor=self.admin,spec=self.spec())
        self.assertFalse(Announcement.objects.exists());self.send.assert_not_called()

    def test_announcement_rejects_non_admin_scoped_forged_and_expired_review(self):
        for actor in (self.owner,self.staff):
            with self.assertRaises(PermissionDenied):
                review_announcement(actor=actor,spec=self.spec())
        with workspace_context(self.ws.pk),self.assertRaises(PermissionDenied):
            review_announcement(actor=self.admin,spec=self.spec())
        review=review_announcement(actor=self.admin,spec=self.spec())
        with self.assertRaises(ValidationError):
            confirm_announcement(actor=self.admin,token=review["token"]+"x")
        with patch("django.core.signing.time.time",return_value=__import__('time').time()+601),self.assertRaises(ValidationError):
            confirm_announcement(actor=self.admin,token=review["token"])

    def test_announcement_stale_consent_template_or_cost_review_is_rejected(self):
        self.consent(self.contact,service=True)
        review=review_announcement(actor=self.admin,spec=self.spec())
        self.consent(self.contact,service=False)
        with self.assertRaises(ValidationError):
            confirm_announcement(actor=self.admin,token=review["token"])
        self.consent(self.contact,service=True)
        review=review_announcement(actor=self.admin,spec=self.spec())
        with self.selected(daily_spend_inr="50"),self.assertRaises(ValidationError):
            confirm_announcement(actor=self.admin,token=review["token"])
        with override_settings(PLATFORM_WHATSAPP_TEMPLATES={}),self.assertRaises(ValidationError):
            confirm_announcement(actor=self.admin,token=review["token"])
        self.assertFalse(Announcement.objects.exists())

    def test_announcement_deduplicates_owner_with_scoped_target_evidence_and_replay(self):
        second=self.make_workspace("pw04-second-announcement",self.owner)
        self.consent(self.contact,workspace=second,service=True);self.consent(self.contact,service=True)
        review=review_announcement(actor=self.admin,spec=self.spec(workspace_ids=[self.ws.pk,second.pk]))
        self.assertEqual(review["recipient_count"],1)
        source=confirm_announcement(actor=self.admin,token=review["token"])
        self.assertEqual(confirm_announcement(actor=self.admin,token=review["token"]).pk,source.pk)
        with workspace_context(self.ws.pk):
            self.assertEqual(AnnouncementTarget.objects.count(),1);self.assertEqual(Delivery.objects.count(),1)
        with workspace_context(second.pk):
            self.assertEqual(AnnouncementTarget.objects.count(),1);self.assertFalse(Delivery.objects.exists())
        self.send.assert_not_called()

    def test_announcement_current_review_and_service_consent_required_at_send(self):
        with override_settings(PLATFORM_WHATSAPP_INTENTS_ENABLED=True):
            source,row=self.notice()
        self.assertFalse(row.capture_only)
        self.consent(self.contact,service=False)
        with self.assertRaises(ValidationError):
            self.dispatch(row)
        self.send.assert_not_called()

    def test_urgent_incident_bypasses_only_quiet_hours(self):
        self.quiet_gate.stop()
        with override_settings(PLATFORM_WHATSAPP_INTENTS_ENABLED=True):
            source,row=self.notice(purpose="incident",urgent=True)
        night=timezone.now().astimezone(ZONE).replace(hour=23,minute=30)
        gate(row,at=night)
        with self.selected(purposes=["paid"]),self.assertRaises(ValidationError):
            gate(row,at=night)
        self.assertFalse(BudgetDay.objects.exists())

    def test_notice_http_requires_csrf_review_and_acknowledgement(self):
        from django.test import Client
        self.client.force_login(self.admin);url=reverse("platform_whatsapp_announcements")
        spec=self.spec();data={**spec,"workspace_ids": str(self.ws.pk),"action":"review"}
        response=self.client.post(url,data)
        self.assertEqual(response.status_code,200);self.assertContains(response,"Review service notice")
        token=response.context["review"]["token"]
        self.assertEqual(self.client.post(url,{"action":"confirm","token":token}).status_code,409)
        self.assertEqual(self.client.post(url,{"action":"confirm","token":token,"acknowledged":"on"}).status_code,200)
        self.assertEqual(Announcement.objects.count(),1)
        secure=Client(enforce_csrf_checks=True);secure.force_login(self.admin)
        self.assertEqual(secure.post(url,{"action":"confirm","token":token,"acknowledged":"on"}).status_code,403)

    def test_new_source_tables_have_forced_rls_and_immutable_boundaries(self):
        self.trial();row=queue_trial_reminder(workspace_id=self.ws.pk)
        source,notice=self.notice()
        with workspace_context(self.ws.pk):
            for mutate in (lambda:TrialReminder.objects.update(stage="other"),lambda:AnnouncementTarget.objects.all().delete(),
                lambda:Announcement.objects.update(text="changed")):
                with self.assertRaises(DatabaseError),transaction.atomic():
                    mutate()
        with workspace_context(self.foreign.pk):
            self.assertFalse(TrialReminder.objects.exists());self.assertFalse(AnnouncementTarget.objects.exists())
        self.assertFalse(TrialReminder.objects.exists());self.assertFalse(AnnouncementTarget.objects.exists())

    def test_trial_ending_template_dispatch_uses_actual_saved_end(self):
        sub,event=self.trial()
        with override_settings(PLATFORM_WHATSAPP_INTENTS_ENABLED=True):
            row=queue_trial_reminder(workspace_id=self.ws.pk)
        self.assertFalse(row.capture_only)
        self.assertEqual(self.dispatch(row),"accepted")
        payload=self.send.call_args.args[0]
        self.assertEqual(payload["template"]["name"],"fictional_ending")
        params=payload["template"]["components"][0]["parameters"]
        self.assertIn(timezone.localtime(sub.trial_end_date).strftime("%d %b %Y"),params[1]["text"])
        self.assertEqual(BudgetDay.objects.get().reserved_count,1)

    def test_reviewed_service_template_dispatch_uses_only_reviewed_fields(self):
        with override_settings(PLATFORM_WHATSAPP_INTENTS_ENABLED=True):
            source,row=self.notice()
        self.assertEqual(self.dispatch(row),"accepted")
        payload=self.send.call_args.args[0]
        self.assertEqual(payload["template"]["name"],"fictional_service")
        params=payload["template"]["components"][0]["parameters"]
        self.assertEqual(params[0]["text"],source.text)
        self.assertEqual(params[-1]["text"],"https://example.test/contact/")
        self.assertEqual(len(params),4)

    def test_secondary_represented_workspace_change_blocks_deduplicated_notice(self):
        second=self.make_workspace("pw04-represented",self.owner)
        self.consent(self.contact,workspace=second,service=True)
        with override_settings(PLATFORM_WHATSAPP_INTENTS_ENABLED=True):
            source,row=self.notice(workspace_ids=[self.ws.pk,second.pk])
        self.consent(self.contact,workspace=second,service=False)
        with self.assertRaises(ValidationError):
            self.dispatch(row)
        self.send.assert_not_called()

    def test_pricing_conflict_preserves_both_facts_and_holds_sending(self):
        row=self.source();self.dispatch(row)
        for category in ("utility","marketing"):
            self.post_payload(status_payload(status_fact(message_id="wamid.accepted_fixture",
                pricing={"category":category,"pricing_model":"PMP","billable":True})))
            self.reconcile(row)
        with workspace_context(self.ws.pk):
            self.assertEqual(CostEvidence.objects.count(),2)
            with self.assertRaises(DatabaseError),transaction.atomic():
                CostEvidence.objects.update(amount=0)
        self.assertTrue(BudgetDay.objects.get().pricing_hold)

    def test_foreign_trial_reminder_source_is_rejected_by_database(self):
        sub,event=self.trial()
        with workspace_context(self.foreign.pk),self.assertRaises(DatabaseError),transaction.atomic():
            TrialReminder.objects.create(workspace=self.foreign,trial_event=event,trial_end=sub.trial_end_date)

    def test_count_or_spend_policy_cannot_increase_after_first_reservation(self):
        row=self.source();second=self.second();self.dispatch(row)
        with self.selected(daily_spend_inr="200"),self.assertRaisesMessage(ValidationError,"daily_pricing_or_policy_hold"):
            self.dispatch(second)
        self.assertEqual(BudgetDay.objects.get().reserved_count,1)
        self.send.assert_called_once()

    def test_reminder_owner_optout_and_lifecycle_rechecked(self):
        self.trial()
        with override_settings(PLATFORM_WHATSAPP_INTENTS_ENABLED=True):
            row=queue_trial_reminder(workspace_id=self.ws.pk)
        change_contact(actor=self.owner,action="pause")
        self.assertIsNone(queue_trial_reminder(workspace_id=self.ws.pk))
        with self.assertRaises(ValidationError):
            self.dispatch(row)
        Company.all_objects.filter(pk=self.ws.pk).update(lifecycle_state="SUSPENDED")
        self.assertIsNone(queue_trial_reminder(workspace_id=self.ws.pk))
        self.send.assert_not_called()

    def test_unpriced_read_after_priced_delivery_keeps_known_cost(self):
        row=self.source();self.dispatch(row)
        self.post_payload(status_payload(status_fact(message_id="wamid.accepted_fixture",
            pricing={"category":"utility","pricing_model":"PMP","billable":True})))
        self.reconcile(row)
        self.post_payload(status_payload(status_fact("read",message_id="wamid.accepted_fixture")))
        self.assertEqual(self.reconcile(row)["status"],"read")
        self.assertFalse(BudgetDay.objects.get().pricing_hold)
        with workspace_context(self.ws.pk):
            self.assertEqual(CostEvidence.objects.count(),1)

    def test_unknown_provider_category_holds_without_losing_delivery(self):
        row=self.source();self.dispatch(row)
        self.post_payload(status_payload(status_fact(message_id="wamid.accepted_fixture",
            pricing={"category":"future_category","pricing_model":"PMP","billable":True})))
        self.assertEqual(self.reconcile(row)["status"],"delivered")
        self.assertTrue(BudgetDay.objects.get().pricing_hold)

    def test_unknown_authenticated_pricing_stops_next_send_before_scoped_reconciliation(self):
        first=self.source();second=self.second();self.dispatch(first)
        self.post_payload(status_payload(status_fact(message_id="wamid.accepted_fixture",
            pricing={"category":"future_category","pricing_model":"PMP","billable":True})))
        with self.assertRaisesMessage(ValidationError,"unreconciled_pricing_hold"):
            self.dispatch(second)
        self.send.assert_called_once()
