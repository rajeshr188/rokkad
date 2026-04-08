# views.py
from email import message

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django_tables2 import RequestConfig

from apps.tenant_apps.girvi.forms import (
    LoanItemForm,
    RepledgedLoanItemForm,
)
from apps.tenant_apps.girvi.models import (
    BaseLoan,
    GivenLoan,
    TakenLoan,
    RepledgedLoanItem,
    LoanItemPic,
)

from ..filters import LoanItemFilter
from ..models import LoanItem
from ..tables import LoanItemTable


def loanitem_list(request):
    filter = LoanItemFilter(request.GET, queryset=LoanItem.objects.all())
    table = LoanItemTable(filter.qs)
    RequestConfig(request, paginate={"per_page": 10}).configure(table)
    return render(
        request, "girvi/loan/loanitem_list.html", {"table": table, "filter": filter}
    )


@login_required
def loanitem_delete(request, parent_id, id):
    item = get_object_or_404(LoanItem, id=id, loan_id=parent_id)
    loan = item.loan
    item.delete()
    messages.error(request, f"Item {item} Deleted")
    loan.save()
    return HttpResponse(status=204, headers={"HX-Trigger": "loanChanged"})


@login_required
def loanitem_detail(request, pk):
    item = get_object_or_404(LoanItem, pk=pk)
    url = item.get_hx_edit_url()
    return render(
        request, "girvi/partials/item-inline-new.html", {"object": item, "url": url}
    )


@login_required
def repledgedloanitem_detail(request, pk):
    item = get_object_or_404(RepledgedLoanItem, pk=pk)
    return render(
        request, "girvi/partials/repledged_item_inline_new.html", {"object": item}
    )


@login_required
def repledged_loanitem_delete(request, parent_id, id):
    item = get_object_or_404(RepledgedLoanItem, id=id, loan_id=parent_id)
    loan = item.loan
    item.delete()
    messages.error(request, f"Repledged Item {item} Deleted")
    loan.save()
    return HttpResponse(status=204, headers={"HX-Trigger": "loanChanged"})


@login_required
def loanitem_create_update(request, parent_id, id=None):
    # Try to get as GivenLoan or TakenLoan
    try:
        parent_obj = GivenLoan.objects.get(id=parent_id)
        is_given_loan = True
    except GivenLoan.DoesNotExist:
        parent_obj = get_object_or_404(TakenLoan, id=parent_id)
        is_given_loan = False

    if parent_obj.status not in ["Created", "Draft", "PendingApproval", "Approved"]:
        messages.error(request, "Cannot add or edit items after loan is disbursed or closed.")
        return redirect(parent_obj.get_absolute_url())

    instance = None
    message = "Item Created"
    form_class = LoanItemForm if is_given_loan else RepledgedLoanItemForm
    model_class = LoanItem if is_given_loan else RepledgedLoanItem
    template_name = (
        "girvi/partials/item-form.html"
        if is_given_loan
        else "girvi/partials/repledged_item_form.html"
    )

    if id:
        instance = get_object_or_404(model_class, id=id, loan=parent_obj)
        message = "Item Updated"

    if request.method == "POST":
        form = form_class(request.POST, request.FILES, instance=instance)
        
        if form.is_valid():
            new_obj = form.save(commit=False)
            new_obj.loan = parent_obj
            if not is_given_loan:
                new_obj.new_loan = parent_obj
                # Use custody status instead of boolean field
                new_obj.original_loanitem.custody_status = "with_lender"
                new_obj.original_loanitem.save()

            new_obj.save()
            
            messages.success(request, f"{message} : {new_obj.id}")
            context = {"object": new_obj, "i": new_obj}

            if request.htmx:
                return HttpResponse(status=204, headers={"HX-Trigger": "loanChanged"})
            if is_given_loan:
                return render(request, "girvi/partials/item-inline-new.html", context)
            return render(
                request, "girvi/partials/repledged_item_inline_new.html", context
            )
    else:
        form = form_class(instance=instance)

    url = reverse("girvi:loanitem_create_update", kwargs={"parent_id": parent_obj.id})
    if instance:
        url = instance.get_hx_edit_url()

    context = {"url": url, "form": form, "object": instance}
    return render(request, template_name, context)


@login_required
def loanitem_picture_modal(request, item_id):
    """Display modal for adding pictures to a loan item."""
    item = get_object_or_404(LoanItem, pk=item_id)
    pictures = item.pictures.all()
    context = {
        "item": item,
        "pictures": pictures,
    }
    return render(request, "girvi/partials/item-picture-modal.html", context)


@login_required
def loanitem_picture_add(request, item_id):
    """Add a picture to a loan item via form submission."""
    item = get_object_or_404(LoanItem, pk=item_id)
    
    if request.method == "POST":
        pic_file = request.FILES.get("pic")
        description = request.POST.get("description", "")
        is_default = request.POST.get("is_default") == "on"
        
        if pic_file:
            # Create picture record
            LoanItemPic.objects.create(
                loan_item=item,
                loan=item.loan,
                pic=pic_file,
                description=description,
                is_default=is_default,
            )
            messages.success(request, "Picture added successfully")
            return HttpResponse(status=204, headers={"HX-Trigger": "pictureAdded"})
    
    return HttpResponse(status=400)


@login_required
def loanitem_picture_delete(request, item_id, pic_id):
    """Delete a picture from a loan item."""
    item = get_object_or_404(LoanItem, pk=item_id)
    pic = get_object_or_404(LoanItemPic, pk=pic_id, loan_item=item)
    pic.delete()
    messages.success(request, "Picture deleted")
    return HttpResponse(status=204, headers={"HX-Trigger": "pictureDeleted"})
