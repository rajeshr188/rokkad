from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from ..forms import CustomerRelationshipForm
from ..models import Customer, CustomerRelationship


@login_required
def relationship_save(request, customer_id, relationship_id=None):
    customer = get_object_or_404(Customer, pk=customer_id)

    relationship_instance = None
    if relationship_id:
        relationship_instance = get_object_or_404(
            CustomerRelationship, pk=relationship_id
        )

    if request.method == "POST":
        form = CustomerRelationshipForm(
            request.POST, instance=relationship_instance, customer=customer
        )
        if form.is_valid():
            relationship_instance = form.save(commit=False)
            relationship_instance.customer = customer
            relationship_instance.save()
        messages.success(request, f"Relationship {relationship_instance} updated.")
        response = HttpResponse()
        response["HX-Trigger"] = "listChanged"
        return response
    else:
        form = CustomerRelationshipForm(
            instance=relationship_instance, customer=customer
        )

    return render(
        request,
        "partials/crispy_form.html",
        {"form": form, "customer": customer},
    )


def relationship_delete(request, relationship_id):
    relationship = get_object_or_404(CustomerRelationship, pk=relationship_id)
    relationship.delete()
    messages.error(request, f"Relationship {relationship} deleted.")
    return HttpResponse("")


def relationship_detail(request, relationship_id):
    relationship = get_object_or_404(CustomerRelationship, pk=relationship_id)
    return render(
        request, "contact/relationship_detail.html", context={"i": relationship}
    )


def relationship_list(request, from_customer_id):
    from_customer = get_object_or_404(Customer, pk=from_customer_id)
    relationships = from_customer.relationships_created.all()
    return render(
        request,
        "contact/relationship_list.html",
        {
            "relationships": relationships,
        },
    )
