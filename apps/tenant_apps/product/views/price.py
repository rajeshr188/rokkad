from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse

from ..forms import PriceOverrideForm, PricingTierForm, PricingTierProductPriceForm
from ..models import Price, PricingTier, PricingTierProductPrice


@login_required
def pricing_tier_list(request):
    object_list = PricingTier.objects.select_related("parent").all()
    return TemplateResponse(
        request,
        "product/price/pricingtier_list.html",
        context={"object_list": object_list, "page_title": "Pricing Tiers"},
    )


@login_required
def pricing_tier_detail(request, pk):
    pricing_tier = get_object_or_404(PricingTier, id=pk)
    price_rows = pricing_tier.price_list.select_related("product").all()
    return TemplateResponse(
        request,
        "product/price/pricingtier_detail.html",
        context={
            "obj": pricing_tier,
            "price_rows": price_rows,
            "page_title": f"Pricing Tier: {pricing_tier.name}",
        },
    )


@login_required
def pricing_tier_create(request):
    form = PricingTierForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        pt = form.save()
        messages.success(request, "Pricing tier created.")
        return redirect("product_pricingtier_detail", pk=pt.pk)
    return TemplateResponse(
        request,
        "product/price/pricingtier_form.html",
        context={"form": form, "page_title": "Create Pricing Tier"},
    )


@login_required
def pricing_tier_update(request, pk):
    obj = get_object_or_404(PricingTier, id=pk)
    form = PricingTierForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Pricing tier updated.")
        return redirect("product_pricingtier_detail", pk=obj.pk)
    return TemplateResponse(
        request,
        "product/price/pricingtier_form.html",
        context={"form": form, "obj": obj, "page_title": "Update Pricing Tier"},
    )


@login_required
def pricing_tier_delete(request, pk):
    obj = get_object_or_404(PricingTier, id=pk)
    if request.method != "POST":
        return redirect("product_pricingtier_detail", pk=obj.pk)
    obj.delete()
    messages.success(request, "Pricing tier deleted.")
    return redirect("product_pricingtier_list")


@login_required
def pricing_tier_product_price_create(request, pk):
    pricing_tier = get_object_or_404(PricingTier, id=pk)
    form = PricingTierProductPriceForm(
        request.POST or None,
        pricing_tier=pricing_tier,
    )
    if request.method == "POST":
        if form.is_valid():
            try:
                row = form.save(commit=False)
                row.pricing_tier = pricing_tier
                row.save()
                messages.success(request, "Tier product price created.")
                return redirect("product_pricingtier_detail", pk=pricing_tier.pk)
            except IntegrityError:
                form.add_error(
                    None,
                    "A price for this tier and product already exists.",
                )
    return TemplateResponse(
        request,
        "product/price/productprice_form.html",
        context={
            "form": form,
            "pricing_tier": pricing_tier,
            "page_title": f"Add Product Price - {pricing_tier.name}",
        },
    )


@login_required
def pricing_tier_product_price_update(request, pk):
    obj = get_object_or_404(PricingTierProductPrice, id=pk)
    form = PricingTierProductPriceForm(request.POST or None, instance=obj)
    if request.method == "POST":
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Tier product price updated.")
                return redirect("product_pricingtier_detail", pk=obj.pricing_tier_id)
            except IntegrityError:
                form.add_error(
                    None,
                    "A price for this tier and product already exists.",
                )
    return TemplateResponse(
        request,
        "product/price/productprice_form.html",
        context={
            "form": form,
            "obj": obj,
            "pricing_tier": obj.pricing_tier,
            "page_title": "Update Product Price",
        },
    )


@login_required
def pricing_tier_product_price_delete(request, pk):
    obj = get_object_or_404(PricingTierProductPrice, id=pk)
    if request.method != "POST":
        return redirect("product_pricingtier_detail", pk=obj.pricing_tier_id)
    tier_id = obj.pricing_tier_id
    obj.delete()
    messages.success(request, "Tier product price deleted.")
    return redirect("product_pricingtier_detail", pk=tier_id)


@login_required
def price_override_list(request):
    object_list = Price.objects.select_related("contact", "product", "price_tier").all()
    return TemplateResponse(
        request,
        "product/price/price_override_list.html",
        context={
            "object_list": object_list,
            "page_title": "Contact Price Overrides",
        },
    )


@login_required
def price_override_create(request):
    form = PriceOverrideForm(request.POST or None)
    if request.method == "POST":
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Contact price override created.")
                return redirect("product_price_override_list")
            except IntegrityError:
                form.add_error(
                    None,
                    "A contact override already exists for this contact and product.",
                )
    return TemplateResponse(
        request,
        "product/price/price_override_form.html",
        context={"form": form, "page_title": "Create Contact Price Override"},
    )


@login_required
def price_override_update(request, pk):
    obj = get_object_or_404(Price, id=pk)
    form = PriceOverrideForm(request.POST or None, instance=obj)
    if request.method == "POST":
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Contact price override updated.")
                return redirect("product_price_override_list")
            except IntegrityError:
                form.add_error(
                    None,
                    "A contact override already exists for this contact and product.",
                )
    return TemplateResponse(
        request,
        "product/price/price_override_form.html",
        context={
            "form": form,
            "obj": obj,
            "page_title": "Update Contact Price Override",
        },
    )


@login_required
def price_override_delete(request, pk):
    obj = get_object_or_404(Price, id=pk)
    if request.method != "POST":
        return redirect("product_price_override_list")
    obj.delete()
    messages.success(request, "Contact price override deleted.")
    return redirect("product_price_override_list")
