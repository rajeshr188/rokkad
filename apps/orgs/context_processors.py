from django.conf import settings


def theme_processor(request):
    if request.user.is_authenticated:
        return {"theme": request.tenant.theme, "logo": request.tenant.logo}
    return {"theme": "", "logo": None}
