from django.conf import settings
from django.db import connection
from django.http import Http404, HttpResponseNotFound
from django.urls import set_urlconf
from django_tenants.utils import (
    get_public_schema_name,
    get_public_schema_urlconf,
    get_tenant_domain_model,
    get_tenant_types,
    has_multi_type_tenants,
    remove_www,
)


class TenantMainMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.process_request(request)
        if response is None:
            response = self.get_response(request)
        return response

    def process_request(self, request):
        hostname = self.hostname_from_request(request)
        domain_model = get_tenant_domain_model()

        try:
            tenant = self.get_tenant(domain_model, hostname)
        except domain_model.DoesNotExist:
            return self.no_tenant_found(request, hostname)

        request.tenant = tenant
        self.setup_url_routing(request)
        return None

    def hostname_from_request(self, request):
        return remove_www(request.get_host().split(":")[0])

    def get_tenant(self, domain_model, hostname):
        domain = domain_model.objects.select_related("tenant").get(domain=hostname)
        return domain.tenant

    def no_tenant_found(self, request, hostname):
        if (
            hasattr(settings, "SHOW_PUBLIC_IF_NO_TENANT_FOUND")
            and settings.SHOW_PUBLIC_IF_NO_TENANT_FOUND
        ):
            self.setup_url_routing(request=request, force_public=True)
            return None
        else:
            raise Http404('No tenant for hostname "%s"' % hostname)

    def setup_url_routing(self, request, force_public=False):
        public_schema_name = get_public_schema_name()

        if has_multi_type_tenants():
            tenant_types = get_tenant_types()
            if not hasattr(request, "tenant") or (
                (force_public or request.tenant.schema_name == get_public_schema_name())
                and "URLCONF" in tenant_types[public_schema_name]
            ):
                request.urlconf = get_public_schema_urlconf()
            else:
                tenant_type = request.tenant.get_tenant_type()
                request.urlconf = tenant_types[tenant_type]["URLCONF"]
            set_urlconf(request.urlconf)
        else:
            if hasattr(settings, "PUBLIC_SCHEMA_URLCONF") and (
                force_public or request.tenant.schema_name == get_public_schema_name()
            ):
                request.urlconf = settings.PUBLIC_SCHEMA_URLCONF
                set_urlconf(request.urlconf)


class WorkspaceMiddleware(TenantMainMiddleware):
    def process_request(self, request):
        try:
            hostname = self.hostname_from_request(request)
        except DisallowedHost:
            from django.http import HttpResponseNotFound

            return HttpResponseNotFound()

        if request.user.is_authenticated and request.user.workspace:
            request.user.workspace.domain_url = hostname
            # request.tenant = workspace  # Assign workspace directly as tenant
            connection.set_tenant(
                request.user.workspace
            )  # Set connection to the workspace's schema
            self.setup_url_routing(request)
            return None

        # Set connection to public schema if no workspace or workspace is None
        connection.set_schema_to_public()
        return super().process_request(request)
