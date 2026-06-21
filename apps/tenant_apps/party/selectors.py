from .models import Party, PartyRole


def active_parties():
    return Party.objects.filter(status=Party.PartyStatus.ACTIVE)


def parties_with_role(role_key):
    return active_parties().filter(
        roles__role_type__key=role_key,
        roles__status=PartyRole.RoleStatus.ACTIVE,
    )


def party_detail_queryset():
    return Party.objects.prefetch_related(
        "roles__role_type",
        "addresses",
        "contact_methods",
        "identifiers",
        "documents",
        "relationships_from__to_party",
        "relationships_to__from_party",
    )
