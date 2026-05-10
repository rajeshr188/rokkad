import django_filters
from django.db.models import Q
from django.forms.widgets import RadioSelect

from .models import Address, Contact, Customer


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
        if not value:
            return queryset

        base_ids = Customer.objects.filter(
            Q(firstname__icontains=value)
            | Q(lastname__icontains=value)
            | Q(relatedto__icontains=value)
        ).values("id")

        # Avoid costly CAST/ILIKE on integer id (id__icontains) by doing exact match
        # only when the search text is numeric.
        if value.isdigit():
            base_ids = Customer.objects.filter(
                Q(id=int(value))
                | Q(firstname__icontains=value)
                | Q(lastname__icontains=value)
                | Q(relatedto__icontains=value)
            ).values("id")
            normalized_query = value
        else:
            normalized_query = "".join(ch for ch in value if ch.isdigit())

        if normalized_query:
            contact_ids = Contact.objects.filter(
                phone_number_normalized__contains=normalized_query
            ).values("customer_id")
        else:
            contact_ids = Contact.objects.filter(
                phone_number__icontains=value
            ).values("customer_id")

        address_ids = Address.objects.filter(
            Q(area__icontains=value) | Q(street__icontains=value)
        ).values("customer_id")

        return queryset.filter(
            Q(id__in=base_ids)
            | Q(id__in=contact_ids)
            | Q(id__in=address_ids)
        )

    def filter_area(self, queryset, name, value):
        if not value:
            return queryset
        address_customer_ids = Address.objects.filter(
            area__icontains=value
        ).values("customer_id")
        return queryset.filter(id__in=address_customer_ids)

    def filter_street(self, queryset, name, value):
        if not value:
            return queryset
        address_customer_ids = Address.objects.filter(
            street__icontains=value
        ).values("customer_id")
        return queryset.filter(id__in=address_customer_ids)
