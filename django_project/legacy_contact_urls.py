"""Temporary bookmark redirects for the retired Contact application."""

from django.shortcuts import redirect
from django.urls import path, reverse


def party_list_redirect(request, *args, **kwargs):
    """Keep tenant bookmarks while serving the exact global support page."""
    if getattr(request, "workspace", None) is None and request.path == reverse("contact"):
        from pages.views import ContactPageView
        return ContactPageView.as_view()(request)
    return redirect("party:party_list")


urlpatterns = (
    path("", party_list_redirect, name="contact_retired"),
    path("<path:legacy_path>", party_list_redirect, name="contact_retired_path"),
)
