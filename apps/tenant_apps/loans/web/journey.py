"""Read-only operator documentation, under the ordinary Loans access boundary."""
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.tenant_apps.loans.access import loans_workspace_required


@loans_workspace_required
@require_GET
def guide(request):
    return render(request, "loans/journey.html")
