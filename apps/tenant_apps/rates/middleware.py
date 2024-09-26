from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Max
from django.utils.deprecation import MiddlewareMixin
from django_tenants.utils import get_public_schema_name

from .models import Rate


# in case the rate needs tobe in cache
class RateMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Check if the user is authenticated
        if not request.user.is_authenticated:
            return
        # Check if the user's workspace is set to a tenant schema
        company = request.user.workspace
        if (
            not company
            or company == ""
            or company.schema_name == get_public_schema_name()
        ):
            request.grate = None
            request.srate = None
            request.brate = None
            return
        grate = cache.get("gold_rate")
        srate = cache.get("silver_rate")
        brate = cache.get("bronze_rate")

        if not (grate and srate and brate):
            latest_rates = (
                Rate.objects.filter(
                    metal__in=[Rate.Metal.GOLD, Rate.Metal.SILVER, Rate.Metal.BRONZE]
                )
                .values("metal")
                .annotate(latest_timestamp=Max("timestamp"))
            )

            for rate in latest_rates:
                if rate["metal"] == Rate.Metal.GOLD and not grate:
                    grate = Rate.objects.get(
                        metal=Rate.Metal.GOLD, timestamp=rate["latest_timestamp"]
                    )
                    cache.set("gold_rate", grate)
                elif rate["metal"] == Rate.Metal.SILVER and not srate:
                    srate = Rate.objects.get(
                        metal=Rate.Metal.SILVER, timestamp=rate["latest_timestamp"]
                    )
                    cache.set("silver_rate", srate)
                elif rate["metal"] == Rate.Metal.BRONZE and not brate:
                    brate = Rate.objects.get(
                        metal=Rate.Metal.BRONZE, timestamp=rate["latest_timestamp"]
                    )

        request.grate = grate
        request.srate = srate
        request.brate = brate
