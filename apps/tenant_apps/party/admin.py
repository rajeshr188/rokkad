from django.contrib import admin

from .models import (
    Party,
    PartyAddress,
    PartyCodeSequence,
    PartyContactMethod,
    PartyDocument,
    PartyIdentifier,
    PartyRelationship,
    PartyRole,
    PartyRoleType,
)


class PartyRoleInline(admin.TabularInline):
    model = PartyRole
    extra = 0


class PartyContactMethodInline(admin.TabularInline):
    model = PartyContactMethod
    extra = 0


class PartyAddressInline(admin.TabularInline):
    model = PartyAddress
    extra = 0


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = [
        "party_code",
        "display_name",
        "party_type",
        "status",
        "relation_label",
        "relation_name",
        "primary_phone",
        "primary_email",
        "credit_hold",
    ]
    list_filter = ["party_type", "status", "relation_label", "credit_hold"]
    search_fields = ["party_code", "display_name", "legal_name", "relation_name", "primary_phone", "primary_email", "tax_pan", "gstin"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [PartyRoleInline, PartyContactMethodInline, PartyAddressInline]


@admin.register(PartyRoleType)
class PartyRoleTypeAdmin(admin.ModelAdmin):
    list_display = ["key", "label", "is_system", "is_active", "sort_order"]
    list_filter = ["is_system", "is_active"]
    search_fields = ["key", "label"]


@admin.register(PartyCodeSequence)
class PartyCodeSequenceAdmin(admin.ModelAdmin):
    list_display = ["key", "next_number", "updated_at"]
    readonly_fields = ["updated_at"]


@admin.register(PartyRole)
class PartyRoleAdmin(admin.ModelAdmin):
    list_display = ["party", "role_type", "segment", "status", "effective_from", "effective_to"]
    list_filter = ["status", "role_type"]
    search_fields = ["party__display_name", "party__party_code", "role_type__key", "role_type__label"]


@admin.register(PartyAddress)
class PartyAddressAdmin(admin.ModelAdmin):
    list_display = ["party", "address_type", "city", "state", "is_default", "is_verified"]
    list_filter = ["address_type", "is_default", "is_verified", "country"]
    search_fields = ["party__display_name", "line1", "city", "postal_code"]


@admin.register(PartyContactMethod)
class PartyContactMethodAdmin(admin.ModelAdmin):
    list_display = ["party", "contact_type", "value", "is_primary", "is_verified"]
    list_filter = ["contact_type", "is_primary", "is_verified"]
    search_fields = ["party__display_name", "value", "normalized_value"]


@admin.register(PartyIdentifier)
class PartyIdentifierAdmin(admin.ModelAdmin):
    list_display = ["party", "identifier_type", "masked_value", "is_verified", "expires_on"]
    list_filter = ["identifier_type", "is_verified"]
    search_fields = ["party__display_name", "masked_value", "value_hash"]


@admin.register(PartyDocument)
class PartyDocumentAdmin(admin.ModelAdmin):
    list_display = ["party", "document_type", "title", "is_verified", "expires_on"]
    list_filter = ["document_type", "is_verified"]
    search_fields = ["party__display_name", "title"]


@admin.register(PartyRelationship)
class PartyRelationshipAdmin(admin.ModelAdmin):
    list_display = ["from_party", "to_party", "relationship_type", "is_active"]
    list_filter = ["relationship_type", "is_active"]
    search_fields = ["from_party__display_name", "to_party__display_name"]
