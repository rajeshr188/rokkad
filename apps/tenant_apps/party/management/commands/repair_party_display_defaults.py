"""Explicit, scoped repair of missing existing customer display selections."""
import hashlib
import json
from collections import Counter, defaultdict

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.tenancy.context import workspace_context
from apps.tenant_apps.party.access import PARTY_ACTION_PERMISSIONS
from apps.tenant_apps.party.models import Party, PartyAddress, PartyContactMethod
from apps.tenant_apps.party.services.action_access import require_party_service_permission
from apps.tenant_apps.party.services.contact_details import ensure_party_display_defaults


def _plan(workspace_id):
    parties = list(Party.objects.filter(workspace_id=workspace_id).order_by("pk").values("id", "primary_phone"))
    addresses = list(PartyAddress.objects.filter(workspace_id=workspace_id).order_by("pk").values(
        "id", "party_id", "address_type", "is_default", "line1", "line2", "area", "city", "postal_code"))
    phones = list(PartyContactMethod.objects.filter(workspace_id=workspace_id,
        contact_type__in=("PHONE", "MOBILE", "WHATSAPP")).order_by("pk").values(
            "id", "party_id", "contact_type", "value", "is_primary"))
    digest = hashlib.sha256(json.dumps([workspace_id, parties, addresses, phones], sort_keys=True).encode()).hexdigest()
    by_address, by_phone = defaultdict(list), defaultdict(list)
    for row in addresses:
        by_address[row["party_id"]].append(row)
    for row in phones:
        if row["value"].strip():
            by_phone[row["party_id"]].append(row)
    counts, candidates = Counter(), []
    for party in parties:
        addr, tel = by_address[party["id"]], by_phone[party["id"]]
        missing_address = bool(addr) and not any(row["is_default"] for row in addr)
        missing_phone = bool(tel) and not any(row["is_primary"] for row in tel)
        missing_summary = bool(tel) and not party["primary_phone"].strip()
        counts["address_default_missing"] += missing_address
        counts["phone_primary_missing"] += missing_phone
        counts["phone_summary_missing"] += missing_summary
        counts["no_saved_address"] += not addr
        counts["no_saved_phone"] += not tel and not party["primary_phone"].strip()
        if missing_address or missing_phone or missing_summary:
            candidates.append(party["id"])
    return {"workspace_id": workspace_id, "digest": digest, "parties": len(parties),
            "candidates": candidates, "counts": dict(counts)}


class Command(BaseCommand):
    help = "Preview or fill missing address/phone selections, preserving existing choices and values."

    def add_arguments(self, parser):
        parser.add_argument("--workspace-id", type=int, required=True)
        parser.add_argument("--actor-id", type=int, required=True)
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--expected-digest")

    def handle(self, *args, **options):
        workspace_id = options["workspace_id"]
        try:
            actor = get_user_model().objects.get(pk=options["actor_id"])
        except get_user_model().DoesNotExist as exc:
            raise CommandError("Repair actor not found.") from exc
        with workspace_context(workspace_id):
            require_party_service_permission(workspace_id, actor, *PARTY_ACTION_PERMISSIONS["edit"])
            plan = _plan(workspace_id)
        report = {key: value for key, value in plan.items() if key != "candidates"}
        report.update(candidate_count=len(plan["candidates"]), applied=False)
        if options["apply"]:
            if options["expected_digest"] != plan["digest"]:
                raise CommandError("Source choices changed or no preview digest supplied. Preview again before applying.")
            changes = Counter(address_defaults=0, primary_contacts=0, phone_summaries=0)
            completed = 0
            try:
                for party_id in plan["candidates"]:
                    # A short independent transaction per customer. The service
                    # rereads choices under its lock, preserving concurrent edits.
                    with workspace_context(workspace_id):
                        changed = ensure_party_display_defaults(workspace_id=workspace_id,
                            party_id=party_id, actor=actor)
                    changes["address_defaults"] += changed["address_id"] is not None
                    changes["primary_contacts"] += changed["contact_id"] is not None
                    changes["phone_summaries"] += changed["phone_summary"]
                    completed += 1
            except Exception as exc:
                raise CommandError(f"Repair stopped after {completed} customers; completed changes are committed. Preview again to resume.") from exc
            with workspace_context(workspace_id):
                after = _plan(workspace_id)
            report.update(applied=True, changes=dict(changes), remaining=after["counts"], after_digest=after["digest"])
        self.stdout.write(json.dumps(report, sort_keys=True))
