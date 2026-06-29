from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse_lazy
from django.views.generic import DeleteView

from apps.tenant_apps.utils.htmx_utils import for_htmx

from ..access import ProductActionRequiredMixin, product_action_required
from ..filters import ProductVariantFilter
from ..forms import ProductVariantForm
from ..models import Product, ProductVariant


PRODUCT_VARIANT_SORTS = {
    "sku": "sku",
    "code": "product_code",
    "name": "name",
    "product": "product__name",
    "type": "product__product_type__name",
}


def _apply_sorting(queryset, sort_key, direction, allowed_sorts):
    sort_field = allowed_sorts.get(sort_key, allowed_sorts["name"])
    if direction == "desc":
        sort_field = f"-{sort_field}"
    return queryset.order_by(sort_field)


@product_action_required("view")
@for_htmx(use_block_from_params=True)
def productvariant_list(request):
    variants = ProductVariant.objects.select_related(
        "product", "product__product_type"
    ).prefetch_related("attributes__values")
    filter = ProductVariantFilter(request.GET, queryset=variants)
    sort_key = request.GET.get("sort", "name")
    direction = request.GET.get("dir", "asc")
    view_mode = request.GET.get("view", "table")
    sorted_qs = _apply_sorting(filter.qs, sort_key, direction, PRODUCT_VARIANT_SORTS)
    paginator = Paginator(sorted_qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    ctx = {
        "filter": filter,
        "page_obj": page_obj,
        "object_list": page_obj.object_list,
        "page_title": "Product Variants",
        "sort_key": sort_key,
        "sort_dir": direction,
        "view_mode": view_mode,
    }
    return TemplateResponse(request, "product/productvariant_list.html", ctx)


@product_action_required("create")
@for_htmx(use_block="content")
def variant_create(request, pk):
    product = get_object_or_404(Product.objects.all(), pk=pk)
    variant = ProductVariant(product=product)
    form = ProductVariantForm(request.POST or None, instance=variant)
    if form.is_valid():
        form.save()
        return redirect("product_productvariant_detail", pk=variant.pk)
    ctx = {"form": form, "product": product, "variant": variant}
    return TemplateResponse(request, "product/productvariant_form.html", ctx)


@product_action_required("view")
@for_htmx(use_block="content")
def productvariant_detail(request, pk):
    variant = get_object_or_404(ProductVariant.objects.all(), pk=pk)
    return TemplateResponse(
        request, "product/productvariant_detail.html", {"object": variant}
    )


@product_action_required("edit")
@for_htmx(use_block="content")
def productvariant_update(request, pk):
    variant = get_object_or_404(ProductVariant.objects.all(), pk=pk)
    form = ProductVariantForm(request.POST or None, instance=variant)
    if form.is_valid():
        form.save()
        return redirect("product_productvariant_detail", pk=variant.pk)
    ctx = {"form": form, "variant": variant}
    return TemplateResponse(request, "product/productvariant_form.html", ctx)


class ProductVariantDeleteView(ProductActionRequiredMixin, DeleteView):
    model = ProductVariant
    required_action = "delete"
    success_url = reverse_lazy("product_productvariant_list")
