from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from ..forms import CustomerRelationshipForm
from ..models import Customer, CustomerRelationship
from .common import get_customer_for_detail, render_customer_detail_fragment


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
            action = "updated" if relationship_id else "created"
            messages.success(request, f"Relationship {relationship_instance} {action}.")
            return render_customer_detail_fragment(
                request,
                get_customer_for_detail(customer.id),
                "customer-relationships-section",
                headers={
                    "HX-Retarget": "#customer-relationships-section",
                    "HX-Reswap": "outerHTML",
                    "HX-Trigger": "contactModalClose",
                },
            )
    else:
        form = CustomerRelationshipForm(
            instance=relationship_instance, customer=customer
        )

    return render(
        request,
        "contact/relationship_form.html",
        {"form": form, "customer": customer, "relationship": relationship_instance},
    )


def relationship_delete(request, relationship_id):
    relationship = get_object_or_404(CustomerRelationship, pk=relationship_id)
    customer_id = relationship.customer_id
    relationship.delete()
    messages.error(request, f"Relationship {relationship} deleted.")
    return render_customer_detail_fragment(
        request,
        get_customer_for_detail(customer_id),
        "customer-relationships-section",
    )


def relationship_detail(request, relationship_id):
    relationship = get_object_or_404(CustomerRelationship, pk=relationship_id)
    return render_customer_detail_fragment(
        request,
        get_customer_for_detail(relationship.customer_id),
        "customer-relationship-item",
        context={"relationship": relationship},
    )


def relationship_list(request, from_customer_id):
    return render_customer_detail_fragment(
        request,
        get_customer_for_detail(from_customer_id),
        "customer-relationships-section",
    )
