from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from ..forms import ProofForm
from ..models import Customer, Proof
from .common import get_customer_for_detail, render_customer_detail_fragment


@login_required
def proof_list(request, pk: int = None):
    customer = get_customer_for_detail(pk)
    return render_customer_detail_fragment(request, customer, "customer-proofs-section")


@login_required
def proof_create_or_update(request, customer_pk=None, proof_pk=None):
    customer = get_object_or_404(Customer, pk=customer_pk)
    proof = None

    if proof_pk:
        proof = get_object_or_404(Proof, pk=proof_pk, customer=customer)
        form = ProofForm(
            request.POST or None,
            request.FILES or None,
            instance=proof,
            customer_id=customer.id,
            proof_id=proof.id,
        )
    else:
        form = ProofForm(
            request.POST or None,
            request.FILES or None,
            customer_id=customer.id,
        )

    if request.method == "POST" and form.is_valid():
        proof_obj = form.save(commit=False)
        proof_obj.customer = customer
        proof_obj.save()

        if proof_pk:
            messages.success(
                request, f"Proof ({proof_obj.get_proof_type_display()}) updated."
            )
        else:
            messages.success(
                request, f"Proof ({proof_obj.get_proof_type_display()}) created."
            )

        return render_customer_detail_fragment(
            request,
            get_customer_for_detail(customer.id),
            "customer-proofs-section",
            headers={
                "HX-Retarget": "#customer-proofs-section",
                "HX-Reswap": "outerHTML",
                "HX-Trigger": "contactModalClose",
            },
        )

    context = {"form": form, "customer": customer}
    if proof:
        context["proof"] = proof

    return render(request, "contact/proof_form.html", context)


@login_required
def proof_detail(request, pk):
    proof = get_object_or_404(Proof, pk=pk)
    return render_customer_detail_fragment(
        request,
        get_customer_for_detail(proof.customer_id),
        "customer-proof-item",
        context={"proof": proof},
    )


@login_required
@require_http_methods(["DELETE"])
def proof_delete(request, pk):
    proof = get_object_or_404(Proof, pk=pk)
    proof_display = f"{proof.get_proof_type_display()} - {proof.proof_number}"
    customer_id = proof.customer_id
    proof.delete()
    messages.error(request, f"Proof {proof_display} deleted.")
    return render_customer_detail_fragment(
        request,
        get_customer_for_detail(customer_id),
        "customer-proofs-section",
    )
