"""Temporary bookmark redirects for the retired Contact application."""

from django.shortcuts import redirect
from django.urls import path


def party_list_redirect(request, *args, **kwargs):
    """Open the canonical Party application for every legacy Contact URL."""
    return redirect("party:party_list")


urlpatterns = (
    path("", party_list_redirect, name="contact_retired"),
    path("<path:legacy_path>", party_list_redirect, name="contact_retired_path"),
)
