"""Rates public facade for cross-app read access."""


def get_workspace_rate_dashboard_summary():
    from apps.tenant_apps.rates.models import Rate, RateSource

    return {
        "gold_rate": (
            Rate.objects.filter(metal=Rate.Metal.GOLD, purity=Rate.Purity.K24)
            .order_by("-timestamp")
            .first()
        ),
        "silver_rate": (
            Rate.objects.filter(metal=Rate.Metal.SILVER)
            .order_by("-timestamp")
            .first()
        ),
        "has_rate_sources": RateSource.objects.exists(),
    }
