import base64
import uuid

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.tenant_apps.loans.selectors import get_party_pawn_loan_history_summary

from .access import assert_party_action_permission, party_action_required
from .forms import (
    PartyAddressForm,
    PartyContactMethodForm,
    PartyDocumentForm,
    PartyForm,
    PartyIdentifierForm,
    PartyProfilePhotoForm,
    PartyRelationshipForm,
    PartyRoleForm,
    PartyMergeForm,
)
from .models import (
    Party,
    PartyAddress,
    PartyContactMethod,
    PartyDocument,
    PartyIdentifier,
    PartyRelationship,
    PartyRole,
)
from .selectors import party_detail_queryset
from .resources import PartyResource
from .services.party_merge import merge_parties


PARTY_EXPORT_FORMATS = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _party_detail_url(request, party, tab="overview"):
    url = reverse("workspace_slug_party_detail", kwargs={
        "workspace_slug": request.workspace.slug, "pk": party.pk,
    })
    return f"{url}?tab={tab}"


def _can_export_party_data(request):
    try:
        assert_party_action_permission(request, "export")
        return True
    except PermissionDenied:
        return False


def _party_queryset_from_request(request):
    query = (request.GET.get("q") or "").strip()
    status = request.GET.get("status") or ""
    role_key = request.GET.get("role") or ""

    parties = (
        Party.objects.prefetch_related("roles__role_type")
        .annotate(
            active_role_count=Count(
                "roles",
                filter=Q(roles__status=PartyRole.RoleStatus.ACTIVE),
                distinct=True,
            )
        )
        .order_by("display_name", "party_code")
    )

    if query:
        parties = parties.filter(
            Q(display_name__icontains=query)
            | Q(legal_name__icontains=query)
            | Q(party_code__icontains=query)
            | Q(primary_phone__icontains=query)
            | Q(primary_email__icontains=query)
            | Q(tax_pan__icontains=query)
            | Q(gstin__icontains=query)
        )
    if status:
        parties = parties.filter(status=status)
    if role_key:
        parties = parties.filter(
            roles__role_type__key=role_key,
            roles__status=PartyRole.RoleStatus.ACTIVE,
        )

    return parties.distinct(), query, status, role_key


def _party_export_querystring(request):
    params = request.GET.copy()
    params.pop("page", None)
    params.pop("_export", None)
    return params.urlencode()


def _export_parties(request, parties, export_format):
    if export_format not in PARTY_EXPORT_FORMATS:
        return HttpResponseBadRequest(f"Invalid export format '{export_format}'.")
    try:
        assert_party_action_permission(request, "export")
    except PermissionDenied as exc:
        raise PermissionDenied("Party export permission is required.") from exc

    dataset = PartyResource().export(parties)
    export_data = dataset.export(export_format)
    response = HttpResponse(
        export_data,
        content_type=PARTY_EXPORT_FORMATS[export_format],
    )
    response["Content-Disposition"] = (
        f'attachment; filename="parties.{export_format}"'
    )
    return response


def _party_detail_context(
    request,
    party,
    *,
    active_tab=None,
    contact_form=None,
    address_form=None,
    identifier_form=None,
    document_form=None,
    photo_form=None,
    relationship_form=None,
    merge_form=None,
):
    edit_contact_id = request.GET.get("edit_contact")
    edit_address_id = request.GET.get("edit_address")
    edit_identifier_id = request.GET.get("edit_identifier")
    edit_document_id = request.GET.get("edit_document")
    edit_relationship_id = request.GET.get("edit_relationship")

    edit_contact = (
        party.contact_methods.filter(pk=edit_contact_id).first()
        if edit_contact_id
        else None
    )
    edit_address = (
        party.addresses.filter(pk=edit_address_id).first() if edit_address_id else None
    )
    edit_identifier = (
        party.identifiers.filter(pk=edit_identifier_id).first()
        if edit_identifier_id
        else None
    )
    edit_document = (
        party.documents.filter(pk=edit_document_id).first() if edit_document_id else None
    )
    edit_relationship = (
        party.relationships_from.filter(pk=edit_relationship_id).first()
        if edit_relationship_id
        else None
    )

    active_tab = active_tab or request.GET.get("tab") or "overview"
    loan_history = get_party_pawn_loan_history_summary(party, limit=20)
    return {
        "party": party,
        "role_form": PartyRoleForm(),
        "loan_history": loan_history,
        "active_tab": active_tab,
        "photo_form": photo_form or PartyProfilePhotoForm(instance=party),
        "contact_form": contact_form
        or PartyContactMethodForm(instance=edit_contact),
        "address_form": address_form or PartyAddressForm(instance=edit_address),
        "identifier_form": identifier_form
        or PartyIdentifierForm(instance=edit_identifier, party=party),
        "document_form": document_form
        or PartyDocumentForm(instance=edit_document, party=party),
        "relationship_form": relationship_form
        or PartyRelationshipForm(instance=edit_relationship, from_party=party),
        "merge_form": merge_form or PartyMergeForm(target_party=party),
        "edit_contact": edit_contact,
        "edit_address": edit_address,
        "edit_identifier": edit_identifier,
        "edit_document": edit_document,
        "edit_relationship": edit_relationship,
    }


def _render_party_detail(request, party, **kwargs):
    return render(
        request,
        "party/detail.html",
        _party_detail_context(request, party, **kwargs),
    )


def _sync_party_primary_contact(party, contact, *, old_contact=None, deleted=False):
    phone_types = {
        PartyContactMethod.ContactType.PHONE,
        PartyContactMethod.ContactType.MOBILE,
        PartyContactMethod.ContactType.WHATSAPP,
    }
    update_fields = []

    if deleted:
        if contact.contact_type == PartyContactMethod.ContactType.EMAIL:
            if party.primary_email == contact.value:
                party.primary_email = ""
                update_fields.append("primary_email")
        elif contact.contact_type in phone_types and party.primary_phone == contact.value:
            party.primary_phone = ""
            update_fields.append("primary_phone")
    elif contact.is_primary:
        if contact.contact_type == PartyContactMethod.ContactType.EMAIL:
            party.primary_email = contact.value
            update_fields.append("primary_email")
        elif contact.contact_type in phone_types:
            party.primary_phone = contact.value
            update_fields.append("primary_phone")
    elif old_contact and old_contact.is_primary:
        if old_contact.contact_type == PartyContactMethod.ContactType.EMAIL:
            if party.primary_email == old_contact.value:
                party.primary_email = ""
                update_fields.append("primary_email")
        elif old_contact.contact_type in phone_types and party.primary_phone == old_contact.value:
            party.primary_phone = ""
            update_fields.append("primary_phone")

    if update_fields:
        update_fields.append("updated_at")
        party.save(update_fields=update_fields)


def _save_contact_form(form, party):
    contact = form.save(commit=False)
    contact.party = party
    old_contact = None
    if contact.pk:
        old_contact = PartyContactMethod.objects.get(pk=contact.pk)
    with transaction.atomic():
        if contact.is_primary:
            PartyContactMethod.objects.filter(
                party=party,
                contact_type=contact.contact_type,
                is_primary=True,
            ).exclude(pk=contact.pk).update(is_primary=False)
        contact.save()
        _sync_party_primary_contact(party, contact, old_contact=old_contact)
    return contact


def _save_address_form(form, party):
    address = form.save(commit=False)
    address.party = party
    with transaction.atomic():
        if address.is_default:
            PartyAddress.objects.filter(
                party=party,
                address_type=address.address_type,
                is_default=True,
            ).exclude(pk=address.pk).update(is_default=False)
        address.save()
    return address


def _image_file_from_data_uri(image_data):
    if not image_data:
        return None
    base64_str = image_data.split(",", 1)[1] if "," in image_data else image_data
    return ContentFile(
        base64.b64decode(base64_str),
        name=f"{uuid.uuid4()}.jpg",
    )


@party_action_required("view")
def party_list(request):
    parties, query, status, role_key = _party_queryset_from_request(request)
    export_format = request.GET.get("_export")
    if export_format:
        return _export_parties(request, parties, export_format)

    paginator = Paginator(parties, 50)
    page_obj = paginator.get_page(request.GET.get("page"))

    role_options = (
        PartyRole.objects.filter(status=PartyRole.RoleStatus.ACTIVE)
        .values_list("role_type__key", "role_type__label")
        .distinct()
        .order_by("role_type__label")
    )

    return render(
        request,
        "party/list.html",
        {
            "page_obj": page_obj,
            "query": query,
            "status": status,
            "role_key": role_key,
            "status_choices": Party.PartyStatus.choices,
            "role_options": role_options,
            "can_export_parties": _can_export_party_data(request),
            "export_querystring": _party_export_querystring(request),
        },
    )


@party_action_required("view")
def party_detail(request, pk):
    party = get_object_or_404(
        party_detail_queryset().prefetch_related(
            "relationships_from__to_party",
            "relationships_to__from_party",
        ),
        pk=pk,
    )

    return _render_party_detail(request, party)


@party_action_required("create")
def party_create(request):
    form = PartyForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        party = form.save(commit=False)
        party.created_by = request.user
        party.updated_by = request.user
        party.save()
        messages.success(request, "Party created.")
        return redirect(
            "workspace_slug_party_detail",
            workspace_slug=request.workspace.slug,
            pk=party.pk,
        )

    return render(
        request,
        "party/form.html",
        {"form": form, "title": "Create Party", "submit_label": "Create"},
    )


@party_action_required("edit")
def party_update(request, pk):
    party = get_object_or_404(Party, pk=pk)
    form = PartyForm(request.POST or None, request.FILES or None, instance=party)
    if request.method == "POST" and form.is_valid():
        party = form.save(commit=False)
        party.updated_by = request.user
        party.save()
        messages.success(request, "Party updated.")
        return redirect(
            "workspace_slug_party_detail",
            workspace_slug=request.workspace.slug,
            pk=party.pk,
        )

    return render(
        request,
        "party/form.html",
        {
            "form": form,
            "party": party,
            "title": "Edit Party",
            "submit_label": "Save",
        },
    )


@party_action_required("edit")
def party_role_add(request, pk):
    party = get_object_or_404(Party, pk=pk)
    form = PartyRoleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        role = form.save(commit=False)
        role.party = party
        try:
            with transaction.atomic():
                role.save()
            messages.success(request, "Role added.")
        except IntegrityError:
            messages.error(request, "An active role of that type already exists.")
    return redirect(_party_detail_url(request, party))


@party_action_required("edit")
def party_role_end(request, pk, role_pk):
    party = get_object_or_404(Party, pk=pk)
    role = get_object_or_404(PartyRole, pk=role_pk, party=party)
    if request.method == "POST":
        role.status = PartyRole.RoleStatus.ENDED
        role.effective_to = role.effective_to or timezone.localdate()
        role.save(update_fields=["status", "effective_to", "updated_at"])
        messages.success(request, "Role ended.")
    return redirect(_party_detail_url(request, party))


@party_action_required("edit")
@require_POST
def party_profile_photo_update(request, pk):
    party = get_object_or_404(Party, pk=pk)
    image_data = request.POST.get("image_data", "").strip()

    if image_data:
        try:
            party.profile_photo = _image_file_from_data_uri(image_data)
            party.save(update_fields=["profile_photo", "updated_at"])
            messages.success(request, "Profile photo updated.")
            return redirect(_party_detail_url(request, party, "overview"))
        except Exception as exc:
            messages.error(request, f"Captured photo could not be processed: {exc}")
            return _render_party_detail(request, party, active_tab="overview")

    form = PartyProfilePhotoForm(request.POST, request.FILES, instance=party)
    if form.is_valid() and request.FILES.get("profile_photo"):
        form.save()
        messages.success(request, "Profile photo updated.")
        return redirect(_party_detail_url(request, party, "overview"))

    messages.error(request, "Capture a photo or choose a file before saving.")
    return _render_party_detail(request, party, active_tab="overview", photo_form=form)


@party_action_required("edit")
@require_POST
def party_profile_photo_remove(request, pk):
    party = get_object_or_404(Party, pk=pk)
    if party.profile_photo:
        party.profile_photo.delete(save=False)
        party.profile_photo = ""
        party.save(update_fields=["profile_photo", "updated_at"])
    messages.success(request, "Profile photo removed.")
    return redirect(_party_detail_url(request, party, "overview"))


@party_action_required("edit")
@require_POST
def party_contact_save(request, pk, contact_pk=None):
    party = get_object_or_404(Party, pk=pk)
    instance = None
    if contact_pk is not None:
        instance = get_object_or_404(PartyContactMethod, pk=contact_pk, party=party)
    form = PartyContactMethodForm(request.POST, instance=instance)
    if form.is_valid():
        try:
            _save_contact_form(form, party)
            messages.success(request, "Contact saved.")
            return redirect(_party_detail_url(request, party, "contacts"))
        except IntegrityError:
            form.add_error(None, "A primary contact of this type already exists.")
    messages.error(request, "Contact could not be saved.")
    return _render_party_detail(
        request,
        party,
        active_tab="contacts",
        contact_form=form,
    )


@party_action_required("edit")
@require_POST
def party_contact_delete(request, pk, contact_pk):
    party = get_object_or_404(Party, pk=pk)
    contact = get_object_or_404(PartyContactMethod, pk=contact_pk, party=party)
    _sync_party_primary_contact(party, contact, deleted=True)
    contact.delete()
    messages.success(request, "Contact deleted.")
    return redirect(_party_detail_url(request, party, "contacts"))


@party_action_required("edit")
@require_POST
def party_address_save(request, pk, address_pk=None):
    party = get_object_or_404(Party, pk=pk)
    instance = None
    if address_pk is not None:
        instance = get_object_or_404(PartyAddress, pk=address_pk, party=party)
    form = PartyAddressForm(request.POST, instance=instance)
    if form.is_valid():
        try:
            _save_address_form(form, party)
            messages.success(request, "Address saved.")
            return redirect(_party_detail_url(request, party, "addresses"))
        except IntegrityError:
            form.add_error(None, "A default address of this type already exists.")
    messages.error(request, "Address could not be saved.")
    return _render_party_detail(
        request,
        party,
        active_tab="addresses",
        address_form=form,
    )


@party_action_required("edit")
@require_POST
def party_address_delete(request, pk, address_pk):
    party = get_object_or_404(Party, pk=pk)
    address = get_object_or_404(PartyAddress, pk=address_pk, party=party)
    address.delete()
    messages.success(request, "Address deleted.")
    return redirect(_party_detail_url(request, party, "addresses"))


@party_action_required("edit")
@require_POST
def party_identifier_save(request, pk, identifier_pk=None):
    party = get_object_or_404(Party, pk=pk)
    instance = None
    if identifier_pk is not None:
        instance = get_object_or_404(PartyIdentifier, pk=identifier_pk, party=party)
    form = PartyIdentifierForm(request.POST, instance=instance, party=party)
    if form.is_valid():
        identifier = form.save(commit=False)
        identifier.party = party
        identifier.save()
        messages.success(request, "Identifier saved.")
        return redirect(_party_detail_url(request, party, "kyc"))
    messages.error(request, "Identifier could not be saved.")
    return _render_party_detail(
        request,
        party,
        active_tab="kyc",
        identifier_form=form,
    )


@party_action_required("edit")
@require_POST
def party_identifier_delete(request, pk, identifier_pk):
    party = get_object_or_404(Party, pk=pk)
    identifier = get_object_or_404(PartyIdentifier, pk=identifier_pk, party=party)
    identifier.delete()
    messages.success(request, "Identifier deleted.")
    return redirect(_party_detail_url(request, party, "kyc"))


@party_action_required("edit")
@require_POST
def party_document_save(request, pk, document_pk=None):
    party = get_object_or_404(Party, pk=pk)
    instance = None
    if document_pk is not None:
        instance = get_object_or_404(PartyDocument, pk=document_pk, party=party)
    form = PartyDocumentForm(request.POST, request.FILES, instance=instance, party=party)
    if form.is_valid():
        document = form.save(commit=False)
        document.party = party
        document.save()
        messages.success(request, "Document saved.")
        return redirect(_party_detail_url(request, party, "kyc"))
    messages.error(request, "Document could not be saved.")
    return _render_party_detail(
        request,
        party,
        active_tab="kyc",
        document_form=form,
    )


@party_action_required("edit")
@require_POST
def party_document_delete(request, pk, document_pk):
    party = get_object_or_404(Party, pk=pk)
    document = get_object_or_404(PartyDocument, pk=document_pk, party=party)
    document.delete()
    messages.success(request, "Document deleted.")
    return redirect(_party_detail_url(request, party, "kyc"))


@party_action_required("edit")
@require_POST
def party_relationship_save(request, pk, relationship_pk=None):
    party = get_object_or_404(Party, pk=pk)
    instance = None
    if relationship_pk is not None:
        instance = get_object_or_404(
            PartyRelationship,
            pk=relationship_pk,
            from_party=party,
        )
    form = PartyRelationshipForm(
        request.POST,
        instance=instance,
        from_party=party,
    )
    if form.is_valid():
        relationship = form.save(commit=False)
        relationship.from_party = party
        relationship.save()
        messages.success(request, "Relationship saved.")
        return redirect(_party_detail_url(request, party, "relationships"))
    messages.error(request, "Relationship could not be saved.")
    return _render_party_detail(
        request,
        party,
        active_tab="relationships",
        relationship_form=form,
    )


@party_action_required("edit")
@require_POST
def party_relationship_delete(request, pk, relationship_pk):
    party = get_object_or_404(Party, pk=pk)
    relationship = get_object_or_404(
        PartyRelationship,
        pk=relationship_pk,
        from_party=party,
    )
    relationship.delete()
    messages.success(request, "Relationship deleted.")
    return redirect(_party_detail_url(request, party, "relationships"))


@party_action_required("edit")
@require_POST
def party_merge(request, pk):
    party = get_object_or_404(Party, pk=pk)
    form = PartyMergeForm(request.POST, target_party=party)
    if form.is_valid():
        source = form.cleaned_data["source_party"]
        try:
            result = merge_parties(target=party, source=source, actor=request.user)
            message = (
                f"Merged {source.display_name} into {party.display_name}. "
                f"Moved {result.contacts_moved} contacts, {result.addresses_moved} "
                f"addresses, {result.identifiers_moved} identifiers, "
                f"and {result.documents_moved} documents."
            )
            if result.skipped:
                message = f"{message} Some relationship or role duplicates were skipped."
            messages.success(request, message)
            return redirect(_party_detail_url(request, party, "merge"))
        except ValidationError as exc:
            for error in exc.messages:
                form.add_error(None, error)
    messages.error(request, "Party merge could not be completed.")
    return _render_party_detail(
        request,
        party,
        active_tab="merge",
        merge_form=form,
    )
