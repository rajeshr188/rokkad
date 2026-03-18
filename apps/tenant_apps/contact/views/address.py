from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from ..forms import AddressForm
from ..models import Address, Customer
from .common import get_customer_for_detail, render_customer_detail_fragment


@login_required
def address_list(request, pk: int = None):
    customer = get_customer_for_detail(pk)
    return render_customer_detail_fragment(request, customer, "customer-addresses-section")


@login_required
def address_create_or_update(request, customer_pk=None, address_pk=None):
    customer = get_object_or_404(Customer, pk=customer_pk)
    address = None
    if address_pk:
        address = get_object_or_404(Address, pk=address_pk, customer=customer)
        form = AddressForm(
            request.POST or None,
            instance=address,
            customer_id=customer.id,
            address_id=address.id,
        )
    else:
        form = AddressForm(request.POST or None, customer_id=customer.id)

    if request.method == "POST" and form.is_valid():
        address = form.save(commit=False)
        address.customer = customer
        address.save()
        if address_pk:
            messages.success(request, f"Address {address} updated.")
        else:
            messages.success(request, f"Address {address} created.")
        customer = get_customer_for_detail(customer.id)
        return render_customer_detail_fragment(
            request,
            customer,
            "customer-addresses-section",
            headers={
                "HX-Retarget": "#customer-addresses-section",
                "HX-Reswap": "outerHTML",
                "HX-Trigger": "contactModalClose",
            },
        )

    # template_name = (
    #     "contact/partials/address_update_form.html" if address_pk else "contact/partials/address_form.html"
    # )
    context = {"form": form, "customer": customer}
    if address:
        context["address"] = address

    return render(request, "contact/address_form.html", context)


def address_set_default(request, pk):
    address = get_object_or_404(Address, pk=pk)
    address.set_default()
    messages.success(request, f"Address {address} set as default.")
    customer = get_customer_for_detail(address.customer_id)
    return render_customer_detail_fragment(request, customer, "customer-addresses-section")


@login_required
def address_detail(request, pk):
    address = get_object_or_404(Address, pk=pk)
    return render_customer_detail_fragment(
        request,
        get_customer_for_detail(address.customer_id),
        "customer-address-item",
        context={"address": address},
    )


@login_required
@require_http_methods(["DELETE"])
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk)
    customer_id = address.customer_id
    address.delete()
    messages.error(request, f"Address {address} deleted.")
    return render_customer_detail_fragment(
        request,
        get_customer_for_detail(customer_id),
        "customer-addresses-section",
    )
