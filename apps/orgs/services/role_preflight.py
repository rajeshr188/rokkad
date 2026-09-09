"""Read-only inventory of the legacy role model for AP-06 migration planning."""
import hashlib
import json
from collections import Counter, defaultdict

from apps.orgs.access import normalize_action
from apps.orgs.models import Company, CompanyInvitation, Membership, Role
from apps.orgs.permissions import get_all_permission_codenames, get_permissions_for_role


SENSITIVE_ACTIONS = frozenset({
    "workspace.settings.manage", "workspace.edit", "workspace.archive", "workspace.delete",
    "workspace.transfer", "billing.manage", "team.member.remove", "team.member.role.change",
    "team.invite.elevated", "admin.access",
})
RETIRED_PREFIXES = ("girvi_", "dea_", "accounting_", "girvi.", "dea.", "accounting.")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True).encode()).hexdigest()


def build_role_preflight():
    """Select only control-plane IDs, role labels and grants; never mutate or send."""
    known_actions = {normalize_action(code) for code in get_all_permission_codenames()}
    roles = []
    for role in Role.objects.order_by("pk").prefetch_related("permissions"):
        stored = sorted({permission.codename for permission in role.permissions.all()})
        defaults = sorted(set(get_permissions_for_role(role.name)))
        codes = sorted(set(stored) | set(defaults))
        actions = sorted({normalize_action(code) for code in codes})
        row = {"role_id": role.pk, "name": role.name,
               "normalized_name": role.name.strip().casefold(),
               "stored_codes": stored, "default_codes": defaults, "effective_actions": actions,
               "unknown_codes": [code for code in codes if normalize_action(code) not in known_actions],
               "retired_codes": [code for code in codes if code.startswith(RETIRED_PREFIXES)],
               "sensitive_actions": sorted(set(actions) & SENSITIVE_ACTIONS)}
        row["grant_fingerprint"] = fingerprint(actions)
        row["source_fingerprint"] = fingerprint(row)
        roles.append(row)
    role_map = {row["role_id"]: row for row in roles}
    memberships = list(Membership.objects.order_by("pk").values("id", "company_id", "user_id", "role_id"))
    invitations = list(CompanyInvitation.objects.order_by("pk").values(
        "id", "company_id", "role_id", "status", "accepted", "inviter_id"))
    workspaces = list(Company.all_objects.order_by("pk").values("id", "owner_id", "lifecycle_state"))
    members_by_workspace, invites_by_workspace = defaultdict(list), defaultdict(list)
    referenced = set()
    for row in memberships:
        members_by_workspace[row["company_id"]].append(row)
        referenced.add(row["role_id"])
    for row in invitations:
        invites_by_workspace[row["company_id"]].append(row)
        referenced.add(row["role_id"])
    findings, copies = [], []
    local_roles = []
    for workspace in workspaces:
        wid = workspace["id"]
        from apps.orgs.models import WorkspaceRole
        from apps.orgs.services.workspace_roles import stored_role_codes
        from apps.tenancy.context import workspace_context
        with workspace_context(wid):
            for local in WorkspaceRole.objects.filter(workspace_id=wid).order_by("role_id"):
                actions = sorted({normalize_action(c) for c in stored_role_codes(wid, local.role_id)})
                local_roles.append({"workspace_id": wid, "role_id": local.role_id,
                    "revision": local.revision, "effective_actions": actions,
                    "grant_fingerprint": fingerprint(actions)})
        members = members_by_workspace[wid]
        invites = invites_by_workspace[wid]
        role_ids = sorted({row["role_id"] for row in members + invites})
        names = defaultdict(list)
        for rid in role_ids:
            role = role_map.get(rid)
            if role is None:
                findings.append({"kind": "missing_role", "workspace_id": wid, "role_id": rid})
                continue
            names[role["normalized_name"]].append(rid)
            copies.append({"workspace_id": wid, "legacy_role_id": rid,
                           "membership_ids": [m["id"] for m in members if m["role_id"] == rid],
                           "invitation_ids": [i["id"] for i in invites if i["role_id"] == rid],
                           "grant_fingerprint": role["grant_fingerprint"]})
        for name, ids in sorted(names.items()):
            if len(ids) > 1:
                findings.append({"kind": "normalized_name_collision", "workspace_id": wid, "role_ids": ids})
        owner_members = [m for m in members if m["user_id"] == workspace["owner_id"]]
        named_owners = [m for m in members if role_map.get(m["role_id"], {}).get("normalized_name") == "owner"]
        if len(owner_members) != 1 or named_owners != owner_members:
            findings.append({"kind": "owner_mirror_mismatch", "workspace_id": wid})
        inviters = [m["id"] for m in members if m["user_id"] != workspace["owner_id"]
                    and "team.invite" in role_map.get(m["role_id"], {}).get("effective_actions", [])]
        # Current choices are global and exclude only the Owner/Admin names.
        dangerous_roles = [r["role_id"] for r in roles if r["normalized_name"] not in {"owner", "admin"}
                           and (r["sensitive_actions"] or r["unknown_codes"])]
        if inviters and dangerous_roles:
            findings.append({"kind": "custom_role_delegation_review", "workspace_id": wid,
                             "inviter_membership_ids": inviters, "available_role_ids": dangerous_roles})
    for role in roles:
        for key in ("unknown_codes", "retired_codes"):
            if role[key]:
                findings.append({"kind": key, "role_id": role["role_id"], "codes": role[key]})
        if role["sensitive_actions"] and role["normalized_name"] not in {"owner", "admin"}:
            findings.append({"kind": "sensitive_non_admin_role", "role_id": role["role_id"],
                             "actions": role["sensitive_actions"]})
    report = {"schema_version": 2, "classification": "stored_grants_and_legacy_templates",
              "roles": roles, "local_roles": local_roles, "workspaces": workspaces, "memberships": memberships,
              "invitations": invitations, "proposed_role_copies": copies,
              "unreferenced_role_ids": sorted(set(role_map) - referenced), "findings": findings,
              "summary": {"workspace_count": len(workspaces), "role_count": len(roles),
                          "local_role_count": len(local_roles),
                          "membership_count": len(memberships), "invitation_count": len(invitations),
                          "proposed_copy_count": len(copies),
                          "finding_counts": dict(sorted(Counter(f["kind"] for f in findings).items()))}}
    report["inventory_fingerprint"] = fingerprint(report)
    return report
