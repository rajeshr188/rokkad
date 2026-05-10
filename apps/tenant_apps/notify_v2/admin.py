from django.contrib import admin
from django.contrib import messages
from django.db import connection
from django.shortcuts import redirect

from .models import (
    NotificationArtifact,
    NotificationAttemptLog,
    NotificationBatch,
    NotificationEvent,
    NotificationEventType,
    NotificationJob,
    NotificationPolicy,
    NotificationRecipient,
    NotificationTemplate,
)


class TenantSchemaAdminGuardMixin:
    """Prevent tenant-only notify_v2 admin pages from querying public schema."""

    @staticmethod
    def _is_public_schema():
        return getattr(connection, "schema_name", "public") == "public"

    def _redirect_public_schema(self, request):
        messages.warning(
            request,
            "Notify V2 admin models are available only in a tenant workspace schema, not public schema.",
        )
        return redirect("admin:index")

    def changelist_view(self, request, extra_context=None):
        if self._is_public_schema():
            return self._redirect_public_schema(request)
        return super().changelist_view(request, extra_context=extra_context)

    def add_view(self, request, form_url="", extra_context=None):
        if self._is_public_schema():
            return self._redirect_public_schema(request)
        return super().add_view(request, form_url=form_url, extra_context=extra_context)

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if self._is_public_schema():
            return self._redirect_public_schema(request)
        return super().change_view(request, object_id, form_url=form_url, extra_context=extra_context)

    def delete_view(self, request, object_id, extra_context=None):
        if self._is_public_schema():
            return self._redirect_public_schema(request)
        return super().delete_view(request, object_id, extra_context=extra_context)


@admin.register(NotificationEventType)
class NotificationEventTypeAdmin(TenantSchemaAdminGuardMixin, admin.ModelAdmin):
    list_display = ["key", "name", "domain", "is_active", "sort_order"]
    list_filter = ["domain", "is_active"]
    search_fields = ["key", "name", "description"]
    ordering = ["domain", "sort_order", "name"]


@admin.register(NotificationPolicy)
class NotificationPolicyAdmin(TenantSchemaAdminGuardMixin, admin.ModelAdmin):
    list_display = ["event_type", "channel", "priority", "batch_enabled", "is_required", "is_active"]
    list_filter = ["channel", "batch_enabled", "is_required", "is_active", "event_type__domain"]
    search_fields = ["event_type__key", "event_type__name"]
    ordering = ["event_type", "priority", "channel"]


@admin.register(NotificationRecipient)
class NotificationRecipientAdmin(TenantSchemaAdminGuardMixin, admin.ModelAdmin):
    list_display = ["name_snapshot", "customer", "email", "phone", "preferred_locale", "is_active"]
    list_filter = ["preferred_locale", "is_active"]
    search_fields = ["name_snapshot", "email", "phone", "customer__firstname", "customer__lastname"]
    ordering = ["name_snapshot"]


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(TenantSchemaAdminGuardMixin, admin.ModelAdmin):
    list_display = ["name", "event_type", "channel", "renderer_type", "locale", "version", "is_active"]
    list_filter = ["channel", "renderer_type", "locale", "is_active", "event_type__domain"]
    search_fields = ["name", "event_type__key", "event_type__name", "layout_key"]
    ordering = ["event_type", "channel", "locale", "-version"]


class NotificationJobInline(admin.TabularInline):
    model = NotificationJob
    extra = 0
    fields = ["channel", "status", "template", "scheduled_for", "attempt_count"]
    readonly_fields = fields
    can_delete = False


@admin.register(NotificationBatch)
class NotificationBatchAdmin(TenantSchemaAdminGuardMixin, admin.ModelAdmin):
    list_display = ["name", "event_type", "status", "job_count", "created_by", "printed_at", "posted_at"]
    list_filter = ["status", "event_type__domain"]
    search_fields = ["name", "event_type__key", "event_type__name", "notes"]
    ordering = ["-created"]
    inlines = [NotificationJobInline]


@admin.register(NotificationEvent)
class NotificationEventAdmin(TenantSchemaAdminGuardMixin, admin.ModelAdmin):
    list_display = ["event_type", "recipient", "batch", "source_app", "source_model", "source_pk", "created"]
    list_filter = ["event_type__domain", "source_app"]
    search_fields = ["event_type__key", "recipient__name_snapshot", "source_model", "source_pk", "dedupe_key"]
    ordering = ["-created"]


class NotificationAttemptLogInline(admin.TabularInline):
    model = NotificationAttemptLog
    extra = 0
    fields = ["attempt_number", "status_before", "status_after", "message", "created_at"]
    readonly_fields = fields
    can_delete = False


@admin.register(NotificationJob)
class NotificationJobAdmin(TenantSchemaAdminGuardMixin, admin.ModelAdmin):
    list_display = ["event", "channel", "status", "scheduled_for", "sent_at", "attempt_count"]
    list_filter = ["channel", "status", "event__event_type__domain"]
    search_fields = ["event__event_type__key", "provider_message_id", "failure_reason"]
    ordering = ["scheduled_for", "created"]
    inlines = [NotificationAttemptLogInline]


@admin.register(NotificationArtifact)
class NotificationArtifactAdmin(TenantSchemaAdminGuardMixin, admin.ModelAdmin):
    list_display = ["job", "artifact_type", "created"]
    list_filter = ["artifact_type"]
    search_fields = ["job__event__event_type__key", "job__provider_message_id"]


@admin.register(NotificationAttemptLog)
class NotificationAttemptLogAdmin(TenantSchemaAdminGuardMixin, admin.ModelAdmin):
    list_display = ["job", "attempt_number", "status_before", "status_after", "created_at"]
    list_filter = ["status_after"]
    search_fields = ["job__event__event_type__key", "message"]
