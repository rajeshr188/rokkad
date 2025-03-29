from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from ..forms import ContactForm
from ..models import Contact, Customer


@login_required
def contact_save(request, customer_pk=None, contact_pk=None):
    customer = get_object_or_404(Customer, pk=customer_pk)
    contact = None
    if contact_pk:
        contact = get_object_or_404(Contact, pk=contact_pk)
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
        return render(request, "contact/contact_detail.html", context={"i": f})

    return render(
        request,
        "partials/crispy_form.html",
        context={"form": form, "customer": customer, "contact": contact},
    )


@login_required
def contact_list(request, pk: int = None):
    customer = get_object_or_404(Customer, id=pk)
    contacts = customer.contactno.all()
    return render(
        request,
        "contact/contact_list.html",
        {"contacts": contacts, "customer_id": customer.id},
    )


def contact_set_default(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    contact.is_default = True
    contact.save()
    messages.success(request, f"Contact {contact} set as default.")
    return HttpResponse(status=204, headers={"HX-Trigger": "listChanged"})


@login_required
def contact_detail(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    return render(request, "contact/contact_detail.html", context={"i": contact})


@login_required
@require_http_methods(["DELETE"])
def contact_delete(request, pk):
    contact = get_object_or_404(Contact, pk=pk)
    contact.delete()
    messages.error(request, f"Contact {contact} deleted.")
    return HttpResponse("")
