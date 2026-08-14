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
    query = django_filters.CharFilter(method="universal_search", label="Search")
    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.all(), widget=Select2Widget
    )
    product_type = django_filters.ModelChoiceFilter(
        queryset=ProductType.objects.all(), widget=Select2Widget
    )
    attribute_values = django_filters.ModelMultipleChoiceFilter(
        queryset=AttributeValue.objects.all(),
        widget=Select2MultipleWidget,
        method="filter_attribute_values",
        label="Attribute Values",
    )

    def universal_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value)
            | Q(description__icontains=value)
            | Q(category__name__icontains=value)
            | Q(product_type__name__icontains=value)
        )

    def filter_attribute_values(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(attributes__values__in=value).distinct()

    class Meta:
        model = Product
        fields = ["query", "category", "product_type", "attribute_values"]


class ProductTypeFilter(django_filters.FilterSet):
    query = django_filters.CharFilter(method="universal_search", label="Search")
    has_variants = django_filters.ChoiceFilter(
        choices=(
            ("", "All"),
            ("true", "With Variants"),
            ("false", "Simple (No Variants)"),
        ),
        method="filter_has_variants",
        label="Variant Mode",
    )
    product_attributes = django_filters.ModelMultipleChoiceFilter(
        queryset=Attribute.objects.all(),
        widget=Select2MultipleWidget,
        method="filter_product_attributes",
        label="Product Attributes",
    )

    def universal_search(self, queryset, name, value):
        return queryset.filter(Q(name__icontains=value)).distinct()

    def filter_has_variants(self, queryset, name, value):
        if value == "true":
            return queryset.filter(has_variants=True)
        if value == "false":
            return queryset.filter(has_variants=False)
        return queryset

    def filter_product_attributes(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(product_attributes__in=value).distinct()

    class Meta:
        model = ProductType
        fields = ["query", "has_variants"]


class ProductVariantFilter(django_filters.FilterSet):
    query = django_filters.CharFilter(method="universal_search", label="Search")
    product = django_filters.ModelChoiceFilter(
        queryset=Product.objects.all(), widget=Select2Widget
    )
    product_type = django_filters.ModelChoiceFilter(
        queryset=ProductType.objects.all(),
        field_name="product__product_type",
        widget=Select2Widget,
    )
    attributes = django_filters.ModelMultipleChoiceFilter(
        queryset=AttributeValue.objects.all(),
        widget=Select2MultipleWidget,
        method="filter_attributes",
    )

    def universal_search(self, queryset, name, value):
        return queryset.filter(
            Q(name__icontains=value)
            | Q(product_code__icontains=value)
            | Q(sku__icontains=value)
            | Q(product__name__icontains=value)
            | Q(product__product_type__name__icontains=value)
        ).distinct()

    def filter_attributes(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(attributes__values__in=value).distinct()

    class Meta:
        model = ProductVariant
        fields = ["query", "product_type", "product", "attributes"]
