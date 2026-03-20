from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import HTML, Column, Div, Fieldset, Layout, Row
from django.utils.text import slugify
from django.utils.translation import pgettext_lazy
from django_select2 import forms as s2forms
from django_select2.forms import Select2MultipleWidget, Select2Widget
from mptt.forms import TreeNodeChoiceField

from .attributes import *
from .models import *


class CrispyFormMixin:
    def setup_form_helper(self, layout=None):
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.render_unmentioned_fields = False
        self.helper.layout = layout or Layout(*self.fields.keys())


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


class CategoryForm(CrispyFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_form_helper(
            Layout(
                Row(Column("name"), Column("parent")),
                "description",
            )
        )

    class Meta:
        model = Category
        fields = ["name", "description", "parent"]


class ProductTypeForm(CrispyFormMixin, forms.ModelForm):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["has_variants"].help_text = "When enabled, you can create multiple variants (e.g. size, colour) for any product of this type."
        self.fields["product_attributes"].help_text = "Attributes shared by all products of this type (e.g. Material, Brand)."
        self.fields["variant_attributes"].help_text = "Attributes that differ between variants of the same product (e.g. Size, Colour). Only available when variants are enabled."
        self.setup_form_helper(
            Layout(
                Fieldset(
                    "Basic Info",
                    Row(
                        Column("name", css_class="col-md-8"),
                        Column(
                            Div(
                                HTML('<label class="form-label">Options</label>'),
                                "has_variants",
                                css_class="d-flex flex-column pt-2",
                            ),
                            css_class="col-md-4",
                        ),
                    ),
                ),
                Fieldset(
                    "Product-level Attributes",
                    HTML('<p class="text-muted small">These attributes apply to all products of this type and do not vary between variants.</p>'),
                    "product_attributes",
                ),
                Fieldset(
                    "Variant-level Attributes",
                    HTML('<p class="text-muted small">These attributes distinguish variants within a product. Requires variants to be enabled.</p>'),
                    "variant_attributes",
                ),
            )
        )


class AttributesMixin:
    """Form mixin that dynamically adds attribute fields."""

    available_attributes = Attribute.objects.none()

    # Keep explicit subclass configuration to avoid accidental misuse.
    model_attributes_field = None

    def __init__(self, *args, **kwargs):
        if not self.model_attributes_field:
            raise Exception(
                "model_attributes_field must be set in subclasses of "
                "AttributesMixin."
            )

    def prepare_fields_for_attributes(self):
        initial_values = self.get_initial_attribute_values()
        for attribute in self.available_attributes:
            field_defaults = {
                "label": attribute.name,
                "required": False,
                "initial": initial_values.get(attribute.pk),
            }
            if attribute.has_values():
                field = ModelChoiceOrCreationField(
                    queryset=attribute.values.all(), **field_defaults
                )
            else:
                field = forms.CharField(**field_defaults)
            self.fields[attribute.get_formfield_name()] = field

    def get_initial_attribute_values(self):
        initial_values = {}

        if getattr(self.instance, "pk", None):
            if isinstance(self.instance, ProductVariant):
                assignments = (
                    AssignedVariantAttribute.objects.filter(variant=self.instance)
                    .select_related("assignment__attribute")
                    .prefetch_related("values")
                )
            else:
                assignments = (
                    AssignedProductAttribute.objects.filter(product=self.instance)
                    .select_related("assignment__attribute")
                    .prefetch_related("values")
                )

            for assigned in assignments:
                values = list(assigned.values.all())
                if not values:
                    continue
                values.sort(key=lambda v: ((v.sort_order is None), v.sort_order or 0, v.pk))
                initial_values[assigned.assignment.attribute_id] = values[0]

        return initial_values

    def iter_attribute_fields(self):
        for attr in self.available_attributes:
            yield self[attr.get_formfield_name()]

    def get_saved_attributes(self):
        values_by_attribute = {}
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
                values_by_attribute[attr.pk] = value
        return {"values_by_attribute": values_by_attribute}

    def save_normalized_attributes(self, values_by_attribute):
        instance = self.instance
        if not getattr(instance, "pk", None):
            return

        if isinstance(instance, ProductVariant):
            assignment_model = AttributeVariant
            assigned_model = AssignedVariantAttribute
            subject_filter = {"variant": instance}
            subject_field = "variant"
            product_type = instance.product.product_type
        else:
            assignment_model = AttributeProduct
            assigned_model = AssignedProductAttribute
            subject_filter = {"product": instance}
            subject_field = "product"
            product_type = instance.product_type

        existing_assignments = {
            assigned.assignment.attribute_id: assigned
            for assigned in assigned_model.objects.filter(**subject_filter).select_related(
                "assignment__attribute"
            )
        }
        keep_attr_ids = set(values_by_attribute.keys())

        for attr_id, assigned in existing_assignments.items():
            if attr_id not in keep_attr_ids:
                assigned.delete()

        for attr_id, value in values_by_attribute.items():
            assignment, _ = assignment_model.objects.get_or_create(
                product_type=product_type,
                attribute_id=attr_id,
            )
            payload = {subject_field: instance, "assignment": assignment}
            assigned, _ = assigned_model.objects.get_or_create(**payload)
            assigned.values.set([value])


class ProductForm(CrispyFormMixin, forms.ModelForm, AttributesMixin):
    category = TreeNodeChoiceField(
        queryset=Category.objects.all(), label=pgettext_lazy("Category", "Category")
    )
    model_attributes_field = "normalized_attributes"

    class Meta:
        model = Product
        exclude = ["product_type", "name"]

    def __init__(self, *args, **kwargs):
        super(ProductForm, self).__init__(*args, **kwargs)
        product_type = self.instance.product_type
        self.available_attributes = product_type.product_attributes.prefetch_related(
            "values"
        ).all()
        self.prepare_fields_for_attributes()
        attribute_fields = [attr.get_formfield_name() for attr in self.available_attributes]
        self.setup_form_helper(
            Layout(
                Fieldset(
                    "Product Details",
                    Row(
                        Column("category", css_class="col-md-6"),
                        Column("description", css_class="col-md-6"),
                    ),
                ),
                Fieldset(
                    "Product Attributes",
                    HTML('<p class="text-muted small mb-3">Attribute values are shared across all variants of this product.</p>'),
                    *attribute_fields,
                ) if attribute_fields else HTML(""),
            )
        )

    def save(self, commit=True):
        attributes = self.get_saved_attributes()
        self.instance.name = (
            self.instance.product_type.name
            + " "
            + generate_name_from_values(
                {
                    attr_id: value
                    for attr_id, value in attributes["values_by_attribute"].items()
                }
            )
        )
        instance = super().save(commit=commit)
        if commit:
            self.save_normalized_attributes(attributes["values_by_attribute"])
        return instance


class ProductVariantForm(CrispyFormMixin, forms.ModelForm, AttributesMixin):
    model_attributes_field = "normalized_attributes"

    class Meta:
        model = ProductVariant
        fields = [
            "sku",
            "product_code",
            "name",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.product.pk:
            self.available_attributes = self.instance.product.product_type.variant_attributes.all().prefetch_related(
                "values"
            )
            self.prepare_fields_for_attributes()
        attribute_fields = [attr.get_formfield_name() for attr in self.available_attributes]
        self.fields["sku"].help_text = "Unique stock-keeping unit identifier."
        self.fields["product_code"].help_text = "Internal product code for this variant."
        self.setup_form_helper(
            Layout(
                Fieldset(
                    "Variant Identity",
                    Row(
                        Column("sku", css_class="col-md-4"),
                        Column("product_code", css_class="col-md-4"),
                        Column("name", css_class="col-md-4"),
                    ),
                ),
                Fieldset(
                    "Variant Attributes",
                    HTML('<p class="text-muted small mb-3">Attribute values that define how this variant differs from others in the same product.</p>'),
                    *attribute_fields,
                ) if attribute_fields else HTML(""),
            )
        )

    def save(self, commit=True):
        data = self.get_saved_attributes()
        self.instance.name = (
            self.instance.product.name
            + " "
            + generate_name_from_values(
                {
                    attr_id: value
                    for attr_id, value in data["values_by_attribute"].items()
                }
            )
        )
        instance = super().save(commit=commit)
        if commit:
            self.save_normalized_attributes(data["values_by_attribute"])
        return instance


class AttributeForm(CrispyFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_form_helper(Layout("name"))

    class Meta:
        model = Attribute
        fields = ["name"]


class AttributeValueForm(CrispyFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_form_helper(
            Layout(
                Row(Column("name"), Column("value")),
                "attribute",
            )
        )

    class Meta:
        model = AttributeValue
        fields = ["name", "value", "attribute"]


class ProductImageForm(CrispyFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_form_helper(
            Layout(
                "product",
                "image",
                "alt",
            )
        )

    class Meta:
        model = ProductImage
        fields = ["product", "image", "alt"]


class VariantImageForm(CrispyFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_form_helper()

    class Meta:
        model = VariantImage
        fields = "__all__"


class StockForm(CrispyFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_form_helper()

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


class UniqueForm(CrispyFormMixin, forms.Form):
    weight = forms.DecimalField(max_digits=10, decimal_places=3)
    quantity = forms.IntegerField()
    is_unique = forms.BooleanField(initial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_form_helper(Layout(Row(Column("weight"), Column("quantity")), "is_unique"))


class StockStatementForm(CrispyFormMixin, forms.Form):
    stock = forms.ModelChoiceField(queryset=Stock.objects.all(), widget=Select2Widget)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_form_helper()

    class Meta:
        model = StockStatement
        fields = ["stock", "Closing_wt", "Closing_qty"]


class PricingTierForm(CrispyFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_form_helper(
            Layout(
                Row(Column("name", css_class="col-md-6"), Column("parent", css_class="col-md-6")),
                "description",
                "minimum_quantity",
            )
        )

    class Meta:
        model = PricingTier
        fields = ["name", "description", "minimum_quantity", "parent"]


class PricingTierProductPriceForm(CrispyFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_form_helper()

    class Meta:
        model = PricingTierProductPrice
        fields = "__all__"


class StockInForm(CrispyFormMixin, forms.ModelForm):
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
        self.setup_form_helper(
            Layout(
                Row(Column("variant", css_class="col-md-6"), Column("stock", css_class="col-md-6")),
                Row(
                    Column("quantity", css_class="col-md-3"),
                    Column("weight", css_class="col-md-3"),
                    Column("touch", css_class="col-md-3"),
                    Column("rate", css_class="col-md-3"),
                ),
                "description",
                "movement_type",
            )
        )
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
class StockOutForm(CrispyFormMixin, forms.ModelForm):
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 2, "cols": 15}))

    class Meta:
        model = StockTransaction
        fields = ["stock", "quantity", "weight", "description", "movement_type"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["movement_type"].initial = Movement.objects.get(name="Out")
        self.fields["movement_type"].widget = HiddenInput()
        self.setup_form_helper(
            Layout(
                Row(Column("stock", css_class="col-md-4"), Column("quantity", css_class="col-md-4"), Column("weight", css_class="col-md-4")),
                "description",
                "movement_type",
            )
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.movement_type = Movement.objects.get(name="Out")
        if commit:
            instance.save()

        instance.stock.update()
        return instance


class AttributeValueSelectionForm(CrispyFormMixin, forms.Form):
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        widget=Select2Widget,
        required=True,
    )
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

        self.setup_form_helper(
            Layout(
                "category",
                Fieldset("Product Attribute Values", "product_attributes"),
                Fieldset("Variant Attribute Values", "variant_attributes"),
            )
        )
