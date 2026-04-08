import base64
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from ..forms import CustomerPicForm
from ..models import Customer, CustomerPic
from .common import get_customer_for_detail, render_customer_detail_page


@login_required
def customer_pics(request, customer_id):
    """List all pictures for a customer (HTMX-friendly)"""
    customer = get_object_or_404(Customer, id=customer_id)
    pics = customer.pics.all()
    return render(
        request,
        "contact/customer_pics.html",
        {"customer": customer, "pics": pics},
    )


@login_required
def customer_pic_form(request, customer_id):
    """Show form to add/capture customer picture"""
    customer = get_object_or_404(Customer, id=customer_id)
    form = CustomerPicForm()
    return render(
        request,
        "contact/customer_pic_form.html",
        {"form": form, "customer": customer},
    )


@login_required
@require_http_methods(["POST"])
def customer_pic_save(request, customer_id):
    """Save customer picture from camera capture or file upload"""
    customer = get_object_or_404(Customer, id=customer_id)
    form = CustomerPicForm(request.POST, request.FILES)

    if form.is_valid():
        customer_pic = form.save(commit=False)
        customer_pic.customer = customer

        # Handle canvas/camera capture (base64 image data)
        image_data = request.POST.get("image_data")
        if image_data:
            try:
                # Extract base64 data (format: "data:image/jpeg;base64,...")
                is_data_uri = "," in image_data
                if is_data_uri:
                    base64_str = image_data.split(",")[1]
                else:
                    base64_str = image_data

                image_file = ContentFile(
                    base64.b64decode(base64_str),
                    name=f"{uuid.uuid4()}.jpg",
                )
                customer_pic.image = image_file
            except Exception as e:
                messages.error(request, f"Failed to process captured image: {str(e)}")
                return render(
                    request,
                    "contact/customer_pic_form.html",
                    {"form": form, "customer": customer, "error": str(e)},
                )

        # Handle file upload
        elif "image" in request.FILES:
            uploaded_image = request.FILES["image"]
            uploaded_image.name = f"{uuid.uuid4()}.jpg"
            customer_pic.image = uploaded_image

        customer_pic.save()
        messages.success(request, "Customer picture added successfully.")
        return render_customer_detail_page(
            request,
            get_customer_for_detail(customer.id),
            headers={
                "HX-Retarget": "#content",
                "HX-Reswap": "innerHTML",
                "HX-Trigger": "contactModalClose",
            },
        )
    else:
        messages.error(request, "Invalid form data. Please try again.")
        return render(
            request,
            "contact/customer_pic_form.html",
            {"form": form, "customer": customer},
        )


@login_required
@require_http_methods(["DELETE"])
def customer_pic_delete(request, pk):
    """Delete a customer picture"""
    pic = get_object_or_404(CustomerPic, pk=pk)
    customer_id = pic.customer_id
    pic.delete()
    messages.error(request, "Picture deleted.")
    return render_customer_detail_page(request, get_customer_for_detail(customer_id))


@login_required
@require_http_methods(["POST"])
def customer_pic_set_default(request, pk):
    """Set a picture as the default for a customer"""
    pic = get_object_or_404(CustomerPic, pk=pk)
    customer = pic.customer

    # Unset all other defaults
    CustomerPic.objects.filter(customer=customer).update(is_default=False)

    # Set this one as default
    pic.is_default = True
    pic.save()

    messages.success(request, "Picture set as default.")
    return render_customer_detail_page(request, get_customer_for_detail(customer.id))
