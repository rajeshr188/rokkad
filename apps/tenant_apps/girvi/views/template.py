import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from apps.orgs.models import Membership

from ..forms import LoanTemplateForm, TemplateFrameForm
from ..models import GivenLoan, LoanTemplate, TemplateFrame
from ..service_modules.printing import LoanPrintService
from .access import GirviWorkspaceRequiredMixin, girvi_workspace_required


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


def _build_clone_name(source_name):
    base_name = f"{source_name} (Copy)"
    candidate = base_name
    counter = 2
    while LoanTemplate.objects.filter(name=candidate).exists():
        candidate = f"{source_name} (Copy {counter})"
        counter += 1
    return candidate


def _starter_frame_blueprint(template_obj):
    """Return the standard 17 starter frames in centimeters.

    The `label` starter frame is intentionally excluded. The 12 core frames
    use the fixed positions provided, while the remaining existing frames stay intact.
    Coordinates follow PDF origin (bottom-left).
    """
    page_w = float(getattr(template_obj, "page_width", 14.8) or 14.8)
    page_h = float(getattr(template_obj, "page_height", 21.0) or 21.0)

    def cm_value(value):
        return round(max(value, 0.1), 2)

    text_left = cm_value(page_w * 0.08)
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
            "x_pos": cm_value(11.00),
            "y_pos": cm_value(18.60),
            "width": cm_value(3.00),
            "height": cm_value(1.00),
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
            "x_pos": cm_value(10.00),
            "y_pos": cm_value(15.00),
            "width": cm_value(3.50),
            "height": cm_value(1.00),
            "font_size": 11,
        },
        {
            **common,
            "frame_name": "loan_date",
            "field_type": "text",
            "x_pos": cm_value(10.00),
            "y_pos": cm_value(14.20),
            "width": cm_value(3.50),
            "height": cm_value(1.00),
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
            "x_pos": cm_value(4.00),
            "y_pos": cm_value(13.00),
            "width": cm_value(6.00),
            "height": cm_value(3.00),
            "font_size": 9,
        },
        {
            **common,
            "frame_name": "customer_pic",
            "field_type": "image",
            "x_pos": cm_value(1.00),
            "y_pos": cm_value(11.00),
            "width": cm_value(2.50),
            "height": cm_value(2.50),
            "font_size": 9,
        },
        {
            **common,
            "frame_name": "loanitem_pic",
            "field_type": "image",
            "x_pos": cm_value(11.00),
            "y_pos": cm_value(8.00),
            "width": cm_value(2.00),
            "height": cm_value(2.00),
            "font_size": 9,
        },
        {
            **common,
            "frame_name": "loan_desc",
            "field_type": "text",
            "x_pos": cm_value(1.00),
            "y_pos": cm_value(8.00),
            "width": cm_value(10.00),
            "height": cm_value(4.00),
            "font_size": 9,
        },
        {
            **common,
            "frame_name": "weight",
            "field_type": "text",
            "x_pos": cm_value(2.50),
            "y_pos": cm_value(7.00),
            "width": cm_value(7.00),
            "height": cm_value(1.00),
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
            "x_pos": cm_value(11.00),
            "y_pos": cm_value(7.00),
            "width": cm_value(2.50),
            "height": cm_value(1.00),
            "font_size": 10,
        },
        {
            **common,
            "frame_name": "amount",
            "field_type": "text",
            "x_pos": cm_value(2.70),
            "y_pos": cm_value(6.00),
            "width": cm_value(3.00),
            "height": cm_value(1.00),
            "font_size": 11,
        },
        {
            **common,
            "frame_name": "amount_words",
            "field_type": "text",
            "x_pos": cm_value(7.20),
            "y_pos": cm_value(6.00),
            "width": cm_value(6.50),
            "height": cm_value(1.00),
            "font_size": 9,
        },
        {
            **common,
            "frame_name": "loan_qr",
            "field_type": "qr",
            "x_pos": cm_value(10.00),
            "y_pos": cm_value(11.20),
            "width": cm_value(1.80),
            "height": cm_value(1.80),
            "font_size": 10,
        },
    ]


class TemplateWorkspaceAdminMixin(GirviWorkspaceRequiredMixin, LoginRequiredMixin):
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
        context["readiness"] = LoanPrintService.assess_template_readiness(template_obj)
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


@girvi_workspace_required
def template_preview_pdf(request, pk):
    workspace = _require_template_admin(request)
    if workspace is None:
        return redirect("workspace_selector")

    template_obj = get_object_or_404(LoanTemplate, pk=pk)
    sample_loan = (
        GivenLoan.objects.select_related("borrower", "series", "series__license")
        .prefetch_related("loanitems", "borrower__address", "borrower__contactno")
        .order_by("-loan_date", "-pk")
        .first()
    )

    if not sample_loan:
        messages.warning(
            request,
            "No loan is available yet for a PDF preview. Create at least one loan and try again.",
        )
        return redirect(template_obj)

    readiness = LoanPrintService.assess_template_readiness(template_obj)
    _, pdf = LoanPrintService.render_loan_ticket(sample_loan, template=template_obj)

    if pdf is None:
        messages.error(
            request,
            f'PDF preview failed for "{template_obj.name}". '
            f'{LoanPrintService.format_readiness_summary(readiness) or "Review the template setup and server logs for the failing frame."}',
        )
        return redirect(template_obj)

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f"inline; filename='{sample_loan.loan_id}-template-preview.pdf'"
    )
    response["Content-Transfer-Encoding"] = "binary"
    return response


@girvi_workspace_required
def template_test_print(request, pk):
    workspace = _require_template_admin(request)
    if workspace is None:
        return redirect("workspace_selector")

    template_obj = get_object_or_404(LoanTemplate, pk=pk)
    sample_loan = (
        GivenLoan.objects.select_related("borrower", "series", "series__license")
        .prefetch_related("loanitems", "borrower__address", "borrower__contactno")
        .order_by("-loan_date", "-pk")
        .first()
    )

    if not sample_loan:
        messages.warning(
            request,
            "No loan is available yet for a test print. Create at least one loan and try again.",
        )
        return redirect(template_obj)

    readiness = LoanPrintService.assess_template_readiness(template_obj)
    _, pdf = LoanPrintService.render_loan_ticket(sample_loan, template=template_obj)

    if pdf is None:
        messages.error(
            request,
            f'Test print failed for "{template_obj.name}". '
            f'{LoanPrintService.format_readiness_summary(readiness) or "Review the template setup and server logs for the failing frame."}',
        )
        return redirect(template_obj)

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f"inline; filename='{sample_loan.loan_id}-template-test.pdf'"
    )
    response["Content-Transfer-Encoding"] = "binary"
    return response


@girvi_workspace_required
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


@girvi_workspace_required
@require_POST
def template_set_default(request, pk):
    workspace = _require_template_admin(request)
    if workspace is None:
        return redirect("workspace_selector")

    template_obj = get_object_or_404(LoanTemplate, pk=pk)
    readiness = LoanPrintService.assess_template_readiness(template_obj)

    if not readiness["can_set_default"]:
        messages.error(
            request,
            f'Cannot set "{template_obj.name}" as default yet. {LoanPrintService.format_readiness_summary(readiness)}',
        )
        return redirect(template_obj)

    template_obj.set_default()
    messages.success(request, f'Template "{template_obj.name}" is now the default.')
    if readiness["warnings"]:
        messages.warning(
            request,
            "Readiness warnings: " + " ".join(readiness["warnings"][:2]),
        )
    return redirect(template_obj)


@girvi_workspace_required
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


@girvi_workspace_required
@require_POST
def template_clone(request, pk):
    workspace = _require_template_admin(request)
    if workspace is None:
        return redirect("workspace_selector")

    template_obj = get_object_or_404(LoanTemplate, pk=pk)

    with transaction.atomic():
        cloned_template = LoanTemplate.objects.create(
            name=_build_clone_name(template_obj.name),
            base_template=getattr(template_obj.base_template, "name", None),
            dup_template=getattr(template_obj.dup_template, "name", None),
            terms_template=getattr(template_obj.terms_template, "name", None),
            form_d3_template=getattr(template_obj.form_d3_template, "name", None),
            print_option=template_obj.print_option,
            page_width=template_obj.page_width,
            page_height=template_obj.page_height,
            is_active=False,
            is_default=False,
        )

        cloned_frames = [
            TemplateFrame(
                template=cloned_template,
                frame_name=frame.frame_name,
                template_type=frame.template_type,
                field_type=frame.field_type,
                x_pos=frame.x_pos,
                y_pos=frame.y_pos,
                width=frame.width,
                height=frame.height,
                font_size=frame.font_size,
                font_name=frame.font_name,
                show_boundary=frame.show_boundary,
            )
            for frame in template_obj.templateframe_set.all()
        ]
        TemplateFrame.objects.bulk_create(cloned_frames)

    messages.success(
        request,
        f'Cloned "{template_obj.name}" to "{cloned_template.name}" with {len(cloned_frames)} frame(s). Activate it when ready.',
    )
    return redirect(cloned_template)


@girvi_workspace_required
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


@girvi_workspace_required
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


@girvi_workspace_required
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


@girvi_workspace_required
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
