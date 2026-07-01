from django import forms

from .models import NoticeGroup, Notification


class NoticeGroupForm(forms.ModelForm):
    class Meta:
        model = NoticeGroup
        fields = ["name", "description"]


class NotificationForm(forms.ModelForm):
    class Meta:
        model = Notification
        fields = [
            "group",
            "customer",
            "party",
            "notice_type_config",
            "medium_type",
            "status",
            "message",
        ]
