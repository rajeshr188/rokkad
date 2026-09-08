import environ
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from django_project.shared_urlpatterns import shared_urlpatterns
from django_project.media import serve_public_media

env = environ.Env()
environ.Env.read_env()

secret_admin_url = env("SECRET_ADMIN_URL", default="admin")

# Legacy explicit public URLConf. The active setting currently points to
# django_project.urls; keep this file equivalent enough for local overrides.
PLATFORM_ADMIN_URLPATTERNS = [
    path(secret_admin_url + "/", admin.site.urls),
]

urlpatterns = PLATFORM_ADMIN_URLPATTERNS + shared_urlpatterns

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, view=serve_public_media, document_root=settings.MEDIA_ROOT)
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
