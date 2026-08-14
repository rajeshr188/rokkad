from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from apps.tenant_apps.girvi.service_modules.printing import GirviDocumentService

from ..models import Release
from .access import girvi_workspace_required


@girvi_workspace_required
def form_h(request, pk):
    release = get_object_or_404(Release, pk=pk)
    result = GirviDocumentService.render_release_form_h(release)
    if not result.ok:
        return HttpResponse(result.error_message or "Failed to generate form.", status=500)
    return GirviDocumentService.build_pdf_response(result)
