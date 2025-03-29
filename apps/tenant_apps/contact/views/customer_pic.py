import base64
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods

from ..forms import CustomerPicForm
from ..models import Customer, CustomerPic


@login_required
def customer_pics(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    pics = customer.pics.all()
    return TemplateResponse(
        request, "contact/customer_pics.html", {"customer": customer, "pics": pics}
    )


@login_required
def add_customer_pic(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    if request.method == "POST":
        form = CustomerPicForm(request.POST, request.FILES)
        if form.is_valid():
            customer_pic = form.save(commit=False)
            customer_pic.customer = customer
            image_data = request.POST.get("image_data")

            if image_data:
                # Generate a unique identifier
                unique_id = uuid.uuid4()

                # Create the image file with the UUID as the name
                image_file = ContentFile(
                    base64.b64decode(image_data.split(",")[1]),
                    name=f"{unique_id}.jpg",
                )
                customer_pic.image = image_file
            elif "image" in request.FILES:
                # Handle image file from local file system
                uploaded_image = request.FILES["image"]
                unique_id = uuid.uuid4()
                uploaded_image.name = f"{unique_id}.jpg"
                customer_pic.image = uploaded_image

            customer_pic.save()
            messages.success(request, "Customer Pic added.")
            return redirect("contact_customer_detail", pk=customer.id)
    else:
        form = CustomerPicForm()
    return render(
        request,
        "contact/add_customer_pic.html",
        {
            "form": form,
            "customer": customer,
            "url": reverse_lazy(
                "contact_customer_pic_add", kwargs={"customer_id": customer.id}
            ),
        },
    )


@login_required
@require_http_methods(["DELETE"])
def customer_pic_delete(request, pk):
    instance = get_object_or_404(CustomerPic, pk=pk)
    instance.delete()
    messages.error(request, f"Customer Pic {instance} deleted.")
    return HttpResponse(status=204, headers={"HX-Trigger": "listChanged"})


@login_required
@require_http_methods(["POST"])
def customer_pic_set_default(request, pk):
    instance = get_object_or_404(CustomerPic, pk=pk)
    customer = instance.customer
    # Update all related CustomerPic instances to set is_default to False
    CustomerPic.objects.filter(customer=customer).update(is_default=False)
    # Set the selected CustomerPic instance to be the default
    instance.is_default = True
    instance.save()
    messages.success(request, f"Customer Pic {instance} set as default.")
    return HttpResponse(status=204, headers={"HX-Trigger": "listChanged"})
