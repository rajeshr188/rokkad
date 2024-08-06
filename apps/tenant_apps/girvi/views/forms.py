from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from apps.tenant_apps.utils.loan_pdf import generate_form_h

from ..models import Loan, Release


def form_h(request, pk):
    release = get_object_or_404(Release, pk=pk)
    pdf = generate_form_h(release)
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="form_h_{release.pk}.pdf"'
    response.write(pdf)
    return response
