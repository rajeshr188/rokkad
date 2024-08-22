import django_filters
from django.db.models import Q
from django_select2.forms import Select2MultipleWidget, Select2Widget

from .models import (
    Attribute,
    AttributeValue,
    Category,
    Product,
    ProductType,
    ProductVariant,
    Stock,
    StockTransaction,
)


class StockFilter(django_filters.FilterSet):
    query = django_filters.CharFilter(method="universal_search", label="Search")
    variant = django_filters.ModelChoiceFilter(
        queryset=ProductVariant.objects.all(), widget=Select2Widget
    )

    class Meta:
        model = Stock
        fields = ["variant"]

    def universal_search(self, queryset, name, value):
        # if value.replace(".", "", 1).isdigit():
        #     value = Decimal(value)
        #     return Customer.objects.filter(
        #         Q(price=value) | Q(cost=value)
        #     )

        return Stock.objects.filter(
            Q(huid__icontains=value)
            | Q(lot_no__icontains=value)
            | Q(serial_no__icontains=value)
            | Q(variant__sku__icontains=value)
        )


class StockTransactionFilter(django_filters.FilterSet):
    class Meta:
        model = StockTransaction
        fields = "__all__"


class ProductFilter(django_filters.FilterSet):
    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.all(), widget=Select2Widget
    )
    product_type = django_filters.ModelChoiceFilter(
        queryset=ProductType.objects.all(), widget=Select2Widget
    )

    class Meta:
        model = Product
        fields = ["category", "product_type"]


class ProductVariantFilter(django_filters.FilterSet):
    product = django_filters.ModelChoiceFilter(
        queryset=Product.objects.all(), widget=Select2Widget
    )
    attributes = django_filters.ModelMultipleChoiceFilter(
        queryset=AttributeValue.objects.all(),
        widget=Select2MultipleWidget,
    )

    class Meta:
        model = ProductVariant
        fields = ["product"]
