from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from ..forms import AddressForm
from ..models import Address, Customer


@login_required
def address_list(request, pk: int = None):
    customer = get_object_or_404(Customer, id=pk)
    addresses = customer.address.all()
    return render(
        request,
        "contact/address_list.html",
        {"addresses": addresses, "customer_id": customer.id},
    )


@login_required
def address_create_or_update(request, customer_pk=None, address_pk=None):
    customer = get_object_or_404(Customer, pk=customer_pk)
    address = None
    if address_pk:
        address = get_object_or_404(Address, pk=address_pk)
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
        # return HttpResponse(headers={"HX-Trigger": "listChanged"})
        return render(request, "contact/address_detail.html", context={"i": address})

    # template_name = (
    #     "contact/partials/address_update_form.html" if address_pk else "contact/partials/address_form.html"
    # )
    context = {"form": form, "customer": customer}
    if address:
        context["address"] = address

    return render(request, "partials/crispy_form.html", context)


def address_set_default(request, pk):
    address = get_object_or_404(Address, pk=pk)
    address.is_default = True
    address.save()
    messages.success(request, f"Address {address} set as default.")
    return HttpResponse(status=204, headers={"HX-Trigger": "listChanged"})


@login_required
def address_detail(request, pk):
    address = get_object_or_404(Address, pk=pk)
    return render(request, "contact/address_detail.html", context={"i": address})


@login_required
@require_http_methods(["DELETE"])
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk)
    address.delete()
    messages.error(request, f"Address {address} deleted.")
    return HttpResponse("")
