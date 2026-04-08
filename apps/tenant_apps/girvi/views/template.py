import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.orgs.models import Membership

from ..forms import LoanTemplateForm, TemplateFrameForm
from ..models import LoanTemplate, TemplateFrame


def _require_template_admin(request):
    profile = getattr(request.user, "profile", None)
    workspace = getattr(profile, "workspace", None)
    if workspace is None:
        messages.error(request, "Please select a workspace first.")
        return None

    if request.user == workspace.owner:
        return workspace

    try:
        membership = Membership.objects.select_related("role").get(
            user=request.user,
            company=workspace,
        )
    except Membership.DoesNotExist as exc:
        raise PermissionDenied("Not a workspace member") from exc

    role = membership.role
    role_name = role.name if role else ""
    has_workspace_edit = bool(
        role and role.permissions.filter(codename="workspace_edit").exists()
    )
    if role_name not in {"Owner", "Admin", "Administrator"} and not has_workspace_edit:
        raise PermissionDenied("Owner or admin access is required")

    return workspace


def _build_preview_frames(template_obj):
    page_height = float(template_obj.page_height or 0)
    preview_frames = []
    for frame in template_obj.templateframe_set.order_by("template_type", "frame_name"):
        y_pos = float(frame.y_pos)
        height = float(frame.height)
        preview_frames.append(
            {
                "frame": frame,
                "top_offset": max(page_height - y_pos - height, 0),
                "left_offset": float(frame.x_pos),
                "width": float(frame.width),
                "height": height,
            }
        )
    return preview_frames


def _starter_frame_blueprint(template_obj):
    """Return default starter frames with geometry in centimeters.

    Coordinates follow PDF origin (bottom-left).
    """
    page_w = float(template_obj.page_width or 14.8)
    page_h = float(template_obj.page_height or 21.0)

    def cm_value(value):
        # Keep values in valid, readable precision for DecimalField inputs.
        return round(max(value, 0.1), 2)

    text_left = cm_value(page_w * 0.08)
    right_col = cm_value(page_w * 0.58)
    full_width = cm_value(page_w * 0.84)
    mid_width = cm_value(page_w * 0.40)
    img_size = cm_value(min(page_w * 0.20, page_h * 0.13))
    qr_size = cm_value(min(page_w * 0.18, page_h * 0.12))

    common = {
        "template_type": TemplateFrame.TemplateType.BOTH,
        "font_name": "Helvetica",
        "show_boundary": 1,
    }

    return [
        {
            **common,
            "frame_name": "license_no",
            "field_type": "text",
            "x_pos": text_left,
            "y_pos": cm_value(page_h * 0.93),
            "width": cm_value(page_w * 0.45),
            "height": cm_value(page_h * 0.04),
            "font_size": 9,
        },
        {
            **common,
            "frame_name": "license_name",
            "field_type": "text",
            "x_pos": text_left,
            "y_pos": cm_value(page_h * 0.88),
            "width": cm_value(page_w * 0.55),
            "height": cm_value(page_h * 0.04),
            "font_size": 10,
        },
        {
            **common,
            "frame_name": "license_address",
            "field_type": "text",
            "x_pos": text_left,
            "y_pos": cm_value(page_h * 0.81),
            "width": cm_value(page_w * 0.55),
            "height": cm_value(page_h * 0.06),
            "font_size": 8,
        },
        {
            **common,
            "frame_name": "license_propreitor",
            "field_type": "text",
            "x_pos": text_left,
            "y_pos": cm_value(page_h * 0.76),
            "width": cm_value(page_w * 0.55),
            "height": cm_value(page_h * 0.04),
            "font_size": 8,
        },
        {
            **common,
            "frame_name": "loan_id",
            "field_type": "text",
            "x_pos": right_col,
            "y_pos": cm_value(page_h * 0.92),
            "width": cm_value(page_w * 0.34),
            "height": cm_value(page_h * 0.04),
            "font_size": 11,
        },
        {
            **common,
            "frame_name": "loan_date",
            "field_type": "text",
            "x_pos": right_col,
            "y_pos": cm_value(page_h * 0.87),
            "width": cm_value(page_w * 0.34),
            "height": cm_value(page_h * 0.04),
            "font_size": 10,
        },
        {
            **common,
            "frame_name": "customer_name",
            "field_type": "text",
            "x_pos": text_left,
            "y_pos": cm_value(page_h * 0.71),
            "width": cm_value(page_w * 0.56),
            "height": cm_value(page_h * 0.04),
            "font_size": 10,
        },
        {
            **common,
            "frame_name": "customer_info",
            "field_type": "text",
            "x_pos": text_left,
            "y_pos": cm_value(page_h * 0.59),
            "width": cm_value(page_w * 0.56),
            "height": cm_value(page_h * 0.11),
            "font_size": 9,
        },
        {
            **common,
            "frame_name": "customer_pic",
            "field_type": "image",
            "x_pos": cm_value(page_w * 0.67),
            "y_pos": cm_value(page_h * 0.60),
            "width": img_size,
            "height": img_size,
            "font_size": 9,
        },
        {
            **common,
            "frame_name": "loanitem_pic",
            "field_type": "image",
            "x_pos": cm_value(page_w * 0.67),
            "y_pos": cm_value(page_h * 0.45),
            "width": img_size,
            "height": img_size,
            "font_size": 9,
        },
        {
            **common,
            "frame_name": "loan_desc",
            "field_type": "text",
            "x_pos": text_left,
            "y_pos": cm_value(page_h * 0.40),
            "width": full_width,
            "height": cm_value(page_h * 0.16),
            "font_size": 9,
        },
        {
            **common,
            "frame_name": "weight",
            "field_type": "text",
            "x_pos": text_left,
            "y_pos": cm_value(page_h * 0.33),
            "width": mid_width,
            "height": cm_value(page_h * 0.04),
            "font_size": 10,
        },
        {
            **common,
            "frame_name": "pure",
            "field_type": "text",
            "x_pos": cm_value(page_w * 0.50),
            "y_pos": cm_value(page_h * 0.33),
            "width": cm_value(page_w * 0.20),
            "height": cm_value(page_h * 0.04),
            "font_size": 10,
        },
        {
            **common,
            "frame_name": "value",
            "field_type": "text",
            "x_pos": cm_value(page_w * 0.72),
            "y_pos": cm_value(page_h * 0.33),
            "width": cm_value(page_w * 0.20),
            "height": cm_value(page_h * 0.04),
            "font_size": 10,
        },
        {
            **common,
            "frame_name": "amount",
            "field_type": "text",
            "x_pos": text_left,
            "y_pos": cm_value(page_h * 0.27),
            "width": cm_value(page_w * 0.40),
            "height": cm_value(page_h * 0.04),
            "font_size": 11,
        },
        {
            **common,
            "frame_name": "amount_words",
            "field_type": "text",
            "x_pos": text_left,
            "y_pos": cm_value(page_h * 0.22),
            "width": full_width,
            "height": cm_value(page_h * 0.05),
            "font_size": 9,
        },
        {
            **common,
            "frame_name": "loan_qr",
            "field_type": "qr",
            "x_pos": cm_value(page_w * 0.74),
            "y_pos": cm_value(page_h * 0.08),
            "width": qr_size,
            "height": qr_size,
            "font_size": 10,
        },
        {
            **common,
            "frame_name": "label",
            "field_type": "text",
            "x_pos": text_left,
            "y_pos": cm_value(page_h * 0.08),
            "width": cm_value(page_w * 0.62),
            "height": cm_value(page_h * 0.10),
            "font_size": 8,
        },
    ]


class TemplateWorkspaceAdminMixin(LoginRequiredMixin):
    workspace = None

    def dispatch(self, request, *args, **kwargs):
        self.workspace = _require_template_admin(request)
        if self.workspace is None:
            return redirect("workspace_selector")
        return super().dispatch(request, *args, **kwargs)


class LoanTemplateListView(TemplateWorkspaceAdminMixin, ListView):
    model = LoanTemplate
    template_name = "girvi/template/template_list.html"
    context_object_name = "templates"

    def get_queryset(self):
        return LoanTemplate.objects.order_by("name")


class LoanTemplateDetailView(TemplateWorkspaceAdminMixin, DetailView):
    model = LoanTemplate
    template_name = "girvi/template/template_detail.html"
    context_object_name = "template_obj"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        template_obj = self.object
        context["frames"] = template_obj.templateframe_set.order_by(
            "template_type", "frame_name"
        )
        context["preview_frames"] = _build_preview_frames(template_obj)
        return context


class LoanTemplateCreateView(TemplateWorkspaceAdminMixin, CreateView):
    model = LoanTemplate
    form_class = LoanTemplateForm
    template_name = "girvi/template/template_form.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Template "{self.object.name}" created.')
        return response


class LoanTemplateUpdateView(TemplateWorkspaceAdminMixin, UpdateView):
    model = LoanTemplate
    form_class = LoanTemplateForm
    template_name = "girvi/template/template_form.html"
    context_object_name = "template_obj"

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Template "{self.object.name}" updated.')
        return response


class LoanTemplateDeleteView(TemplateWorkspaceAdminMixin, DeleteView):
    model = LoanTemplate
    template_name = "girvi/template/template_confirm_delete.html"
    context_object_name = "template_obj"
    success_url = reverse_lazy("girvi:girvi_template_list")

    def delete(self, request, *args, **kwargs):
        template_obj = self.get_object()
        messages.success(request, f'Template "{template_obj.name}" deleted.')
        return super().delete(request, *args, **kwargs)


class LoanTemplatePreviewView(TemplateWorkspaceAdminMixin, DetailView):
    model = LoanTemplate
    template_name = "girvi/template/template_preview.html"
    context_object_name = "template_obj"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["preview_frames"] = _build_preview_frames(self.object)
        return context


@login_required
def download_template_pack(request):
    workspace = _require_template_admin(request)
    if workspace is None:
        return redirect("workspace_selector")

    try:
        file_path = os.path.join(settings.BASE_DIR, "template_pack.zip")
        if not os.path.exists(file_path):
            raise Http404("Template pack not found")

        file = open(file_path, "rb")
        response = FileResponse(
            file,
            content_type="application/zip",
            as_attachment=True,
            filename="template_pack.zip",
        )
        response["Content-Length"] = os.path.getsize(file_path)
        return response
    except Exception as exc:
        if "file" in locals():
            file.close()
        raise Http404(f"Error downloading template pack: {str(exc)}")


@login_required
@require_POST
def template_set_default(request, pk):
    workspace = _require_template_admin(request)
    if workspace is None:
        return redirect("workspace_selector")

    template_obj = get_object_or_404(LoanTemplate, pk=pk)
    template_obj.set_default()
    messages.success(request, f'Template "{template_obj.name}" is now the default.')
    return redirect(template_obj)


@login_required
@require_POST
def template_toggle_active(request, pk):
    workspace = _require_template_admin(request)
    if workspace is None:
        return redirect("workspace_selector")

    template_obj = get_object_or_404(LoanTemplate, pk=pk)
    template_obj.is_active = not template_obj.is_active
    if not template_obj.is_active and template_obj.is_default:
        template_obj.is_default = False
    template_obj.save()

    state = "activated" if template_obj.is_active else "deactivated"
    messages.success(request, f'Template "{template_obj.name}" {state}.')
    return redirect(template_obj)


@login_required
def template_frame_create(request, template_pk):
    workspace = _require_template_admin(request)
    if workspace is None:
        return redirect("workspace_selector")

    template_obj = get_object_or_404(LoanTemplate, pk=template_pk)
    if request.method == "POST":
        form = TemplateFrameForm(request.POST, template=template_obj)
        if form.is_valid():
            frame = form.save()
            messages.success(
                request,
                f'Frame "{frame.get_frame_name_display()}" added to "{template_obj.name}".',
            )
            return redirect(template_obj)
    else:
        form = TemplateFrameForm(template=template_obj)

    return render(
        request,
        "girvi/template/frame_form.html",
        {
            "form": form,
            "template_obj": template_obj,
            "frame_obj": None,
        },
    )


@login_required
def template_frame_update(request, template_pk, pk):
    workspace = _require_template_admin(request)
    if workspace is None:
        return redirect("workspace_selector")

    template_obj = get_object_or_404(LoanTemplate, pk=template_pk)
    frame_obj = get_object_or_404(TemplateFrame, pk=pk, template=template_obj)
    if request.method == "POST":
        form = TemplateFrameForm(request.POST, instance=frame_obj, template=template_obj)
        if form.is_valid():
            frame = form.save()
            messages.success(
                request,
                f'Frame "{frame.get_frame_name_display()}" updated.',
            )
            return redirect(template_obj)
    else:
        form = TemplateFrameForm(instance=frame_obj, template=template_obj)

    return render(
        request,
        "girvi/template/frame_form.html",
        {
            "form": form,
            "template_obj": template_obj,
            "frame_obj": frame_obj,
        },
    )


@login_required
@require_POST
def template_frame_delete(request, template_pk, pk):
    workspace = _require_template_admin(request)
    if workspace is None:
        return redirect("workspace_selector")

    template_obj = get_object_or_404(LoanTemplate, pk=template_pk)
    frame_obj = get_object_or_404(TemplateFrame, pk=pk, template=template_obj)
    frame_name = frame_obj.get_frame_name_display()
    frame_obj.delete()
    messages.success(request, f'Frame "{frame_name}" deleted.')
    return redirect(template_obj)


@login_required
@require_POST
def template_create_starter_frames(request, pk):
    workspace = _require_template_admin(request)
    if workspace is None:
        return redirect("workspace_selector")

    template_obj = get_object_or_404(LoanTemplate, pk=pk)
    blueprint = _starter_frame_blueprint(template_obj)

    created = 0
    skipped = 0
    for frame_spec in blueprint:
        _, is_created = TemplateFrame.objects.get_or_create(
            template=template_obj,
            frame_name=frame_spec["frame_name"],
            template_type=frame_spec["template_type"],
            defaults=frame_spec,
        )
        if is_created:
            created += 1
        else:
            skipped += 1

    if created and skipped:
        messages.success(
            request,
            f"Created {created} starter frames and kept {skipped} existing frames unchanged.",
        )
    elif created:
        messages.success(request, f"Created {created} starter frames.")
    else:
        messages.info(request, "Starter frames already exist for this template.")

    return redirect(template_obj)