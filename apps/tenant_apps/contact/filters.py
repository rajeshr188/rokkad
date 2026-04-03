import django_filters
from django.db.models import Q
from django.forms.widgets import RadioSelect

from .models import Customer


class CustomerFilter(django_filters.FilterSet):
    query = django_filters.CharFilter(method="universal_search", label="")
    relatedto = django_filters.CharFilter(lookup_expr="icontains")
    area = django_filters.CharFilter(method="filter_area", label="Area")
    street = django_filters.CharFilter(method="filter_street", label="Street")
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
            "area",
            "street",
            "customer_type",
            "active",
        ]

    def universal_search(self, queryset, name, value):
        """
        Search across names, ID, contact numbers, and address fragments.
        """
        return queryset.filter(
            Q(firstname__icontains=value)
            | Q(lastname__icontains=value)
            | Q(id__icontains=value)
            | Q(relatedto__icontains=value)
            | Q(contactno__phone_number__icontains=value)
            | Q(address__area__icontains=value)
            | Q(address__street__icontains=value)
        ).distinct()

    def filter_area(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(address__area__icontains=value).distinct()

    def filter_street(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(address__street__icontains=value).distinct()
