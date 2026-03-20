from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.tenant_apps.utils.htmx_utils import for_htmx

from ..models import Attribute, AttributeValue, Product, ProductType, ProductVariant


@login_required
@for_htmx(use_block="content")
def home(request):
    ctx = {
        "stats": {
            "product_types": ProductType.objects.count(),
            "products": Product.objects.count(),
            "variants": ProductVariant.objects.count(),
            "attributes": Attribute.objects.count(),
            "attribute_values": AttributeValue.objects.count(),
        }
    }
    return render(request, "product/home.html", ctx)
