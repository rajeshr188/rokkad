"""Temporary bookmark redirects for the retired Girvi application."""

from django.shortcuts import redirect
from django.urls import path


def pawn_loan_list_redirect(request, *args, **kwargs):
    """Open the canonical Loans application for every legacy Girvi URL."""
    return redirect("loans:pawn_loan_list")


urlpatterns = (
    path("", pawn_loan_list_redirect, name="girvi_retired"),
    path("<path:legacy_path>", pawn_loan_list_redirect, name="girvi_retired_path"),
)
