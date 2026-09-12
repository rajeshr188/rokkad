"""Date controls for activity, independent of today's portfolio balances."""
from datetime import timedelta

from django import forms
from django.utils import timezone


class DashboardActivityForm(forms.Form):
    period = forms.ChoiceField(choices=(
        ("month", "This month"), ("today", "Today"),
        ("30days", "Last 30 days"), ("custom", "Custom dates"),
    ), widget=forms.Select(attrs={"class": "form-select"}))
    start = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    end = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))

    def __init__(self, *args, today=None, **kwargs):
        self.today = today or timezone.localdate()
        super().__init__(*args, **kwargs)

    def clean(self):
        data = super().clean()
        period = data.get("period")
        if period == "custom":
            start, end = data.get("start"), data.get("end")
            if not start or not end:
                raise forms.ValidationError("Enter both dates for a custom period.")
        else:
            end = self.today
            start = {"month": end.replace(day=1), "today": end,
                     "30days": end - timedelta(days=29)}.get(period, end)
        if end > self.today or start > end:
            raise forms.ValidationError("Choose a start date on or before the end date, with no future dates.")
        if (end - start).days >= 366:
            raise forms.ValidationError("Choose an activity period of at most 366 days.")
        data.update(start=start, end=end)
        return data
