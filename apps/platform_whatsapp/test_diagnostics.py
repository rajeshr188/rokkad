"""PW-05 authorization/status/review boundaries. Every provider request is mocked."""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from django.core.exceptions import PermissionDenied,ValidationError
from django.core.management import call_command,CommandError
from django.db import transaction
from django.test import TestCase,TransactionTestCase,override_settings,Client
from django.urls import reverse
from django.utils import timezone
from apps.orgs.models import Company,Membership
from apps.orgs.audit import AuditLog
from apps.orgs.services.control_plane import transfer_workspace_ownership
from apps.tenancy.context import workspace_context
from .test_dispatch import DispatchFixture
from .test_release_controls import SEND4,fixture_pilot
from .test_intents import STORAGE,PaidFixture
from .test_receipts import status_payload,status_fact
from .diagnostics import owner_history,platform_dashboard,pilot_preflight,invoice_delivery_status
from .operations import review_operation,confirm_operation
from .models import Delivery,Attempt,ReceiptLink,BudgetDay,ProviderReceipt
from .transport import TransportFailure


@override_settings(**SEND4,STORAGES=STORAGE)
class DiagnosticTests(DispatchFixture,TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.owner.email="pw05-owner@example.test"
        self.owner.save(update_fields=["email"])
    def platform(self,ids=None):
        return platform_dashboard(actor=self.admin,workspace_ids=ids or [self.ws.pk])
    def history(self):
        return owner_history(actor=self.owner,workspace_slug=self.ws.slug)
    def operation_url(self,row,action):
        return reverse("platform_whatsapp_operation",kwargs={"workspace_slug":row.workspace.slug,"delivery_id":row.pk,"action":action})
    def rejected(self):
        row=self.source();self.send.side_effect=TransportFailure("provider_rejected",outcome="rejected",retryable=True,http_status=429)
        self.assertEqual(self.dispatch(row),"rejected")
        return row
    def future(self,row):
        return patch("apps.platform_whatsapp.operations.timezone.now",return_value=self.attempts(row)[-1].finished_at+timedelta(minutes=2))
    def confirm(self,review,row,actor=None,action="retry"):
        return confirm_operation(actor=actor or self.owner,token=review["token"],workspace_slug=self.ws.slug,delivery_id=row.pk,action=action)

    def test_owner_history_is_read_only_masked_and_scope_bound(self):
        row=self.source(capture=True);before=(Delivery.objects.count(),Attempt.objects.count(),ProviderReceipt.objects.count())
        report=self.history();self.assertEqual(report["counts"][0]["state"],"captured")
        self.assertEqual(report["deliveries"][0]["recipient"],row.masked_phone)
        self.assertFalse(report["deliveries"][0]["retryable"])
        self.assertEqual(before,(Delivery.objects.count(),Attempt.objects.count(),ProviderReceipt.objects.count()))
        self.send.assert_not_called()
        for actor in (self.staff,self.other,self.admin):
            with self.assertRaises(PermissionDenied):owner_history(actor=actor,workspace_slug=self.ws.slug)

    def test_owner_history_preserves_read_and_conflicting_callback_evidence(self):
        row=self.source();self.dispatch(row)
        for status in ("read","failed"):
            self.post_payload(status_payload(status_fact(status,message_id="wamid.accepted_fixture")))
        self.reconcile(row)
        report=self.history();self.assertEqual(report["counts"][0]["state"],"read")
        self.assertTrue(report["deliveries"][0]["receipt_conflict"])
        self.send.assert_called_once()

    def test_owner_history_does_not_ingest_pending_receipts(self):
        row=self.source();self.dispatch(row)
        self.post_payload(status_payload(status_fact(message_id="wamid.accepted_fixture")))
        self.assertEqual(self.history()["counts"][0]["state"],"accepted")
        with workspace_context(self.ws.pk):self.assertFalse(ReceiptLink.objects.exists())

    def test_new_owner_cannot_see_previous_owners_saved_sources(self):
        self.source(capture=True)
        Membership.objects.create(company=self.ws,user=self.other,role=self.member_role)
        transfer_workspace_ownership(workspace=self.ws,new_owner=self.other,actor=self.owner,previous_owner_role=self.member_role,reason="Fictional PW05 transfer")
        report=owner_history(actor=self.other,workspace_slug=self.ws.slug)
        self.assertFalse(report["deliveries"])
        with self.assertRaises(PermissionDenied):self.history()

    def test_platform_dashboard_is_admin_only_and_explicitly_bounded(self):
        for actor in (self.owner,self.staff,None):
            with self.assertRaises(PermissionDenied):platform_dashboard(actor=actor,workspace_ids=[self.ws.pk])
        for ids in ([0],[self.ws.pk]*2,list(range(1,102)),[True],[999999999]):
            with self.assertRaises(ValidationError):self.platform(ids)
        with workspace_context(self.ws.pk),self.assertRaises(PermissionDenied):self.platform()
        self.send.assert_not_called()

    def test_platform_totals_do_not_claim_global_unmatched_from_hidden_rls_links(self):
        row=self.source();self.dispatch(row)
        self.post_payload(status_payload(status_fact(message_id="wamid.accepted_fixture")));self.reconcile(row)
        report=self.platform();self.assertEqual(report["receipts_not_in_selected_matches"],0)
        outside=platform_dashboard(actor=self.admin,workspace_ids=[self.foreign.pk])
        self.assertEqual(outside["receipts_not_in_selected_matches"],1)
        self.assertFalse(outside["summaries"][0]["deliveries"])

    def test_platform_cost_estimates_do_not_double_count_delivery_and_read(self):
        row=self.source();self.dispatch(row)
        for status in ("delivered","read"):
            self.post_payload(status_payload(status_fact(status,message_id="wamid.accepted_fixture",pricing={"category":"utility","pricing_model":"PMP","billable":True})));self.reconcile(row)
        report=self.platform()["summaries"][0]
        self.assertEqual(str(report["known_estimates"]),"0.100000")
        self.assertEqual(report["reserved_count"],1)
        self.assertEqual(str(report["reserved_amount"]),"0.400000")

    def test_platform_get_does_not_send_reconcile_or_expose_credentials(self):
        row=self.source(capture=True);self.client.force_login(self.admin)
        response=self.client.get(reverse("platform_whatsapp_dashboard"),{"workspace_ids":str(self.ws.pk)})
        self.assertEqual(response.status_code,200);self.assertIn("no-store",response["Cache-Control"])
        for private in ("fictional-private-token","fictional-pairing-secret","+919876543210"):
            self.assertNotContains(response,private)
        self.assertContains(response,"Saved preview only");self.send.assert_not_called()

    def test_owner_status_route_get_is_masked_and_admin_override_denied(self):
        self.source(capture=True);url=reverse("platform_whatsapp_history",kwargs={"workspace_slug":self.ws.slug})
        response=self.client.get(url);self.assertEqual(response.status_code,200);self.assertNotContains(response,"+919876543210")
        self.client.force_login(self.admin);self.assertEqual(self.client.get(url).status_code,403)

    def test_retry_review_get_makes_no_request_and_needs_backoff(self):
        row=self.rejected()
        with self.assertRaises(ValidationError):review_operation(actor=self.owner,workspace_slug=self.ws.slug,delivery_id=row.pk,action="retry")
        with self.future(row):
            response=self.client.get(self.operation_url(row,"retry"));self.assertEqual(response.status_code,200)
        self.send.assert_called_once();self.assertEqual(len(self.attempts(row)),1)

    def test_reviewed_retry_commits_a_new_bounded_attempt_and_audits_actor(self):
        row=self.rejected()
        with self.future(row):
            reviewed=review_operation(actor=self.owner,workspace_slug=self.ws.slug,delivery_id=row.pk,action="retry")
            self.send.side_effect=None
            self.assertEqual(self.confirm(reviewed,row),"accepted")
            with self.assertRaises(ValidationError):self.confirm(reviewed,row)
        self.assertEqual(len(self.attempts(row)),2);self.assertEqual(BudgetDay.objects.get().reserved_count,2)
        self.assertTrue(AuditLog.objects.filter(user=self.owner,description="Reviewed platform WhatsApp retry").exists())

    def test_retry_never_available_for_capture_accepted_or_unknown(self):
        row=self.source();self.dispatch(row)
        with self.assertRaises(ValidationError):review_operation(actor=self.owner,workspace_slug=self.ws.slug,delivery_id=row.pk,action="retry")
        unknown_ws=self.make_workspace("pw05-unknown",self.owner);self.consent(self.contact,workspace=unknown_ws)
        row=self.source(workspace=unknown_ws);self.send.side_effect=TransportFailure("provider_connection_uncertain");self.dispatch(row)
        with self.assertRaises(ValidationError):review_operation(actor=self.owner,workspace_slug=unknown_ws.slug,delivery_id=row.pk,action="retry")

    def test_retry_rechecks_consent_and_configuration_and_exact_route(self):
        row=self.rejected()
        with self.future(row):
            reviewed=review_operation(actor=self.owner,workspace_slug=self.ws.slug,delivery_id=row.pk,action="retry")
            with self.assertRaises(PermissionDenied):confirm_operation(actor=self.owner,token=reviewed["token"],workspace_slug=self.foreign.slug,delivery_id=row.pk,action="retry")
            with self.assertRaises(PermissionDenied):self.confirm(reviewed,row,action="reconcile")
            with override_settings(PLATFORM_WHATSAPP_RETENTION_REFERENCE="changed-policy"),self.assertRaises(ValidationError):self.confirm(reviewed,row)
            from .services import change_contact
            change_contact(actor=self.owner,action="pause")
            with self.assertRaises(ValidationError):self.confirm(reviewed,row)
        self.send.assert_called_once()

    def test_reconcile_review_is_admin_only_and_never_sends(self):
        row=self.source();self.dispatch(row)
        self.post_payload(status_payload(status_fact(message_id="wamid.accepted_fixture")))
        with self.assertRaises(PermissionDenied):review_operation(actor=self.owner,workspace_slug=self.ws.slug,delivery_id=row.pk,action="reconcile")
        reviewed=review_operation(actor=self.admin,workspace_slug=self.ws.slug,delivery_id=row.pk,action="reconcile")
        self.assertEqual(self.confirm(reviewed,row,actor=self.admin,action="reconcile"),"delivered")
        self.send.assert_called_once()

    def test_http_confirmation_needs_csrf_ack_and_correct_actor(self):
        row=self.source();self.dispatch(row);self.client.force_login(self.admin)
        url=self.operation_url(row,"reconcile");response=self.client.get(url);token=response.context["review"]["token"]
        self.assertEqual(self.client.post(url,{"token":token}).status_code,409)
        secure=Client(enforce_csrf_checks=True);secure.force_login(self.admin)
        self.assertEqual(secure.post(url,{"token":token,"acknowledged":"on"}).status_code,403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url,{"token":token,"acknowledged":"on"}).status_code,403)
        self.send.assert_called_once()

    def test_signed_operation_review_expiry_and_forgery_never_send(self):
        row=self.rejected()
        with self.future(row):
            reviewed=review_operation(actor=self.owner,workspace_slug=self.ws.slug,delivery_id=row.pk,action="retry")
            with patch("django.core.signing.time.time",return_value=timezone.now().timestamp()+601):
                with self.assertRaises(ValidationError):self.confirm(reviewed,row)
            reviewed["token"]+="x"
            with self.assertRaises(ValidationError):self.confirm(reviewed,row)
        self.send.assert_called_once()

    def test_preflight_checks_canonical_owner_without_disclosing_email(self):
        report=pilot_preflight(actor=self.admin,workspace_slug=self.ws.slug,owner_email="different@example.test")
        self.assertFalse(report["owner_match"]);self.assertIn("canonical_owner_mismatch",report["blockers"])
        self.assertFalse(report["provider_acceptance_proven"])
        self.assertNotIn("different@example.test",str(report));self.send.assert_not_called()

    def test_preflight_requires_fresh_request_and_explicit_release_references(self):
        self.source(capture=True)
        with override_settings(PLATFORM_WHATSAPP_RETENTION_REFERENCE="",PLATFORM_WHATSAPP_SUPPORT_MONITOR=""):
            report=pilot_preflight(actor=self.admin,workspace_slug=self.ws.slug,owner_email=self.owner.email)
        for blocker in ("setup_already_captured_for_enrollment","new_intents_disabled","retention_reference_required","support_monitor_required"):
            self.assertIn(blocker,report["blockers"])
        self.assertFalse(report["ready_for_owner_setup_review"])

    def test_preflight_command_is_read_only_and_needs_restricted_role(self):
        output=StringIO();call_command("check_platform_whatsapp_pilot",actor_id=self.admin.pk,workspace_slug=self.ws.slug,owner_email=self.owner.email,stdout=output)
        self.assertIn('"owner_match": true',output.getvalue());self.send.assert_not_called()
        with transaction.atomic(),self.assertRaises(CommandError):call_command("check_platform_whatsapp_pilot",actor_id=self.admin.pk,workspace_slug=self.ws.slug,owner_email=self.owner.email,stdout=output)

    def test_preflight_reports_missing_schema_without_querying_contact_tables(self):
        with patch("apps.platform_whatsapp.diagnostics.schema_ready",return_value=False),patch("apps.platform_whatsapp.diagnostics._target") as target:
            report=pilot_preflight(actor=self.admin,workspace_slug=self.ws.slug,owner_email=self.owner.email)
        self.assertIn("platform_whatsapp_schema_required",report["blockers"])
        target.assert_not_called();self.send.assert_not_called()

    def test_preflight_rejects_blank_owner_identity(self):
        report=pilot_preflight(actor=self.admin,workspace_slug=self.ws.slug,owner_email="")
        self.assertFalse(report["owner_match"])

    def test_configuration_does_not_bypass_missing_release_references(self):
        row=self.source()
        with override_settings(PLATFORM_WHATSAPP_RETENTION_REFERENCE=""),self.assertRaises(ValidationError):self.dispatch(row)
        self.send.assert_not_called();self.assertFalse(self.attempts(row))


@override_settings(**SEND4,STORAGES=STORAGE,RAZORPAY_KEY_SECRET="test-secret")
class InvoiceDiagnosticTests(PaidFixture,TestCase):
    def test_paid_invoice_channels_are_independent_and_read_only(self):
        self.paired();invoice=self.order();self.confirm(invoice)
        from apps.platform_mail.models import Delivery as MailDelivery
        mail=MailDelivery.objects.get(invoice=invoice);mail.status=MailDelivery.Status.FAILED;mail.save(update_fields=["status"])
        with workspace_context(self.ws.pk):
            before=list(Delivery.objects.values())
            report=invoice_delivery_status(actor=self.owner,invoice=invoice)
            self.assertEqual(report["whatsapp"]["state"],"captured")
            self.assertEqual(report["email_status"],"Failed")
            self.assertEqual(before,list(Delivery.objects.values()))
        invoice.refresh_from_db();self.assertEqual(invoice.status,"paid")

    def test_invoice_status_requires_context_and_canonical_owner(self):
        invoice=self.order();self.confirm(invoice)
        with self.assertRaises(PermissionDenied):invoice_delivery_status(actor=self.owner,invoice=invoice)
        with workspace_context(self.foreign.pk),self.assertRaises(PermissionDenied):invoice_delivery_status(actor=self.owner,invoice=invoice)
        with workspace_context(self.ws.pk):
            for actor in (self.admin,self.staff,self.other):
                self.assertIsNone(invoice_delivery_status(actor=actor,invoice=invoice))
            self.assertIsNone(invoice_delivery_status(actor=self.owner,invoice=invoice)["whatsapp"])

    def test_invoice_http_shows_independent_channel_status(self):
        self.paired();invoice=self.order();self.confirm(invoice);self.client.force_login(self.owner)
        url=reverse("workspace_subscriptions:invoice-detail",kwargs={"workspace_slug":self.ws.slug,"pk":invoice.pk})
        response=self.client.get(url)
        self.assertEqual(response.status_code,200);self.assertContains(response,"Receipt messages")
        self.assertContains(response,"Saved preview only");self.assertNotContains(response,"+919876543210")
