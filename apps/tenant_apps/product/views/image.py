from django.views.generic import CreateView, DetailView, ListView, UpdateView

from ..access import ProductActionRequiredMixin
from ..forms import (
    AttributeForm,
    AttributeValueForm,
    ProductImageForm,
    VariantImageForm,
)
from ..models import Attribute, AttributeValue, ProductImage, VariantImage

# from ..filters import ProductFilter,ProductVariantFilter,StockFilterfrom django.shortcuts import get_object_or_404,redirect, render


# from blabel import Labelwriter


class AttributeListView(ProductActionRequiredMixin, ListView):
    model = Attribute
    required_action = "view"


class AttributeCreateView(ProductActionRequiredMixin, CreateView):
    model = Attribute
    form_class = AttributeForm
    required_action = "create"


class AttributeDetailView(ProductActionRequiredMixin, DetailView):
    model = Attribute
    required_action = "view"


class AttributeUpdateView(ProductActionRequiredMixin, UpdateView):
    model = Attribute
    form_class = AttributeForm
    required_action = "edit"


class AttributeValueListView(ProductActionRequiredMixin, ListView):
    model = AttributeValue
    required_action = "view"


class AttributeValueCreateView(ProductActionRequiredMixin, CreateView):
    model = AttributeValue
    form_class = AttributeValueForm
    required_action = "create"


class AttributeValueDetailView(ProductActionRequiredMixin, DetailView):
    model = AttributeValue
    required_action = "view"


class AttributeValueUpdateView(ProductActionRequiredMixin, UpdateView):
    model = AttributeValue
    form_class = AttributeValueForm
    required_action = "edit"


class ProductImageListView(ProductActionRequiredMixin, ListView):
    model = ProductImage
    required_action = "view"


class ProductImageCreateView(ProductActionRequiredMixin, CreateView):
    model = ProductImage
    form_class = ProductImageForm
    required_action = "create"


class ProductImageDetailView(ProductActionRequiredMixin, DetailView):
    model = ProductImage
    required_action = "view"


class ProductImageUpdateView(ProductActionRequiredMixin, UpdateView):
    model = ProductImage
    form_class = ProductImageForm
    required_action = "edit"


class VariantImageListView(ProductActionRequiredMixin, ListView):
    model = VariantImage
    required_action = "view"


class VariantImageCreateView(ProductActionRequiredMixin, CreateView):
    model = VariantImage
    form_class = VariantImageForm
    required_action = "create"


class VariantImageDetailView(ProductActionRequiredMixin, DetailView):
    model = VariantImage
    required_action = "view"


class VariantImageUpdateView(ProductActionRequiredMixin, UpdateView):
    model = VariantImage
    form_class = VariantImageForm
    required_action = "edit"
