import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse

from apps.tenant_apps.utils.htmx_utils import for_htmx

from ..forms import AttributeValueSelectionForm, ProductTypeForm
from ..models import (
    AssignedProductAttribute,
    AssignedVariantAttribute,
    AttributeProduct,
    AttributeVariant,
    Category,
    Product,
    ProductType,
    ProductVariant,
)

logger = logging.getLogger(__name__)


def _set_product_attributes(product_obj, attr_values):
    for attr_value in attr_values:
        assignment, _ = AttributeProduct.objects.get_or_create(
            product_type=product_obj.product_type,
            attribute=attr_value.attribute,
        )
        assigned, _ = AssignedProductAttribute.objects.get_or_create(
            product=product_obj,
            assignment=assignment,
        )
        assigned.values.set([attr_value])


def _set_variant_attributes(variant_obj, attr_values):
    for attr_value in attr_values:
        assignment, _ = AttributeVariant.objects.get_or_create(
            product_type=variant_obj.product.product_type,
            attribute=attr_value.attribute,
        )
        assigned, _ = AssignedVariantAttribute.objects.get_or_create(
            variant=variant_obj,
            assignment=assignment,
        )
        assigned.values.set([attr_value])


@login_required
@for_htmx(use_block="content")
def producttype_list(request):
    producttypes = ProductType.objects.all()
    ctx = {"object_list": producttypes}
    return TemplateResponse(request, "product/producttype_list.html", ctx)


@login_required
@for_htmx(use_block="content")
def producttype_create(request):
    form = ProductTypeForm(request.POST or None)
    if form.is_valid():
        producttype = form.save()
        return redirect("product_producttype_detail", pk=producttype.pk)
    ctx = {"form": form}
    return TemplateResponse(request, "product/producttype_form.html", ctx)


@login_required
@for_htmx(use_block="content")
def producttype_detail(request, pk):
    producttype = get_object_or_404(ProductType, pk=pk)
    ctx = {"object": producttype}
    return TemplateResponse(request, "product/producttype_detail.html", ctx)


@login_required
@for_htmx(use_block="content")
def producttype_update(request, pk):
    producttype = get_object_or_404(ProductType, pk=pk)
    form = ProductTypeForm(request.POST or None, instance=producttype)
    if form.is_valid():
        producttype = form.save()
        return redirect("product_producttype_detail", pk=producttype.pk)
    ctx = {"form": form, "producttype": producttype}
    return TemplateResponse(request, "product/producttype_form.html", ctx)


@login_required
def producttype_delete(request, pk):
    producttype = get_object_or_404(ProductType, pk=pk)
    producttype.delete()
    return redirect("product_producttype_list")


import uuid  # Import the uuid module

# views.py
from itertools import product

from django.db import IntegrityError

# def generate_products_and_variants(request, product_type_id):
#     product_type = get_object_or_404(ProductType, id=product_type_id)

#     # Retrieve product attributes and variant attributes
#     product_attributes = product_type.product_attributes.all()
#     variant_attributes = product_type.variant_attributes.all()

#     # Generate all possible combinations of product attributes
#     product_attr_combinations = list(product(*[attr.values.all() for attr in product_attributes]))

#     # Generate all possible combinations of variant attributes
#     variant_attr_combinations = list(product(*[attr.values.all() for attr in variant_attributes]))

#     for product_attr_comb in product_attr_combinations:
#         try:
#             # Create a new Product instance
#             product_g = Product.objects.create(
#                 product_type=product_type,
#                 name=f"{product_type.name} {' '.join([attr_value.name for attr_value in product_attr_comb])}",
#                 description="Generated product",
#                 category=Category.objects.first(),  # Assuming product_type has a category field
#                 attributes={str(attr_value.attribute.id): str(attr_value.id) for attr_value in product_attr_comb},
#                 jattributes={attr_value.attribute.name: attr_value.name for attr_value in product_attr_comb}
#             )
#         except IntegrityError:
#             # Skip product creation if unique constraint exception occurs
#             continue

#         for variant_attr_comb in variant_attr_combinations:
#             # Generate a unique product code
#             product_code = str(uuid.uuid4())[:32]  # Truncate UUID to 32 characters
#             try:
#                 # Create a new ProductVariant instance
#                 ProductVariant.objects.create(
#                     product=product_g,
#                     product_code=product_code,
#                     sku=f"{product_g.name} {' '.join([attr_value.name for attr_value in variant_attr_comb])}",
#                     name=f"{product_g.name} {' '.join([attr_value.name for attr_value in variant_attr_comb])}",
#                     attributes={str(attr_value.attribute.id): str(attr_value.id) for attr_value in variant_attr_comb},
#                     jattributes={attr_value.attribute.name: attr_value.name for attr_value in variant_attr_comb}
#                 )
#             except IntegrityError:
#                 # Skip variant creation if unique constraint exception occurs
#                 continue

#     return redirect("product_producttype_list")


def generate_products_and_variants(request, product_type_id):
    # if any of the attributes has no attributevalues at all then combinations will be empty
    product_type = get_object_or_404(ProductType, id=product_type_id)

    if request.method == "POST":
        form = AttributeValueSelectionForm(request.POST, product_type=product_type)
        if form.is_valid():
            selected_product_attributes = form.cleaned_data["product_attributes"]
            logger.warning(
                f"Selected product attributes: {selected_product_attributes}"
            )
            selected_variant_attributes = form.cleaned_data["variant_attributes"]
            logger.warning(
                f"Selected variant attributes: {selected_variant_attributes}"
            )

            # Generate all possible combinations of selected product attributes
            product_attr_combinations = list(
                product(
                    *[
                        selected_product_attributes.filter(attribute=attr)
                        for attr in product_type.product_attributes.all()
                    ]
                )
            )
            logger.warning(
                f"Product attribute combinations: {product_attr_combinations}"
            )
            # Generate all possible combinations of selected variant attributes
            variant_attr_combinations = list(
                product(
                    *[
                        selected_variant_attributes.filter(attribute=attr)
                        for attr in product_type.variant_attributes.all()
                    ]
                )
            )
            logger.warning(
                f"Variant attribute combinations: {variant_attr_combinations}"
            )
            if not product_attr_combinations:
                logger.warning("No product attribute combinations found.")
            if not variant_attr_combinations:
                logger.warning("No variant attribute combinations found.")

            for product_attr_comb in product_attr_combinations:
                try:
                    # Check if the product already exists
                    product_g, created = Product.objects.get_or_create(
                        product_type=product_type,
                        name=f"{product_type.name} {' '.join([attr_value.name for attr_value in product_attr_comb])}",
                        defaults={
                            "description": "Generated product",
                            "category": Category.objects.first(),
                        },
                    )
                    _set_product_attributes(product_g, product_attr_comb)
                    if created:
                        logger.error(f"Product created: {product_g.name}")
                    else:
                        logger.error(f"Product already exists: {product_g.name}")
                except IntegrityError as e:
                    logger.error(f"IntegrityError while creating product: {e}")
                    continue

                for variant_attr_comb in variant_attr_combinations:
                    # Generate a unique product code
                    product_code = str(uuid.uuid4()).replace("-", "")[
                        :32
                    ]  # Remove hyphens and truncate to 32 characters
                    try:
                        # Create a new ProductVariant instance
                        variant_obj = ProductVariant.objects.create(
                            product=product_g,
                            product_code=product_code,
                            sku=f"{product_g.name} {' '.join([attr_value.name for attr_value in variant_attr_comb])}",
                            name=f"{product_g.name} {' '.join([attr_value.name for attr_value in variant_attr_comb])}",
                        )
                        _set_variant_attributes(variant_obj, variant_attr_comb)
                    except IntegrityError as e:
                        logger.error(f"IntegrityError while creating variant: {e}")
                        # Skip variant creation if unique constraint exception occurs
                        continue

            return redirect("product_producttype_list")
    else:
        form = AttributeValueSelectionForm(product_type=product_type)

    return render(
        request,
        "product/generate_pandv.html",
        {"form": form, "product_type": product_type},
    )
