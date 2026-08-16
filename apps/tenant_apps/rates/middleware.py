from django.core.cache import cache
from django.db.models import Max
from django.utils.deprecation import MiddlewareMixin

from .models import Rate


# in case the rate needs tobe in cache
class RateMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # Check if the user is authenticated
        if not request.user.is_authenticated:
            return

        workspace = getattr(request, "workspace", None)
        if workspace is None:
            request.grate = None
            request.srate = None
            request.brate = None
            return

        cache_keys = {
            Rate.Metal.GOLD: f"workspace:{workspace.pk}:gold_rate",
            Rate.Metal.SILVER: f"workspace:{workspace.pk}:silver_rate",
            Rate.Metal.BRONZE: f"workspace:{workspace.pk}:bronze_rate",
        }
        grate = cache.get(cache_keys[Rate.Metal.GOLD])
        srate = cache.get(cache_keys[Rate.Metal.SILVER])
        brate = cache.get(cache_keys[Rate.Metal.BRONZE])

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
                    cache.set(cache_keys[Rate.Metal.GOLD], grate)
                elif rate["metal"] == Rate.Metal.SILVER and not srate:
                    srate = Rate.objects.get(
                        metal=Rate.Metal.SILVER, timestamp=rate["latest_timestamp"]
                    )
                    cache.set(cache_keys[Rate.Metal.SILVER], srate)
                elif rate["metal"] == Rate.Metal.BRONZE and not brate:
                    brate = Rate.objects.get(
                        metal=Rate.Metal.BRONZE, timestamp=rate["latest_timestamp"]
                    )
                    cache.set(cache_keys[Rate.Metal.BRONZE], brate)

        request.grate = grate
        request.srate = srate
        request.brate = brate
