"""Girvi Dashboard and Navigation Views"""
from django.shortcuts import render

from apps.tenant_apps.girvi.selectors import (
    build_girvi_dashboard_read_model,
)
from .access import girvi_workspace_required


@girvi_workspace_required
def girvi_dashboard(request):
    """
    Girvi Dashboard: Central hub showing all available operations,
    organized by workflow/entity with counts and quick access links.
    """
    
    context = build_girvi_dashboard_read_model(
        user=request.user,
        workspace=getattr(request, "tenant", None),
    )

    return render(request, 'girvi/dashboard.html', context)
