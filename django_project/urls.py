import environ
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from django_project.shared_urlpatterns import shared_urlpatterns

env = environ.Env()
environ.Env.read_env()

secret_admin_url = env("SECRET_ADMIN_URL", default="admin")

urlpatterns = [path(secret_admin_url + "/", admin.site.urls)] + shared_urlpatterns

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
