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
        company = request.user.profile.workspace
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

# from decimal import Decimal
# from typing import Optional
# from django.core.cache import cache
# from django.db.models import Max
# from django.http import HttpRequest, HttpResponse
# from django.utils.deprecation import MiddlewareMixin
# from django_tenants.utils import get_public_schema_name
# import logging

# from .models import Rate

# logger = logging.getLogger(__name__)

# class RateMiddleware(MiddlewareMixin):
#     """Middleware to handle metal rates caching and retrieval.
    
#     Attaches latest gold, silver and bronze rates to the request object.
#     Handles caching to minimize database queries.
#     """
    
#     CACHE_KEYS = {
#         Rate.Metal.GOLD: "gold_rate",
#         Rate.Metal.SILVER: "silver_rate", 
#         Rate.Metal.BRONZE: "bronze_rate"
#     }
    
#     DEFAULT_RATES = {
#         Rate.Metal.GOLD: Decimal("0.0"),
#         Rate.Metal.SILVER: Decimal("0.0"),
#         Rate.Metal.BRONZE: Decimal("0.0")
#     }

#     def get_cached_rate(self, metal: str) -> Optional[Rate]:
#         """Get rate from cache or return None."""
#         return cache.get(self.CACHE_KEYS[metal])

#     def set_cached_rate(self, metal: str, rate: Rate) -> None:
#         """Set rate in cache."""
#         cache.set(self.CACHE_KEYS[metal], rate)

#     def get_latest_rate(self, metal: str) -> Rate:
#         """Get latest rate for metal type or create default."""
#         try:
#             latest = Rate.objects.filter(metal=metal).latest('timestamp')
#             self.set_cached_rate(metal, latest)
#             return latest.selling_rate
#         except Rate.DoesNotExist:
#             logger.warning(f"No rate found for {metal}, creating default")
#             rate = Rate.objects.create(
#                 metal=metal,
#                 selling_rate=self.DEFAULT_RATES[metal]
#             )
#             self.set_cached_rate(metal, rate)
#             return rate

#     def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
#         """Process incoming request to attach metal rates."""
#         # Early returns
#         if not request.user.is_authenticated:
#             return None
            
#         company = getattr(request.user.profile, 'workspace', None)
#         if not company or company.schema_name == get_public_schema_name():
#             return None

#         try:
#             # Get or fetch rates for each metal
#             for metal in Rate.Metal:
#                 rate = self.get_cached_rate(metal) or self.get_latest_rate(metal) or None
#                 setattr(request, f"{metal.lower()[:1]}rate", rate)
                
#         except Exception as e:
#             logger.error(f"Error processing rates: {str(e)}")
#             # Set default rates on error
#             for metal in Rate.Metal:
#                 setattr(request, f"{metal.lower()[:]}rate", 
#                     None)

#         return None