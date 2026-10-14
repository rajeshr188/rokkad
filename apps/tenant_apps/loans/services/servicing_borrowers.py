"""Exact Party references for borrower corrections in servicing bundle version 5."""
from copy import deepcopy

from apps.tenant_apps.party.models import Party
from .servicing_bundle_contract import require
from .recorded_history import _digest, _text


def source_parties(loan, namespace):
    from apps.tenant_apps.data_portability.models import PartyIdentity
    identities = {loan.borrower_id}
    for log in loan.change_log.filter(event_kind="BORROWER_CORRECTED"):
        evidence = log.metadata["borrower_correction"]
        identities.update(evidence[key]["id"] for key in ("before", "after"))
    parties = {row.pk: row for row in Party.objects.filter(workspace_id=loan.workspace_id, pk__in=identities)}
    require(set(parties) == identities, "Correction Party identities are missing or foreign.")
    result = {}
    for pk, party in sorted(parties.items()):
        identity, _ = PartyIdentity.objects.get_or_create(workspace_id=loan.workspace_id, party=party)
        result[str(pk)] = dict(source_system="rokkad:"+str(namespace.public_id), id=str(identity.public_id))
    return result


def validate_parties(document):
    loans = {str(row["id"]): row for row in document["tables"]["PawnLoan"]}
    references = document["agreement_parties"]
    require(type(references) is dict and set(references) == set(loans), "Map Party evidence for every loan.")
    logs = document["tables"]["LoanChangeLog"]
    for log in logs:
        require((log['event_kind'] == 'BORROWER_CORRECTED') == ('borrower_correction' in log['metadata']),
            'Borrower correction evidence must belong to its explicit correction event.')
    for key, loan in loans.items():
        entries = references[key]
        require(type(entries) is dict and entries, "Missing agreement Party identities.")
        for pk, reference in entries.items():
            require(type(pk) is str and pk.isascii() and pk.isdigit() and int(pk) > 0 and str(int(pk)) == pk,
                "Invalid source Party row identity.")
            require(type(reference) is dict and set(reference) == {"source_system", "id"}
                and all(type(value) is str and value for value in reference.values()), "Invalid exact Party reference.")
        required = {str(loan["borrower_id"])}
        previous = None
        for log in sorted((row for row in logs if str(row["loan_id"]) == key and row["event_kind"] == "BORROWER_CORRECTED"), key=lambda row: row["id"]):
            evidence = log["metadata"].get("borrower_correction")
            require(type(evidence) is dict and evidence.get("schema") == "recorded-borrower-correction/1", "Unsupported borrower correction evidence.")
            for side in ("before", "after"):
                party = evidence.get(side)
                require(type(party) is dict and set(party) == {"id", "name", "code", "status"}
                    and type(party["id"]) is int and party["id"] > 0
                    and all(type(party[field]) is str for field in ("name", "code", "status")), "Invalid correction Party snapshot.")
                required.add(str(party["id"]))
            require(evidence["before"]["id"] != evidence["after"]["id"]
                and (previous is None or previous == evidence["before"]["id"]), "Broken borrower correction chain.")
            require(log["actor_id"] is not None and log["from_state"] == log["to_state"] == "ACTIVE"
                and log["reason"] == evidence.get("reason") and bool(log["reason"].strip()), "Invalid correction recorder/reason.")
            facts = dict(borrower_id=evidence["after"]["id"], reference=evidence.get("reference"),
                reason=evidence["reason"], request_key=evidence.get("request_key"))
            for field, limit in (('reference',160), ('reason',500), ('request_key',80)):
                require(_text(facts[field], field, limit) == facts[field], 'Correction text must retain its canonical value.')
            fingerprint = evidence.get('source_fingerprint')
            require(type(fingerprint) is str and len(fingerprint) == 64
                and all(c in '0123456789abcdef' for c in fingerprint), 'Invalid correction source fingerprint.')
            require(all(type(facts[field]) is str and facts[field].strip() for field in ("reference", "reason", "request_key"))
                and evidence.get("request_sha256") == _digest(facts), "Correction request evidence differs.")
            previous = evidence["after"]["id"]
        require(previous is None or previous == loan["borrower_id"], "Current borrower does not match its correction chain.")
        require(set(entries) == required and entries[str(loan["borrower_id"])] == document["setup"][key]["borrower"],
            "Correction Party inventory differs from the loan's exact identities.")


def destination_parties(document, loan_id, workspace_id, current_borrower_id):
    from apps.tenant_apps.data_portability.children import parent_for
    result = {}
    for source_id, reference in document["agreement_parties"][loan_id].items():
        parent = parent_for(dict(party_source_system=reference["source_system"], party_external_id=reference["id"]), workspace_id)
        require(parent is not None and Party.objects.filter(workspace_id=workspace_id, pk=parent.party_id).exists(),
            "Import every exact former/current customer before restoring this loan's corrections.")
        result[source_id] = parent.party_id
    require(len(set(result.values())) == len(result), "Distinct correction customers cannot collapse to one destination Party.")
    source = next(row for row in document["tables"]["PawnLoan"] if str(row["id"]) == loan_id)
    require(result[str(source["borrower_id"])] == current_borrower_id, "Current borrower mapping differs from exact Party evidence.")
    return result


def remap_correction(evidence, party_refs, source_workspace_id):
    result = deepcopy(evidence)
    result["portable_source"] = dict(workspace_id=source_workspace_id,
        before_id=evidence["before"]["id"], after_id=evidence["after"]["id"], request_sha256=evidence["request_sha256"])
    for side in ("before", "after"):
        require(str(evidence[side]["id"]) in party_refs, "Unmapped borrower correction Party.")
        result[side]["id"] = party_refs[str(evidence[side]["id"])]
    result["request_sha256"] = _digest(dict(borrower_id=result["after"]["id"],
        **{key: result[key] for key in ("reference", "reason", "request_key")}))
    return result
