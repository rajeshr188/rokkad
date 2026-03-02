from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from ..forms import ProofForm
from ..models import Customer, Proof


@login_required
def proof_list(request, pk: int = None):
    """List all proofs for a customer"""
    customer = get_object_or_404(Customer, id=pk)
    proofs = customer.proofs.all()
    return render(
        request,
        "contact/proof_list.html",
        {"proofs": proofs, "customer_id": customer.id},
    )


@login_required
def proof_create_or_update(request, customer_pk=None, proof_pk=None):
    """Create or update a proof document for a customer"""
    customer = get_object_or_404(Customer, pk=customer_pk)
    proof = None

    if proof_pk:
        proof = get_object_or_404(Proof, pk=proof_pk)
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

        return render(request, "contact/proof_detail.html", context={"i": proof_obj})

    context = {"form": form, "customer": customer}
    if proof:
        context["proof"] = proof

    return render(request, "partials/crispy_form.html", context)


@login_required
def proof_detail(request, pk):
    """View proof details"""
    proof = get_object_or_404(Proof, pk=pk)
    return render(request, "contact/proof_detail.html", context={"i": proof})


@login_required
@require_http_methods(["DELETE"])
def proof_delete(request, pk):
    """Delete a proof document"""
    proof = get_object_or_404(Proof, pk=pk)
    proof_display = f"{proof.get_proof_type_display()} - {proof.proof_number}"
    proof.delete()
    messages.error(request, f"Proof {proof_display} deleted.")
    return HttpResponse("")
