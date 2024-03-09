from django.urls import path

from .views import *

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("about/", AboutPageView.as_view(), name="about"),
    path("tenant/", TenantPageView.as_view(), name="tenant"),
    path("privacy-policy/", PrivacyPolicy.as_view(), name="privacy_policy"),
    path(
        "cancellation-and-refund/",
        CancellationAndRefund.as_view(),
        name="cancellation_and_refund",
    ),
    path(
        "terms-and-conditions/",
        TermsAndConditions.as_view(),
        name="terms_and_conditions",
    ),
    path("contact/", ContactPageView.as_view(), name="contact"),
    path("help/", HelpPageView.as_view(), name="help"),
    path("faq/", FaqPageView.as_view(), name="faq"),
    path("dashboard/", Dashboard, name="dashboard"),
]
