import django_filters
from django_select2.forms import ModelSelect2Widget

from apps.tenant_apps.contact.forms import CustomerWidget
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.product.models import Stock

from .models import Approval, ApprovalLine


class ApprovalFilter(django_filters.FilterSet):
    contact = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.all(),
        widget=CustomerWidget(empty_label="Customer"),
    )

    class Meta:
        model = Approval
        fields = [
            "contact",
            "status",
            "is_billed",
        ]


class ApprovalLineFilter(django_filters.FilterSet):
    approval__contact = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.all(),
        widget=CustomerWidget(empty_label="Customer"),
    )
    product = django_filters.ModelChoiceFilter(
        queryset=Stock.objects.all(),
        widget=ModelSelect2Widget(
            empty_label="stock", search_fields=["variant__name__icontains"]
        ),
    )

    class Meta:
        model = ApprovalLine
        fields = [
            "approval__contact",
        ]
