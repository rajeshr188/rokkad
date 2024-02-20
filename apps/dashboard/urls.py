from django.urls import path,include
from . import views
from django.conf import settings

urlpatterns = [
    path('', views.index, name='index'),
    # Add more paths for your other views here
]
if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns