from django import forms
from django.utils.text import slugify
from django.utils.translation import pgettext_lazy
from django_select2 import forms as s2forms
from django_select2.forms import Select2MultipleWidget, Select2Widget
from mptt.forms import TreeNodeChoiceField

from .attributes import *
from .models import *


class ModelChoiceOrCreationField(forms.ModelChoiceField):
    """ModelChoiceField with the ability to create new choices.

    This field allows to select values from a queryset, but it also accepts
    new values that can be used to create new model choices.
    """

    def to_python(self, value):
        if value in self.empty_values:
            return None
        try:
            key = self.to_field_name or "pk"
            obj = self.queryset.get(**{key: value})
        except (ValueError, TypeError, self.queryset.model.DoesNotExist):
            return value
        else:
            return obj


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description", "parent"]


class ProductTypeForm(forms.ModelForm):
    product_attributes = forms.ModelMultipleChoiceField(
        # widget=forms.CheckboxSelectMultiple,
        widget=Select2MultipleWidget,
        queryset=Attribute.objects.all(),
        required=False,
    )
    variant_attributes = forms.ModelMultipleChoiceField(
        # widget=forms.CheckboxSelectMultiple,
        widget=Select2MultipleWidget,
        queryset=Attribute.objects.all(),
        required=False,
    )

    class Meta:
        model = ProductType
        exclude = []
        labels = {
            "name": pgettext_lazy("Item name", "Name"),
            "has_variants": pgettext_lazy("Enable variants", "Enable variants"),
            "variant_attributes": pgettext_lazy(
                "Product type attributes", "Attributes specific to each variant"
            ),
            "product_attributes": pgettext_lazy(
                "Product type attributes", "Attributes common to all variants"
            ),
        }

    def clean(self):
        data = super().clean()
        has_variants = self.cleaned_data["has_variants"]
        product_attr = set(self.cleaned_data["product_attributes"])
        variant_attr = set(self.cleaned_data["variant_attributes"])
        if not has_variants and variant_attr:
            msg = pgettext_lazy(
                "Product type form error", "Product variants are disabled."
            )
            self.add_error("variant_attributes", msg)
        if product_attr & variant_attr:
            msg = pgettext_lazy(
                "Product type form error",
                "A single attribute can't belong to both a product " "and its variant.",
            )
            self.add_error("variant_attributes", msg)

        if not self.instance.pk:
            return data
        # self.check_if_variants_changed(has_variants)
        # self.update_variants_names(saved_attributes=variant_attr)
        return data


class AttributesMixin:
    """Form mixin that dynamically adds attribute fields."""

    available_attributes = Attribute.objects.none()

    # Name of a field in self.instance that hold attributes HStore
    model_attributes_field = None

    def __init__(self, *args, **kwargs):
        if not self.model_attributes_field:
            raise Exception(
                "model_attributes_field must be set in subclasses of "
                "AttributesMixin."
            )

    def prepare_fields_for_attributes(self):
        initial_attrs = getattr(self.instance, self.model_attributes_field)
        for attribute in self.available_attributes:
            field_defaults = {
                "label": attribute.name,
                "required": False,
                "initial": initial_attrs.get(str(attribute.pk)),
            }
            if attribute.has_values():
                field = ModelChoiceOrCreationField(
                    queryset=attribute.values.all(), **field_defaults
                )
            else:
                field = forms.CharField(**field_defaults)
            self.fields[attribute.get_formfield_name()] = field

    def iter_attribute_fields(self):
        for attr in self.available_attributes:
            yield self[attr.get_formfield_name()]

    def get_saved_attributes(self):
        data = {}
        attributes = {}
        ja = {}
        for attr in self.available_attributes:
            value = self.cleaned_data.pop(attr.get_formfield_name())
            if value:
                # if the passed attribute value is a string,
                # create the attribute value.
                if not isinstance(value, AttributeValue):
                    value = AttributeValue(
                        attribute_id=attr.pk, name=value, slug=slugify(value)
                    )
                    value.save()
                attributes[attr.pk] = value.pk

                ja[attr.name] = value.value
        data["attributes"] = attributes
        data["ja"] = ja
        return data


class ProductForm(forms.ModelForm, AttributesMixin):
    category = TreeNodeChoiceField(
        queryset=Category.objects.all(), label=pgettext_lazy("Category", "Category")
    )
    model_attributes_field = "attributes"

    class Meta:
        model = Product
        exclude = ["attributes", "jattributes", "product_type", "name"]

    def __init__(self, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        product_type = self.instance.product_type
        self.available_attributes = product_type.product_attributes.prefetch_related(
            "values"
        ).all()
        self.prepare_fields_for_attributes()

    def save(self, commit=True):
        attributes = self.get_saved_attributes()
        self.instance.attributes = attributes["attributes"]
        self.instance.jattributes = attributes["ja"]
        # attrs = self.instance.product_type.product_attributes.all()
        # attrs = get_product_attributes_data(self.instance)
        self.instance.name = (
            self.instance.product_type.name
            + " "
            + generate_name_from_values(self.instance.jattributes)
        )
        instance = super().save(commit=commit)
        return instance


class ProductVariantForm(forms.ModelForm, AttributesMixin):
    model_attributes_field = "attributes"

    class Meta:
        model = ProductVariant
        fields = [
            "name",
        ]
        labels = {
            "quantity": pgettext_lazy("Integer number", "Number in stock"),
            "cost_price": pgettext_lazy("Currency amount", "Cost price"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.product.pk:
            self.available_attributes = self.instance.product.product_type.variant_attributes.all().prefetch_related(
                "values"
            )
            self.prepare_fields_for_attributes()

    def save(self, commit=True):
        data = self.get_saved_attributes()
        self.instance.attributes = data["attributes"]
        self.instance.jattributes = data["ja"]
        attrs = self.instance.product.product_type.variant_attributes.all()
        self.instance.name = (
            self.instance.product.name
            + " "
            + generate_name_from_values(self.instance.jattributes)
        )
        return super().save(commit=commit)


class AttributeForm(forms.ModelForm):
    class Meta:
        model = Attribute
        fields = ["name"]


class AttributeValueForm(forms.ModelForm):
    class Meta:
        model = AttributeValue
        fields = ["name", "value", "attribute"]


class ProductImageForm(forms.ModelForm):
    class Meta:
        model = ProductImage
        fields = ["alt"]


class VariantImageForm(forms.ModelForm):
    class Meta:
        model = VariantImage
        fields = "__all__"


class StockForm(forms.ModelForm):
    class Meta:
        model = Stock
        fields = "__all__"


class StockWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "huid__icontains",
        "variant__name__icontains",
        "serial_no__icontains",
        "lot_no__icontains",
    ]


class UniqueForm(forms.Form):
    weight = forms.DecimalField(max_digits=10, decimal_places=3)
    quantity = forms.IntegerField()
    is_unique = forms.BooleanField(initial=True)


class StockStatementForm(forms.Form):
    stock = forms.ModelChoiceField(queryset=Stock.objects.all(), widget=Select2Widget)

    class Meta:
        model = StockStatement
        fields = ["stock", "Closing_wt", "Closing_qty"]


class PricingTierForm(forms.ModelForm):
    class Meta:
        model = PricingTier
        fields = ["name", "description", "minimum_quantity", "parent"]


class PricingTierProductPriceForm(forms.ModelForm):
    class Meta:
        model = PricingTierProductPrice
        fields = "__all__"


class StockInForm(forms.ModelForm):
    # journal_entry = forms.ModelChoiceField(queryset=JournalEntry.objects.all(), widget=forms.HiddenInput())
    variant = forms.ModelChoiceField(
        queryset=ProductVariant.objects.all(), widget=Select2Widget
    )
    rate = forms.DecimalField(max_digits=10, decimal_places=3)
    touch = forms.DecimalField(max_digits=10, decimal_places=3)
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 2, "cols": 15}))
    stock = forms.ModelChoiceField(
        queryset=Stock.objects.all(), widget=StockWidget, required=False
    )

    class Meta:
        model = StockTransaction
        fields = [
            "variant",
            "quantity",
            "weight",
            "touch",
            "rate",
            "description",
            "stock",
            "movement_type",
            # "journal_entry",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # self.fields["movement_type"].widget = HiddenInput()
        # self.fields["movement_type"].initial = Movement.objects.get(name="In")
        # self.fields["stock"].widget = HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        stock = cleaned_data.get("stock")
        variant = cleaned_data.get("variant")

        # Ensure either variant or stock is provided
        if not stock and not variant:
            raise ValidationError("Either variant or stock must be provided.")

        if not stock:
            variant = cleaned_data.get("variant")
            sku = cleaned_data.get("sku")
            quantity = cleaned_data.get("quantity")
            weight = cleaned_data.get("weight")
            touch = cleaned_data.get("touch")
            rate = cleaned_data.get("rate")
            stock = Stock.objects.create(
                weight=weight,
                quantity=quantity,
                variant=variant,
                sku=sku,
                purchase_touch=touch,
            )
            print(f"stock: {stock}")
            cleaned_data["stock"] = stock
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        # instance.movement_type = Movement.objects.get(name="In")

        if commit:
            instance.save()

        instance.stock.update_status()
        return instance


#  not relevant
class StockOutForm(forms.ModelForm):
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 2, "cols": 15}))

    class Meta:
        model = StockTransaction
        fields = ["stock", "quantity", "weight", "description", "movement_type"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["movement_type"].initial = Movement.objects.get(name="Out")
        self.fields["movement_type"].widget = HiddenInput()

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.movement_type = Movement.objects.get(name="Out")
        if commit:
            instance.save()

        instance.stock.update()
        return instance


class AttributeValueSelectionForm(forms.Form):
    product_attributes = forms.ModelMultipleChoiceField(
        queryset=AttributeValue.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    variant_attributes = forms.ModelMultipleChoiceField(
        queryset=AttributeValue.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        product_type = kwargs.pop("product_type", None)
        super().__init__(*args, **kwargs)

        if product_type:
            self.fields["product_attributes"].queryset = AttributeValue.objects.filter(
                attribute__in=product_type.product_attributes.all()
            )
            self.fields["variant_attributes"].queryset = AttributeValue.objects.filter(
                attribute__in=product_type.variant_attributes.all()
            )
