from django.contrib import admin
from .models import (
    NoticeGroup,
    Notification,
    NoticeTypeConfig,
    NotificationItem,
    NotificationTemplate,
)


@admin.register(NoticeTypeConfig)
class NoticeTypeConfigAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "name",
        "category",
        "is_active",
        "sort_order",
        "has_templates",
    ]
    list_filter = ["category", "is_active"]
    search_fields = ["code", "name", "description"]
    ordering = ["category", "sort_order", "name"]
    readonly_fields = ["created", "modified"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "code",
                    "name",
                    "category",
                    "description",
                    "is_active",
                    "sort_order",
                )
            },
        ),
        (
            "SMS Template",
            {
                "fields": ("sms_template",),
                "classes": ("collapse",),
            },
        ),
        (
            "WhatsApp Template",
            {
                "fields": ("whatsapp_template",),
                "classes": ("collapse",),
            },
        ),
        (
            "Email Templates",
            {
                "fields": ("email_subject_template", "email_template"),
                "classes": ("collapse",),
            },
        ),
        (
            "Postal Template",
            {
                "fields": ("postal_template",),
                "classes": ("collapse",),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created", "modified"),
                "classes": ("collapse",),
            },
        ),
    )

    def has_templates(self, obj):
        templates_count = sum(
            [
                bool(obj.sms_template),
                bool(obj.whatsapp_template),
                bool(obj.email_template),
                bool(obj.postal_template),
            ]
        )
        return f"{templates_count}/4"

    has_templates.short_description = "Templates"

    actions = ["activate", "deactivate"]

    def activate(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} notice types activated.")

    activate.short_description = "Activate selected notice types"

    def deactivate(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} notice types deactivated.")

    deactivate.short_description = "Deactivate selected notice types"


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "notice_type_config",
        "medium_type",
        "renderer",
        "is_active",
        "sort_order",
        "pdf_template_key",
    ]
    list_filter = ["medium_type", "renderer", "is_active", "notice_type_config"]
    search_fields = [
        "name",
        "notice_type_config__code",
        "notice_type_config__name",
        "body_template",
        "pdf_template_key",
    ]
    ordering = ["notice_type_config__category", "sort_order", "name"]
    readonly_fields = ["created", "modified"]

    fieldsets = (
        (
            "Template Scope",
            {
                "fields": (
                    "notice_type_config",
                    "name",
                    "medium_type",
                    "renderer",
                    "is_active",
                    "sort_order",
                )
            },
        ),
        (
            "Content",
            {
                "fields": ("subject_template", "body_template", "pdf_template_key"),
                "description": "Use PDF renderer for fixed printed forms and Django/Jinja templates for flexible digital notifications.",
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created", "modified"),
                "classes": ("collapse",),
            },
        ),
    )


class NotificationItemInline(admin.TabularInline):
    model = NotificationItem
    extra = 0
    readonly_fields = ["content_type", "object_id", "created"]
    fields = [
        "content_type",
        "object_id",
        "reference_number",
        "amount",
        "due_date",
        "notes",
    ]
    can_delete = True


@admin.register(NoticeGroup)
class NoticeGroupAdmin(admin.ModelAdmin):
    list_display = ["name", "created", "notification_count", "description_preview"]
    search_fields = ["name", "description"]
    date_hierarchy = "created"
    readonly_fields = ["created"]

    def notification_count(self, obj):
        return obj.notifications.count()

    notification_count.short_description = "Notifications"

    def description_preview(self, obj):
        if obj.description:
            return (
                obj.description[:50] + "..."
                if len(obj.description) > 50
                else obj.description
            )
        return "-"

    description_preview.short_description = "Description"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "customer",
        "effective_notice_type_display",
        "medium_type",
        "status",
        "item_count",
        "is_printed",
        "created",
    ]
    list_filter = [
        "status",
        "notice_type",  # Old field
        "notice_type_config",  # New field
        "medium_type",
        "is_printed",
        "created",
    ]
    search_fields = ["customer__name", "message", "id"]
    readonly_fields = ["created", "last_updated"]
    date_hierarchy = "created"
    inlines = [NotificationItemInline]  # New generic items

    fieldsets = (
        ("Basic Information", {"fields": ("group", "customer")}),
        (
            "Notification Settings",
            {
                "fields": (
                    "notice_type_config",
                    "notice_type",
                    "medium_type",
                    "message",
                ),
                "description": "Use notice_type_config for new notifications. The notice_type field is deprecated.",
            },
        ),
        (
            "Status & Tracking",
            {"fields": ("status", "is_printed", "created", "last_updated")},
        ),
    )

    def effective_notice_type_display(self, obj):
        """Display the effective notice type (new or old)"""
        return obj.effective_notice_type

    effective_notice_type_display.short_description = "Notice Type"

    def item_count(self, obj):
        return obj.items.count()

    item_count.short_description = "Items (New)"

    actions = ["mark_as_sent", "mark_as_draft", "generate_messages"]

    def mark_as_sent(self, request, queryset):
        updated = queryset.update(status=Notification.StatusType.Sent)
        self.message_user(request, f"{updated} notifications marked as sent.")

    mark_as_sent.short_description = "Mark selected as Sent"

    def mark_as_draft(self, request, queryset):
        updated = queryset.update(status=Notification.StatusType.Draft)
        self.message_user(request, f"{updated} notifications marked as draft.")

    mark_as_draft.short_description = "Mark selected as Draft"

    def generate_messages(self, request, queryset):
        """Bulk action to generate messages from templates"""
        count = 0
        for notification in queryset:
            notification.generate_message()
            notification.save()
            count += 1
        self.message_user(request, f"Generated messages for {count} notifications.")

    generate_messages.short_description = "Generate messages from templates"


@admin.register(NotificationItem)
class NotificationItemAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "notification",
        "content_type",
        "object_id",
        "reference_number",
        "amount",
        "due_date",
        "created",
    ]
    list_filter = ["content_type", "created"]
    search_fields = ["reference_number", "notes", "notification__id"]
    readonly_fields = ["created", "content_object_link"]
    date_hierarchy = "created"

    fieldsets = (
        ("Notification Link", {"fields": ("notification",)}),
        (
            "Related Object",
            {
                "fields": ("content_type", "object_id", "content_object_link"),
                "description": "The business object this notification item refers to (loan, invoice, etc.)",
            },
        ),
        (
            "Item Details",
            {"fields": ("reference_number", "amount", "due_date", "notes")},
        ),
        (
            "Metadata",
            {
                "fields": ("created",),
            },
        ),
    )

    def content_object_link(self, obj):
        """Display a link to the related object if it has get_absolute_url"""
        if obj.content_object and hasattr(obj.content_object, "get_absolute_url"):
            from django.utils.html import format_html

            return format_html(
                '<a href="{}">{}</a>',
                obj.content_object.get_absolute_url(),
                str(obj.content_object),
            )
        elif obj.content_object:
            return str(obj.content_object)
        return "-"

    content_object_link.short_description = "Related Object"
