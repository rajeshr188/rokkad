from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from apps.orgs.models import Company
from apps.orgs.services.platform_console import require_console_access
from .diagnostics import platform_dashboard, owner_history, selected_ids
from .models import Delivery
from .operations import review_operation, confirm_operation


class ScopeForm(forms.Form):
    workspace_ids=forms.CharField(required=False,max_length=1200,label="Workspace IDs",
        widget=forms.TextInput(attrs={"class":"form-control"}),help_text="Comma-separated IDs, at most 100. Empty uses the configured pilot cohort.")
    def clean_workspace_ids(self):
        raw=self.cleaned_data["workspace_ids"].strip()
        if not raw:return selected_ids()
        try:values=[int(v.strip()) for v in raw.split(",")]
        except ValueError:raise forms.ValidationError("Enter comma-separated positive Workspace IDs.")
        from .diagnostics import validate_ids
        try:return validate_ids(values)
        except ValidationError as exc:raise forms.ValidationError(exc.messages)


@never_cache
@login_required
@require_GET
def platform(request):
    require_console_access(request.user)
    if getattr(request,"workspace",None) is not None:raise PermissionDenied("Open messaging outside a Workspace.")
    form=ScopeForm(request.GET)
    context={"section":"whatsapp","form":form};status=200
    if form.is_valid():
        try:context.update(platform_dashboard(actor=request.user,workspace_ids=form.cleaned_data["workspace_ids"]))
        except ValidationError as exc:context["errors"]=exc.messages;status=400
    else:status=400
    return render(request,"platform_whatsapp/platform.html",context,status=status)


@never_cache
@login_required
@require_GET
def history(request,workspace_slug):
    if getattr(request,"workspace",None) is not None:raise PermissionDenied("Open account messaging outside a Workspace.")
    try:context=owner_history(actor=request.user,workspace_slug=workspace_slug)
    except Company.DoesNotExist:
        from django.http import Http404
        raise Http404
    return render(request,"platform_whatsapp/history.html",context)


@transaction.non_atomic_requests
@never_cache
@login_required
@require_http_methods(["GET","POST"])
def operation(request,workspace_slug,delivery_id,action):
    if getattr(request,"workspace",None) is not None:raise PermissionDenied("Open account or platform messaging outside a Workspace.")
    errors=None;review=None;result=None;status=200
    try:
        if request.method=="POST":
            if request.POST.get("acknowledged")!="on":raise ValidationError("Acknowledge the reviewed action.")
            result=confirm_operation(actor=request.user,token=request.POST.get("token",""),
                workspace_slug=workspace_slug,delivery_id=delivery_id,action=action)
        else:
            review=review_operation(actor=request.user,workspace_slug=workspace_slug,delivery_id=delivery_id,action=action)
    except (ValidationError,Company.DoesNotExist,Delivery.DoesNotExist) as exc:
        errors=exc.messages if isinstance(exc,ValidationError) else ["Messaging source unavailable."];status=409
    return render(request,"platform_whatsapp/operation.html",{"review":review,"result":result,"errors":errors,
        "workspace_slug":workspace_slug,"action":action},status=status)
