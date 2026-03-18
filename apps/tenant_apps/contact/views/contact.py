from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from ..forms import ContactForm
from ..models import Contact, Customer
from .common import get_customer_for_detail, render_customer_detail_fragment


@login_required
def contact_save(request, customer_pk=None, contact_pk=None):
    customer = get_object_or_404(Customer, pk=customer_pk)
    contact = None
    if contact_pk:
        contact = get_object_or_404(Contact, pk=contact_pk, customer=customer)
        form = ContactForm(
            request.POST or None,
            instance=contact,
            customer_id=customer.id,
            contact_id=contact.id,
        )
    else:
        form = ContactForm(
            request.POST or None,
            initial={"customer": customer},
            customer_id=customer.id,
        )

    if request.method == "POST" and form.is_valid():
        f = form.save(commit=False)
        f.customer = customer
        f.save()
        if contact:
            messages.success(request, f"Contact {f} updated.")
        else:
            messages.success(request, f"Contact {f} created.")
        customer = get_customer_for_detail(customer.id)
        return render_customer_detail_fragment(
            request,
            customer,
            "customer-contacts-section",
            headers={
                "HX-Retarget": "#customer-contacts-section",
                "HX-Reswap": "outerHTML",
                "HX-Trigger": "contactModalClose",
            },
        )

    return render(
        request,
        "contact/contact_form.html",
        context={"form": form, "customer": customer, "contact": contact},
    )


@login_required
def contact_list(request, pk: int = None):
    customer = get_customer_for_detail(pk)
    return render_customer_detail_fragment(request, customer, "customer-contacts-section")


def contact_set_default(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    contact.set_default()
    messages.success(request, f"Contact {contact} set as default.")
    return render_customer_detail_fragment(
        request,
        get_customer_for_detail(contact.customer_id),
        "customer-contacts-section",
    )


@login_required
def contact_detail(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    return render_customer_detail_fragment(
        request,
        get_customer_for_detail(contact.customer_id),
        "customer-contact-item",
        context={"contact": contact},
    )


@login_required
@require_http_methods(["DELETE"])
def contact_delete(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    customer_id = contact.customer_id
    contact.delete()
    messages.error(request, f"Contact {contact} deleted.")
    return render_customer_detail_fragment(
        request,
        get_customer_for_detail(customer_id),
        "customer-contacts-section",
    )
