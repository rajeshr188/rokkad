from django.contrib import admin

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


@admin.register(NotificationEventType)
class NotificationEventTypeAdmin(admin.ModelAdmin):
    list_display = ["key", "name", "domain", "is_active", "sort_order"]
    list_filter = ["domain", "is_active"]
    search_fields = ["key", "name", "description"]
    ordering = ["domain", "sort_order", "name"]


@admin.register(NotificationPolicy)
class NotificationPolicyAdmin(admin.ModelAdmin):
    list_display = ["event_type", "channel", "priority", "batch_enabled", "is_required", "is_active"]
    list_filter = ["channel", "batch_enabled", "is_required", "is_active", "event_type__domain"]
    search_fields = ["event_type__key", "event_type__name"]
    ordering = ["event_type", "priority", "channel"]


@admin.register(NotificationRecipient)
class NotificationRecipientAdmin(admin.ModelAdmin):
    list_display = ["name_snapshot", "customer", "email", "phone", "preferred_locale", "is_active"]
    list_filter = ["preferred_locale", "is_active"]
    search_fields = ["name_snapshot", "email", "phone", "customer__firstname", "customer__lastname"]
    ordering = ["name_snapshot"]


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
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
class NotificationBatchAdmin(admin.ModelAdmin):
    list_display = ["name", "event_type", "status", "job_count", "created_by", "printed_at", "posted_at"]
    list_filter = ["status", "event_type__domain"]
    search_fields = ["name", "event_type__key", "event_type__name", "notes"]
    ordering = ["-created"]
    inlines = [NotificationJobInline]


@admin.register(NotificationEvent)
class NotificationEventAdmin(admin.ModelAdmin):
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
class NotificationJobAdmin(admin.ModelAdmin):
    list_display = ["event", "channel", "status", "scheduled_for", "sent_at", "attempt_count"]
    list_filter = ["channel", "status", "event__event_type__domain"]
    search_fields = ["event__event_type__key", "provider_message_id", "failure_reason"]
    ordering = ["scheduled_for", "created"]
    inlines = [NotificationAttemptLogInline]


@admin.register(NotificationArtifact)
class NotificationArtifactAdmin(admin.ModelAdmin):
    list_display = ["job", "artifact_type", "created"]
    list_filter = ["artifact_type"]
    search_fields = ["job__event__event_type__key", "job__provider_message_id"]


@admin.register(NotificationAttemptLog)
class NotificationAttemptLogAdmin(admin.ModelAdmin):
    list_display = ["job", "attempt_number", "status_before", "status_after", "created_at"]
    list_filter = ["status_after"]
    search_fields = ["job__event__event_type__key", "message"]
