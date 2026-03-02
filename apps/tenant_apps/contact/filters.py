import django_filters
from django.db.models import Q
from django.forms.widgets import RadioSelect

from .models import Customer


class CustomerFilter(django_filters.FilterSet):
    query = django_filters.CharFilter(method="universal_search", label="")
    relatedto = django_filters.CharFilter(lookup_expr="icontains")
    # contactno = django_filters.CharFilter(
    #     field_name="contactno__phone_number", lookup_expr="icontains"
    # )
    active = django_filters.ChoiceFilter(
        choices=[(True, "Active"), (False, "Inactive")],
        widget=RadioSelect,
        empty_label=None,
        label="",
    )

    class Meta:
        model = Customer
        fields = [
            "query",
            "relatedto",
            "customer_type",
            "active",
        ]

    def universal_search(self, queryset, name, value):
        """
        Search across first name, last name, ID, and contact numbers.
        """
        return Customer.objects.filter(
            Q(firstname__icontains=value)
            | Q(lastname__icontains=value)
            | Q(id__icontains=value)
            | Q(contactno__phone_number__icontains=value)
        ).distinct()
