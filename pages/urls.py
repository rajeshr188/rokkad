from django.urls import path

from .views import HomePageView, AboutPageView,TenantPageView

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("about/", AboutPageView.as_view(), name="about"),
    path("tenant/", TenantPageView.as_view(), name="tenant"),
]
