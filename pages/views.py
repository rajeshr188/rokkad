from django.views.generic import TemplateView


class HomePageView(TemplateView):
    template_name = "pages/home.html"

class TenantPageView(TemplateView):
    template_name = "pages/tenant.html"
    
class AboutPageView(TemplateView):
    template_name = "pages/about.html"
