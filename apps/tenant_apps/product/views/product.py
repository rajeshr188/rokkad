from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse_lazy
from django.views.generic import DeleteView

from apps.tenant_apps.utils.htmx_utils import for_htmx

from ..access import ProductActionRequiredMixin, product_action_required
from ..filters import ProductFilter
from ..forms import ProductForm, ProductVariantForm
from ..models import Product, ProductType, ProductVariant


PRODUCT_SORTS = {
    "name": "name",
    "category": "category__name",
    "type": "product_type__name",
}


def _apply_sorting(queryset, sort_key, direction, allowed_sorts):
    sort_field = allowed_sorts.get(sort_key, allowed_sorts["name"])
    if direction == "desc":
        sort_field = f"-{sort_field}"
    return queryset.order_by(sort_field)


# create product_list with filter view
@product_action_required("view")
@for_htmx(use_block_from_params=True)
def product_list(request):
    products = (
        Product.objects.select_related("category", "product_type")
        .prefetch_related("variants", "images", "attributes__values")
        .all()
    )
    filter = ProductFilter(request.GET, queryset=products)
    sort_key = request.GET.get("sort", "name")
    direction = request.GET.get("dir", "asc")
    view_mode = request.GET.get("view", "table")
    sorted_qs = _apply_sorting(filter.qs, sort_key, direction, PRODUCT_SORTS)
    paginator = Paginator(sorted_qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    ctx = {
        "filter": filter,
        "page_obj": page_obj,
        "object_list": page_obj.object_list,
        "page_title": "Products",
        "sort_key": sort_key,
        "sort_dir": direction,
        "view_mode": view_mode,
    }
    return TemplateResponse(request, "product/product_list.html", ctx)


@product_action_required("create")
@for_htmx(use_block="content")
def product_create(request, type_pk):
    product_type = get_object_or_404(ProductType, pk=type_pk)
    create_variant = not product_type.has_variants
    product = Product()
    product.product_type = product_type
    product_form = ProductForm(request.POST or None, instance=product)
    if create_variant:
        variant = ProductVariant(product=product)
        variant_form = ProductVariantForm(
            request.POST or None, instance=variant, prefix="variant"
        )
        variant_errors = not variant_form.is_valid()
    else:
        variant_form = None
        variant_errors = False

    if product_form.is_valid() and not variant_errors:
        product = product_form.save()
        if create_variant:
            variant.product = product
            variant_form.save()

        return redirect("product_product_detail", pk=product.pk)
    ctx = {
        "product_form": product_form,
        "variant_form": variant_form,
        "product": product,
    }
    return TemplateResponse(request, "product/product_form.html", ctx)


@product_action_required("view")
@for_htmx(use_block="content")
def product_detail(request, pk):
    products = Product.objects.prefetch_related("variants", "images").all()
    product = get_object_or_404(products, pk=pk)
    variants = product.variants.all()
    ctx = {"object": product, "variants": variants}
    return TemplateResponse(request, "product/product_detail.html", ctx)


@product_action_required("edit")
def product_edit(request, pk):
    product = get_object_or_404(Product.objects.prefetch_related("variants"), pk=pk)
    form = ProductForm(request.POST or None, instance=product)

    edit_variant = not product.product_type.has_variants
    if edit_variant:
        variant = product.variants.first() or ProductVariant(product=product)
        variant_form = ProductVariantForm(
            request.POST or None, instance=variant, prefix="variant"
        )
        variant_errors = not variant_form.is_valid()
    else:
        variant_form = None
        variant_errors = False

    if form.is_valid() and not variant_errors:
        product = form.save()
        if edit_variant:
            variant_form.save()
        return redirect("product_product_detail", pk=product.pk)
    ctx = {"product": product, "product_form": form, "variant_form": variant_form}
    return TemplateResponse(request, "product/product_form.html", ctx)


class ProductDeleteView(ProductActionRequiredMixin, DeleteView):
    model = Product
    required_action = "delete"
    success_url = reverse_lazy("product_product_list")
