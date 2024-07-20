import django_filters
from django_select2.forms import Select2Widget

from apps.tenant_apps.contact.forms import CustomerWidget
from apps.tenant_apps.contact.models import Customer

from .models import Invoice, Receipt


class InvoiceFilter(django_filters.FilterSet):
    customer = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.all(),
        widget=CustomerWidget,
    )
    due_date = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")

    class Meta:
        model = Invoice
        fields = ["id", "status"]


class ReceiptFilter(django_filters.FilterSet):
    customer = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.all(), widget=CustomerWidget
    )

    class Meta:
        model = Receipt
        fields = ["id", "created", "status"]
