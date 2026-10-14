"""Bounded read-only control-plane diagnostics; no ingestion, source mutation or IO."""
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.apps import apps
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.db.models import Case, CharField, Count, Exists, Max, Q, OuterRef, Subquery, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.orgs.models import Company
from apps.orgs.services.platform_console import require_console_access
from apps.platform_mail.models import Delivery as MailDelivery
from apps.tenancy.context import current_workspace_id, workspace_context
from .configuration import readiness, template_mapping, transport_blockers
from .controls import pilot, in_cohort, ZONE
from .intents import _render, _target, TEMPLATE_REVISION
from .models import Attempt, BudgetDay, Delivery, ProviderReceipt, ReceiptLink, Reservation
from .services import require_account_actor, require_owner
from .receipts import delivery_summary

PURPOSE_LABELS = dict(Delivery.Purpose.choices)
STATUS_LABELS = {"captured":"Saved preview only", "queued":"Queued", "claimed":"Acceptance unconfirmed",
    "accepted":"Accepted; delivery unconfirmed", "sent":"Sent; delivery unconfirmed", "delivered":"Delivered",
    "read":"Read", "failed":"Delivery failed", "rejected":"Rejected", "unknown":"Acceptance unknown",
    "cancelled":"Cancelled before request"}


def scoped_statuses(rows):
    latest=Attempt.objects.filter(delivery_id=OuterRef("pk")).order_by("-number")
    rows=rows.annotate(last_outcome=Subquery(latest.values("outcome")[:1]),
        last_attempt_id=Subquery(latest.values("id")[:1]))
    all_receipts=ReceiptLink.objects.filter(attempt__delivery_id=OuterRef("pk"))
    last_receipts=ReceiptLink.objects.filter(attempt_id=OuterRef("last_attempt_id"))
    rows=rows.annotate(proven_read=Exists(all_receipts.filter(receipt__status="read")),
        proven_delivery=Exists(all_receipts.filter(receipt__status="delivered")),
        last_failed=Exists(last_receipts.filter(receipt__status="failed")),
        last_sent=Exists(last_receipts.filter(receipt__status="sent")))
    return rows.annotate(state=Case(When(capture_only=True,then=Value("captured")),
        When(proven_read=True,then=Value("read")),When(proven_delivery=True,then=Value("delivered")),
        When(last_failed=True,then=Value("failed")),When(last_sent=True,then=Value("sent")),
        default=Coalesce("last_outcome",Value("queued")),output_field=CharField()))


def counts(rows):
    return [{"state":r["state"],"label":STATUS_LABELS.get(r["state"],"Needs review"),"count":r["count"]}
        for r in scoped_statuses(rows).order_by().values("state").annotate(count=Count("pk")).order_by("state")]


def delivery_row(row, *, owner=False):
    result=_render(row)
    latest=row.attempts.order_by("-number").first()
    result.update(workspace=row.workspace, expires_at=row.expires_at, capture_only=row.capture_only,
        state=("captured" if row.capture_only else delivery_summary(row)["status"]),
        attempt_count=row.attempts.count(), diagnostic=latest.diagnostic if latest else "",
        retryable=bool(latest and latest.outcome=="rejected" and latest.retryable and latest.number<3 and result["eligible"]),
        email_status=None)
    if row.invoice_id:
        mail=MailDelivery.objects.filter(invoice_id=row.invoice_id).first()
        result["email_status"]=mail.get_status_display() if mail else "No email intent recorded"
    return result


def rows_for(workspace):
    return Delivery.objects.select_related("workspace__owner","setup_request","trial_event__subscription",
        "invoice__subscription","reminder__trial_event__subscription","announcement_target__announcement").filter(workspace=workspace)


def owner_history(*,actor,workspace_slug):
    require_account_actor(actor)
    workspace=Company.all_objects.select_related("owner").get(slug=workspace_slug)
    with workspace_context(workspace.pk):
        require_owner(actor,workspace)
        rows=rows_for(workspace).filter(owner=actor)
        return {"workspace":workspace,"counts":counts(rows),
            "deliveries":[delivery_row(row,owner=True) for row in rows.order_by("-pk")[:25]],
            "dispatch_enabled":not transport_blockers(),"checked_at":timezone.now()}


def invoice_delivery_status(*, actor, invoice):
    """Existing scoped billing page: channels are independent; current owner only."""
    workspace=invoice.subscription.company
    if current_workspace_id()!=workspace.pk:
        raise PermissionDenied("Explicit matching Workspace context required.")
    try:
        require_owner(actor,workspace)
    except PermissionDenied:
        return None
    row=rows_for(workspace).filter(invoice=invoice,owner=actor).first()
    mail=MailDelivery.objects.filter(invoice=invoice).first()
    return {"workspace":workspace,"whatsapp":delivery_row(row) if row else None,
        "email_status":mail.get_status_display() if mail else "No email intent recorded"}


def schema_ready():
    tables=set(connection.introspection.table_names())
    required={model._meta.db_table for model in apps.get_app_config("platform_whatsapp").get_models()}
    return required<=tables and ("platform_whatsapp","0004_release_controls") in MigrationRecorder(connection).applied_migrations()


def validate_ids(ids):
    if (not isinstance(ids,list) or not 1<=len(ids)<=100 or len(set(ids))!=len(ids)
        or any(type(v) is not int or v<=0 for v in ids)):
        raise ValidationError("Choose 1 to 100 distinct positive Workspace IDs.")
    return sorted(ids)


def selected_ids():
    try:
        return sorted(p["workspace_id"] for p in pilot()["cohort"])
    except ValidationError:
        return []


def platform_dashboard(*,actor,workspace_ids):
    require_console_access(actor)
    ids=validate_ids(workspace_ids) if workspace_ids else []
    workspaces=list(Company.all_objects.select_related("owner").filter(pk__in=ids).exclude(slug="public").order_by("pk"))
    if len(workspaces)!=len(ids):
        raise ValidationError("Every selected Workspace must exist.")
    summaries=[];matched_count=0;today=timezone.now().astimezone(ZONE).date()
    for workspace in workspaces:
        with workspace_context(workspace.pk):
            rows=rows_for(workspace)
            matched_count+=ReceiptLink.objects.filter(workspace=workspace).count()
            reservations=list(Reservation.objects.filter(workspace=workspace,budget__day=today).annotate(
                known_estimate=Max("cost_evidence__amount",filter=Q(cost_evidence__known=True))))
            summaries.append({"workspace":workspace,"counts":counts(rows),
                "deliveries":[delivery_row(r) for r in rows.order_by("-pk")[:5]],
                "reserved_count":len(reservations),"reserved_amount":sum((r.amount for r in reservations),Decimal(0)),
                "known_estimates":sum((r.known_estimate for r in reservations if r.known_estimate is not None),Decimal(0)),
                "priced_count":sum(r.known_estimate is not None for r in reservations)})
    templates=[]
    for purpose,label in PURPOSE_LABELS.items():
        try:
            template_mapping(purpose,TEMPLATE_REVISION);available=True
        except ValidationError:
            available=False
        templates.append({"purpose":label,"available":available})
    return {"summaries":summaries,"readiness":readiness(),"templates":templates,
        "budget_days":list(BudgetDay.objects.order_by("-day")[:7]),
        "receipts_not_in_selected_matches":max(ProviderReceipt.objects.count()-matched_count,0),
        "pricing_markers":ProviderReceipt.objects.filter(Q(pricing_category="unknown")|Q(pricing_model="unknown")).count(),
        "checked_at":timezone.now(),"selected_ids":ids}


def pilot_preflight(*,actor,workspace_slug,owner_email):
    require_console_access(actor)
    workspace=Company.all_objects.select_related("owner").get(slug=workspace_slug)
    blockers=list(readiness()["blockers"])
    owner_match=bool(owner_email.strip()) and workspace.owner.email.casefold()==owner_email.strip().casefold()
    if not owner_match:
        blockers.append("canonical_owner_mismatch")
    target=None
    installed=schema_ready()
    if not installed:blockers.append("platform_whatsapp_schema_required")
    with workspace_context(workspace.pk):
        target=_target(workspace,"setup",at=timezone.now()) if installed else None
        if not target: blockers.append("fresh_owner_pairing_and_setup_consent_required")
        if workspace.lifecycle_state!="ACTIVE":blockers.append("workspace_not_active")
        try:
            if not in_cohort(workspace,"setup"):blockers.append("outside_named_setup_pilot")
        except ValidationError:
            pass
        if target and Delivery.objects.filter(workspace=workspace,contact=target[0],contact_revision=target[0].revision,
            purpose="setup").exists():
            blockers.append("setup_already_captured_for_enrollment")
    try:
        template_mapping("setup",TEMPLATE_REVISION)
    except ValidationError:
        blockers.append("approved_setup_template_required")
    if not getattr(settings,"PLATFORM_WHATSAPP_INTENTS_ENABLED",False):blockers.append("new_intents_disabled")
    # These are release inputs; configured credentials do not prove acceptance.
    for key in ("RETENTION_REFERENCE","SUPPORT_MONITOR"):
        value=getattr(settings,"PLATFORM_WHATSAPP_"+key,"")
        if not isinstance(value,str) or not value.strip() or len(value)>200:
            blockers.append(key.lower()+"_required")
    return {"workspace_id":workspace.pk,"owner_match":owner_match,"recipient":target[0].masked_phone if target else "Not paired",
        "blockers":list(dict.fromkeys(blockers)),"ready_for_owner_setup_review":not blockers,
        "provider_acceptance_proven":False,"checked_at":timezone.now()}
