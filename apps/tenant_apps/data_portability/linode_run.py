"""Snapshot-bound operator package for replaying the accepted Linode conversion.

This composes existing import services. It does not restore SQL, synchronize a live
source, approve changed source facts, or replace ordinary authorization/RLS.
"""
from collections import Counter
from copy import deepcopy
from datetime import date
import hashlib
from itertools import batched
import json
from pathlib import Path
import re
from uuid import UUID, uuid5

from django.db import connection, transaction

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans import models as loans
from apps.tenant_apps.loans.services.archive import accept_evidence
from apps.tenant_apps.loans.services.archive_contract import review_document
from apps.tenant_apps.loans.services.history_contract import digest
from apps.tenant_apps.loans.services.history_setup import require_history_setup_access
from apps.tenant_apps.loans.services.license_series import (
    create_legacy_license_reference, create_configured_series, reserve_sequence_through,
)
from apps.tenant_apps.loans.services.product_catalog import (
    create_product_version_draft, activate_product_version, retire_product_version,
)
from apps.tenant_apps.party.models import Party, PartyAddress, PartyContactMethod
from . import services, contracts, child_contracts, legacy_opening
from .access import require_access
from .address_reviews import review_distinct_addresses
from .name_reviews import review_distinct_names
from .legacy_dump import inspect_archive
from .legacy_party_preparation import build_party_preparation
from .legacy_preview import encode
from .models import ImportBatch, SourceIdentity, ChildSourceIdentity, LoanHistoryBatch
from .parsers import PortabilityError, MAX_BYTES

PROFILE = "linode-reviewed-run/1"
SCHEMAS = {"jcl": "linode-jcl/1", "jsk": "linode-jsk/1", "lakshmipawnbroker": "linode-lakshmi/1"}
PARTY_PROFILES = (contracts.PROFILE, child_contracts.CONTACT, child_contracts.ADDRESS)


def require(condition, message):
    if not condition:
        raise PortabilityError(message)


def sha_file(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(encode(value) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_rows(path):
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            require(len(line) <= 2 * 1024 * 1024, "An operator package row exceeds its size limit.")
            yield json.loads(line)


def write_rows(path, rows):
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(encode(row) + "\n")
            count += 1
    return count


def runtime_guard(expected_database):
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(),rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
        name, superuser, bypass = cursor.fetchone()
    require(name == expected_database and not superuser and not bypass,
            "Select the exact expected database under its restricted runtime role.")


def validate_workspace_map(mapping):
    require(type(mapping) is dict and set(mapping) == set(SCHEMAS), "Map exactly the three Linode schemas.")
    require(all(type(wid) is int and wid > 0 for wid in mapping.values()) and len(set(mapping.values())) == 3,
            "Each source schema requires a distinct positive destination Workspace ID.")


def source_index(extracted):
    return {f"{table}:{pk}": digest(row) for table, rows in extracted["tables"].items() for pk, row in rows.items()}


def compare_index(old, new):
    return {"added": sorted(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys()),
            "changed": sorted(key for key in old.keys() & new.keys() if old[key] != new[key])}


def load_package(directory, expected_sha256):
    root = Path(directory).resolve()
    manifest_path = root / "manifest.json"
    require(manifest_path.stat().st_size <= MAX_BYTES, "Package manifest is too large.")
    require(sha_file(manifest_path) == expected_sha256, "The reviewed package checksum changed.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest.get("profile") == PROFILE and set(manifest.get("workspaces", {})) == set(SCHEMAS),
            "Unsupported Linode operator package.")
    require(1 <= len(manifest["files"]) <= 1000, "Invalid package file count.")
    paths = set()
    for entry in manifest["files"]:
        relative = entry["path"]
        require(isinstance(relative, str) and re.fullmatch(r"[a-z0-9_/-]+\.(json|jsonl)", relative), "Invalid package path.")
        path = (root / relative).resolve()
        require(root in path.parents and relative not in paths, "Package paths must be unique and contained.")
        require(path.stat().st_size <= 256 * 1024 * 1024 and sha_file(path) == entry["sha256"],
                "A reviewed package file changed or exceeds its limit.")
        paths.add(relative)
    # Every consumed file is covered by the reviewed manifest, including nested batch paths.
    for schema, workspace in manifest["workspaces"].items():
        required = {f"{schema}/{name}" for name in ("source-index.json", "setup.json", "openings.jsonl", "closed.jsonl", "excluded.jsonl")}
        required.update(entry["path"] for entry in workspace["party_batches"])
        require(required <= paths, "Package contains an unhashed input reference.")
    return root, manifest


def build_package(*, directory, archive_path, workspaces, actor, expected_database,
                  namespace, approval_reference, exclusions, pg_restore="pg_restore"):
    """Capture immutable accepted inputs; refuse any financial servicing since import."""
    runtime_guard(expected_database)
    validate_workspace_map(workspaces)
    require(approval_reference.strip() and len(approval_reference) <= 255, "Record the owner's bounded review reference.")
    UUID(namespace)
    for wid in workspaces.values():
        with workspace_context(wid):
            require_history_setup_access(wid, actor)
            require_access(wid, actor, "export")
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=False)
    (root / ".gitignore").write_text("*\n")
    manifest = {"profile": PROFILE, "namespace": namespace, "archive_sha256": sha_file(archive_path),
                "approval_reference": approval_reference, "source_database": expected_database,
                "media": {"source": "LINODE_SERVER_FILESYSTEM", "root": None, "copied": False},
                "production_ready": False, "workspaces": {}}
    for schema, wid in workspaces.items():
        out = root / schema
        out.mkdir()
        extracted = inspect_archive(archive_path, schema=schema, pg_restore=pg_restore)
        require(extracted["archive_sha256"] == manifest["archive_sha256"], "Source archive changed during preparation.")
        save(out / "source-index.json", source_index(extracted))
        party = build_party_preparation(extracted, schema=schema, source_namespace=namespace, source_profile=SCHEMAS[schema])
        expected = {profile: {r["id"]: r for r in records} for profile, records in party["records"].items()}
        seen = {profile: set() for profile in PARTY_PROFILES}
        batches = []
        with workspace_context(wid):
            require(not ImportBatch.objects.exclude(state__in=["COMPLETED", "CANCELLED"]).exists(), "Finish Party staging before packaging.")
            for profile in PARTY_PROFILES:
                for batch in ImportBatch.objects.filter(state="COMPLETED", contract_version=profile).order_by("pk"):
                    require(batch.source_system == party["source_system"] and batch.source_type == "jsonl", "Unexpected Party source in reviewed Workspace.")
                    records = [r.raw for r in batch.rows.order_by("source_row")]
                    for record in records:
                        external = record["id"]
                        require(external not in seen[profile] and record == expected[profile].get(external), "Accepted Party input differs from the source preparation.")
                        seen[profile].add(external)
                    name = f"party-{len(batches)+1:04d}.jsonl"
                    write_rows(out / name, records)
                    require((out / name).stat().st_size <= MAX_BYTES, "Party batch exceeds the normal staging size limit.")
                    batches.append({"path": f"{schema}/{name}", "profile": profile, "count": len(records),
                        "name_reviews": {k:v["reason"] for k,v in batch.mapping.get("name_reviews", {}).items()},
                        "address_reviews": {k:v["reason"] for k,v in batch.mapping.get("address_reviews", {}).items()}})
            require(all(seen[p] == set(expected[p]) for p in PARTY_PROFILES), "Party package does not cover the complete source.")
            origins = list(loans.HistoricalLoanImport.objects.order_by("pk"))
            require(len(origins) == loans.PawnLoan.objects.count() == loans.PawnLoanEvent.objects.count(),
                    "Only the accepted, unserviced opening snapshot can be packaged.")
            frozen = {b.source_sha256:b for b in LoanHistoryBatch.objects.filter(state="COMPLETED", profile=legacy_opening.PROFILE)}
            opening_rows = []
            for origin in origins:
                require(origin.source_sha256 == digest(origin.document), "Accepted opening fingerprint changed.")
                batch = frozen[origin.source_sha256]
                require(batch.document["opening"] == origin.document, "Signed staging and accepted opening disagree.")
                source = origin.document["review"]["source"]
                require(source["archive_sha256"] == manifest["archive_sha256"] and source["schema"] == schema
                        and source["namespace"] == namespace, "Unexpected source opening.")
                opening_rows.append(batch.document)
            opened = {r["opening"]["review"]["source"]["loan_id"] for r in opening_rows}
            require(len(opened) == len(opening_rows), "Duplicate source openings.")
            write_rows(out / "openings.jsonl", opening_rows)
            closed = set()
            def closed_rows():
                for evidence in loans.HistoricalLoanEvidence.objects.order_by("pk").iterator(chunk_size=500):
                    document = evidence.document
                    require(evidence.source_id not in closed and document["source"]["snapshot_reference"] == "sha256:"+manifest["archive_sha256"], "Unexpected closed-history source.")
                    require(evidence.source_sha256 == digest(document) and evidence.review == review_document(document), "Closed evidence fingerprint changed.")
                    closed.add(evidence.source_id)
                    yield document
            closed_count = write_rows(out / "closed.jsonl", closed_rows())
        omitted = exclusions.get(schema, [])
        excluded = {r["source_id"] for r in omitted}
        require(len(excluded) == len(omitted) and all(r["archive_sha256"] == manifest["archive_sha256"] for r in omitted), "Excluded source decisions do not match this archive.")
        write_rows(out / "excluded.jsonl", omitted)
        all_loans = {"girvi_loan:"+pk for pk in extracted["tables"]["girvi_loan"]}
        require(not (opened & closed or opened & excluded or closed & excluded) and opened | closed | excluded == all_loans,
                "Every source loan must occur exactly once in openings, closed evidence or reviewed exclusions.")
        table = extracted["tables"]
        series = []
        for sid, row in table["girvi_series"].items():
            prefix = row["name"] or f"LEGACY{sid}-"
            suffixes = [int(match[1]) for loan in table["girvi_loan"].values()
                        if (match := re.fullmatch(re.escape(prefix)+r"([0-9]+)", loan["loan_id"]))]
            series.append({"id":sid, "license_id":row["license_id"], "prefix":prefix, "last_used":max(suffixes, default=0)})
        setup = {"licenses":[{"id":pk,"label":row["name"]} for pk,row in table["girvi_license"].items()],
                 "series":series, "max_tenure":max([12]+[r["opening"]["setup"]["tenure_months"] for r in opening_rows])}
        save(out / "setup.json", setup)
        manifest["workspaces"][schema] = {"source_system":party["source_system"], "party_batches":batches,
            "party_counts":party["counts"], "preparation_review":party["review"], "openings":len(opened),
            "closed":closed_count, "excluded":len(excluded), "source_loans":len(all_loans)}
    manifest["files"] = [{"path":p.relative_to(root).as_posix(), "sha256":sha_file(p)}
                         for p in sorted(root.rglob("*")) if p.is_file() and p.name != ".gitignore"]
    save(root / "manifest.json", manifest)
    return sha_file(root / "manifest.json"), manifest


def check_source(*, directory, expected_sha256, archive_path, pg_restore="pg_restore"):
    """Read-only comparison: changed snapshots require new preparation and approval."""
    root, manifest = load_package(directory, expected_sha256)
    report = {"expected_archive_sha256":manifest["archive_sha256"], "actual_archive_sha256":sha_file(archive_path), "schemas":{}}
    for schema in SCHEMAS:
        extracted = inspect_archive(archive_path, schema=schema, pg_restore=pg_restore)
        require(extracted["archive_sha256"] == report["actual_archive_sha256"], "Source changed during inspection.")
        report["schemas"][schema] = compare_index(json.loads((root/schema/"source-index.json").read_text()), source_index(extracted))
    report["exact_snapshot"] = report["actual_archive_sha256"] == report["expected_archive_sha256"]
    report["requires_new_preparation"] = not report["exact_snapshot"]
    return report


def rebind_opening(row, *, workspace_id, borrower_id, setup_map):
    inputs = deepcopy(row["opening"])
    evidence = row["source_evidence"]
    source_id = inputs["review"]["source"]["loan_id"]
    source_loan = next(r for r in evidence["records"] if r["source"]["external_id"] == source_id)
    mapped = setup_map["series"][source_loan["facts"]["series_id"]]
    inputs["review"]["mapping"].update(workspace_id=workspace_id, borrower_id=borrower_id,
        licence_revision_id=mapped["revision_id"], series_id=mapped["series_id"], product_version_id=setup_map["product_version_id"])
    return inputs


def _setup(*, workspace, actor, config, package_sha256):
    """One atomic setup checkpoint in the existing audit log, tied to this package."""
    with transaction.atomic():
        Company.all_objects.select_for_update().get(pk=workspace.pk)
        previous = AuditLog.objects.filter(company=workspace, action="DATA_IMPORT", data__linode_run=package_sha256, data__phase="setup").first()
        if previous:
            require(previous.data["config_sha256"] == digest(config), "Setup input changed.")
            return previous.data["mapping"]
        require(not any(model.objects.exists() for model in (Party,loans.PawnLoan,loans.HistoricalLoanEvidence,loans.LoanLicense,loans.LoanProduct,ImportBatch)),
                "A new package requires a clean Workspace; existing rehearsal or business data cannot be merged.")
        require(not AuditLog.objects.filter(company=workspace, data__phase="setup", data__linode_run__isnull=False).exists(), "Workspace is bound to another package.")
        reference = "Reviewed Linode package sha256:"+package_sha256
        licences = {r["id"]:create_legacy_license_reference(workspace=workspace, name="Linode licence "+r["id"],
            source_label=r["label"], evidence_reference=reference, actor=actor) for r in config["licenses"]}
        mapping = {"series":{}}
        for row in config["series"]:
            licence = licences[row["license_id"]]
            series = create_configured_series(license=licence, name="Legacy "+row["prefix"], code="LINODE-"+row["id"],
                is_active=True, pawn_loan_prefix=row["prefix"], release_prefix="MIG-"+row["id"]+"-R", number_width=5,
                maximum_number=max(10000,row["last_used"]), actor=actor)
            reserve_sequence_through(series=series, document_kind="PAWN_LOAN", last_used_number=row["last_used"], evidence_reference=reference, actor=actor)
            mapping["series"][row["id"]] = {"series_id":series.pk,"revision_id":licence.revisions.get(kind="LEGACY_REFERENCE").pk}
        product = loans.LoanProduct.objects.create(workspace=workspace,code="LINODE-LEGACY",name="Legacy opening servicing",created_by=actor,updated_by=actor)
        version = create_product_version_draft(product.pk, actor=actor, available_from=None, available_until=None,
            repayment_structure="FLEXIBLE_PARTIAL_PAYMENT", amortisation_method="NONE", payment_frequency="FLEXIBLE",
            minimum_tenor_months=1, maximum_tenor_months=config["max_tenure"], operational_grace_days=3,
            extra_payment_rule="REDUCE_PRINCIPAL", calculation_contract_version="original-anniversary-upfront-inclusive/2")
        activate_product_version(version.pk,actor=actor)
        retire_product_version(version.pk,actor=actor)
        mapping["product_version_id"] = version.pk
        AuditLog.log("DATA_IMPORT",company=workspace,user=actor,description="Bound clean Workspace to reviewed Linode package.",
            data={"linode_run":package_sha256,"phase":"setup","config_sha256":digest(config),"mapping":mapping})
        return mapping


def _party_batch(*, root, entry, system, workspace_id, actor):
    content = (root/entry["path"]).read_bytes()
    args = {"workspace_id":workspace_id,"actor":actor}
    batch = ImportBatch.objects.filter(source_system=system,source_sha256=hashlib.sha256(content).hexdigest(),
                                      contract_version=entry["profile"]).exclude(state="CANCELLED").order_by("pk").first()
    if batch is None:
        batch = services.stage_import(**args,content=content,filename=Path(entry["path"]).name,source_system=system,profile=entry["profile"])
    if batch.state != "COMPLETED":
        batch = services.validate_import(**args,batch_id=batch.public_id,mapping={})
        for key, reviewer in (("name_reviews",review_distinct_names),("address_reviews",review_distinct_addresses)):
            reasons = entry[key]
            for reason in sorted(set(reasons.values())):
                batch = reviewer(**args,batch_id=batch.public_id,external_ids=[k for k,v in reasons.items() if v==reason],reason=reason,approval_digest=batch.approval_digest)
        require(batch.state == "READY", "Party batch has unresolved conflicts; inspect its ordinary review page.")
    services.commit_import(**args,batch_id=batch.public_id,approval_digest=batch.approval_digest,acknowledge_warnings=True)


def replay_package(*, directory, expected_sha256, archive_path, workspaces, actor,
                   expected_database, output_dir, confirmed=False, pg_restore="pg_restore", progress=print):
    runtime_guard(expected_database)
    validate_workspace_map(workspaces)
    root, manifest = load_package(directory, expected_sha256)
    require(confirmed, "Explicitly confirm the reviewed package before admission.")
    require(expected_database != manifest["source_database"], "The accepted rehearsal database is not a replay destination.")
    for wid in workspaces.values():
        with workspace_context(wid):
            require_history_setup_access(wid,actor)
            require_access(wid,actor,"child_commit")
    require(sha_file(archive_path) == manifest["archive_sha256"], "This snapshot changed. Run check-source and prepare a new reviewed package; never reuse old financial decisions automatically.")
    out = Path(output_dir)
    out.mkdir(parents=True,exist_ok=True)
    (out/".gitignore").write_text("*\n")
    binding = {"package_sha256":expected_sha256,"database":expected_database,"workspaces":workspaces}
    if (out/"binding.json").exists():
        require(json.loads((out/"binding.json").read_text()) == binding,"Output directory belongs to another run.")
    else:
        save(out/"binding.json",binding)
    for schema,wid in workspaces.items():
        meta = manifest["workspaces"][schema]
        with workspace_context(wid):
            workspace = require_history_setup_access(wid,actor)
            mapped = _setup(workspace=workspace,actor=actor,config=json.loads((root/schema/"setup.json").read_text()),package_sha256=expected_sha256)
        for entry in meta["party_batches"]:
            with workspace_context(wid):
                _party_batch(root=root,entry=entry,system=meta["source_system"],workspace_id=wid,actor=actor)
            progress(f"{schema}: Party batch {entry['path']} committed/reused",flush=True)
        prepared = list(read_rows(root/schema/"openings.jsonl"))
        for profile in sorted({r["source_evidence"]["source_profile"] for r in prepared}):
            selected = [r for r in prepared if r["source_evidence"]["source_profile"] == profile]
            for offset in range(0,len(selected),20):
                with workspace_context(wid):
                    inputs = []
                    decisions = {}
                    expected_evidence = {}
                    for row in selected[offset:offset+20]:
                        review = row["opening"]["review"]
                        external = str(uuid5(uuid5(UUID(manifest["namespace"]),schema),review["mapping"]["borrower_external_id"]))
                        borrower = SourceIdentity.objects.select_related("identity").get(source_system=meta["source_system"],external_id=external).identity.party_id
                        document = rebind_opening(row,workspace_id=wid,borrower_id=borrower,setup_map=mapped)
                        expected_evidence[digest(document)] = row["source_evidence"]
                        existing = loans.HistoricalLoanImport.objects.filter(source_sha256=digest(document)).first()
                        if existing:
                            require(existing.document == document,"Accepted opening changed.")
                            continue
                        inputs.append({"review":document["review"],"setup":document["setup"]})
                        decision = row["source_evidence"].get("payment_exclusion")
                        if decision:
                            decisions[review["source"]["loan_id"]] = {k:v for k,v in decision.items() if k != "rule"}
                    if inputs:
                        # A crashed unfinished chunk is reused only if its exact document matches.
                        pending = []
                        batches = []
                        for values in inputs:
                            fingerprint = digest({"profile":"loan-opening-commit/1",**values})
                            staged = LoanHistoryBatch.objects.filter(profile=legacy_opening.PROFILE,source_sha256=fingerprint,state__in=["STAGED","READY"]).first()
                            if staged:batches.append(staged)
                            else:pending.append(values)
                        if pending:
                            keys = {i["review"]["source"]["loan_id"] for i in pending}
                            batches += legacy_opening.stage_many(workspace_id=wid,actor=actor,archive_path=archive_path,
                                openings=pending,source_profile=profile,payment_reviews={k:v for k,v in decisions.items() if k in keys},pg_restore=pg_restore)
                        for batch in batches:
                            require(batch.document["source_evidence"] == expected_evidence[batch.source_sha256],
                                    "Staged source decisions differ from the approved package.")
                            args = {"workspace_id":wid,"actor":actor,"batch_id":batch.public_id}
                            approval = legacy_opening.preview(**args)
                            origin = legacy_opening.commit(**args,approval=approval,confirmed=True)
                            require(legacy_opening.commit(**args,approval=approval,confirmed=True).pk == origin.pk,"Opening retry changed result.")
                progress(f"{schema}: {profile} openings through {min(offset+20,len(selected))}/{len(selected)}",flush=True)
        accepted = 0
        for chunk in batched(read_rows(root/schema/"closed.jsonl"), 100):
            with workspace_context(wid):
                for document in chunk:
                    accept_evidence(workspace_id=wid,actor=actor,document=document,expected_sha256=digest(document),confirmed=True)
            accepted += len(chunk)
            if accepted % 1000 == 0:progress(f"{schema}: closed history {accepted}/{meta['closed']}",flush=True)
        save(out/(schema+"-admitted.json"),{"openings":meta["openings"],"closed":meta["closed"],"excluded":meta["excluded"]})
    # Admission checkpoint is deliberately not labelled reconciled/production-ready.
    save(out/"admission.json",{**binding,"state":"ADMITTED_RECONCILIATION_REQUIRED","media_copied":False})
    return manifest


def verify_package(*, directory, expected_sha256, workspaces, actor, expected_database, output_dir, progress=print):
    """Compare every admitted input and financial position; never label counts alone complete."""
    from decimal import Decimal, ROUND_HALF_EVEN
    from apps.tenant_apps.loans.selectors.balances import calculate_pawn_loan_balance
    from apps.tenant_apps.loans.services.opening_continuation import preview_opening_collection, opening_interest_breakdown
    runtime_guard(expected_database)
    validate_workspace_map(workspaces)
    root, manifest = load_package(directory, expected_sha256)
    out = Path(output_dir)
    binding = {"package_sha256":expected_sha256,"database":expected_database,"workspaces":workspaces}
    require((out/"binding.json").exists() and json.loads((out/"binding.json").read_text()) == binding,
            "Verify using the matching admission output directory.")
    report = {"package_sha256":expected_sha256,"database":expected_database,"workspaces":{},"media_copied":False,"production_ready":False}
    rls_models = (Party,PartyContactMethod,PartyAddress,loans.PawnLoan,loans.PawnLoanEvent,loans.HistoricalLoanEvidence)
    for schema,wid in workspaces.items():
        meta = manifest["workspaces"][schema]
        with workspace_context(wid):
            workspace = require_history_setup_access(wid,actor)
            checkpoint = AuditLog.objects.get(company=workspace,action="DATA_IMPORT",data__linode_run=expected_sha256,data__phase="setup")
            require(checkpoint.data["config_sha256"] == digest(json.loads((root/schema/"setup.json").read_text())),
                    "Setup checkpoint differs from the reviewed package.")
            mapped = checkpoint.data["mapping"]
            require(not ImportBatch.objects.exclude(state__in=["COMPLETED","CANCELLED"]).exists()
                    and not LoanHistoryBatch.objects.exclude(state__in=["COMPLETED","CANCELLED"]).exists(), "Unfinished import batches remain.")
            masters = {s.external_id:s for s in SourceIdentity.objects.filter(source_system=meta["source_system"]).select_related("identity__party")}
            kids = {(s.profile,s.external_id):s for s in ChildSourceIdentity.objects.filter(source_system=meta["source_system"]).select_related("identity__contact","identity__address")}
            contacts = list(PartyContactMethod.objects.all())
            counts = Counter()
            for entry in meta["party_batches"]:
                profile = entry["profile"]
                for raw in read_rows(root/entry["path"]):
                    canonical,issues = (contracts.validate_record(raw,canonical_source=True) if profile == contracts.PROFILE
                        else child_contracts.validate_child(raw,canonical_source=True,profile=profile))
                    require(not any(i["severity"]=="ERROR" for i in issues),"Invalid packaged Party row.")
                    if profile == contracts.PROFILE:
                        source = masters[raw["id"]]
                        current = contracts.semantic(source.identity.party)
                        require(all(current[k] == canonical[k] for k in contracts.FIELDS if k not in {"primary_phone","primary_email"}),"Party fields differ from the reviewed source.")
                        primary = [p.value for p in contacts if p.party_id == source.identity.party_id and p.is_primary]
                        require((current["primary_phone"] or "") == (primary[0] if primary else ""),"Primary contact summary differs.")
                    else:
                        source = kids[profile,raw["id"]]
                        obj = source.identity.contact if profile == child_contracts.CONTACT else source.identity.address
                        require(source.identity.parent_id == masters[raw["party_external_id"]].identity_id,"Child parent identity differs.")
                        require(child_contracts.semantic(profile,obj) == {k:canonical[k] for k in child_contracts.fields(profile)},"Child fields differ.")
                        require(source.local_digest == contracts.digest(child_contracts.local_state(profile,obj)),"Child local fingerprint differs.")
                    require(source.accepted_digest == contracts.source_digest(canonical),"Accepted Party source fingerprint differs.")
                    counts[profile] += 1
            require(dict(counts) == meta["party_counts"],"Party input counts differ.")
            require([Party.objects.count(),len(contacts),PartyAddress.objects.count()] == [counts[p] for p in PARTY_PROFILES],"Unexpected destination Party rows.")
            require(len(masters) == counts[contracts.PROFILE] and len(kids) == counts[child_contracts.CONTACT]+counts[child_contracts.ADDRESS],"Unexpected source aliases.")
            require(len({s.identity_id for s in masters.values()}) == len(masters)
                    and len({s.identity_id for s in kids.values()}) == len(kids),
                    "Reviewed distinct source records were merged.")
            expected = {}
            for row in read_rows(root/schema/"openings.jsonl"):
                original = row["opening"]["review"]
                external = str(uuid5(uuid5(UUID(manifest["namespace"]),schema),original["mapping"]["borrower_external_id"]))
                document = rebind_opening(row,workspace_id=wid,borrower_id=masters[external].identity.party_id,setup_map=mapped)
                expected[document["review"]["source"]["loan_id"]] = (document,row["source_evidence"])
            require(len(expected) == loans.PawnLoan.objects.count() == loans.PawnLoanEvent.objects.count() == loans.HistoricalLoanImport.objects.count(),"Unexpected operational loan/event counts.")
            origins = loans.HistoricalLoanImport.objects.select_related("loan__policy_snapshot").prefetch_related(
                "loan__loan_events","loan__collateral_items","loan__repayment_schedules__obligations")
            batches = {b.source_sha256:b for b in LoanHistoryBatch.objects.filter(profile=legacy_opening.PROFILE,state="COMPLETED")}
            principal = Decimal(0)
            interest = Decimal(0)
            for origin in origins.iterator(chunk_size=100):
                key = origin.document["review"]["source"]["loan_id"]
                document,evidence = expected[key]
                require(origin.document == document and origin.source_sha256 == digest(document),"Opening input fingerprint differs.")
                require(batches[origin.source_sha256].document == {"opening":document,"source_evidence":evidence},"Signed opening source evidence differs.")
                review = document["review"]
                loan = origin.loan
                require(loan.state == "ACTIVE" and loan.loan_number == review["source"]["number"] and loan.borrower_id == review["mapping"]["borrower_id"],"Loan identity/state differs.")
                events = tuple(loan.loan_events.all())
                items = {i.pk:i for i in loan.collateral_items.all()}
                require(len(events)==1 and events[0].event_kind=="MIGRATION_OPENING" and str(events[0].effective_date)==review["cutover"]["date"],"Opening event differs.")
                require(len(items)==len(review["collateral"]),"Collateral count differs.")
                for row in review["collateral"]:
                    item = items[origin.references["items"][row["id"]]]
                    require(item.description==row["description"] and item.metal==row["metal"] and item.custody_state=="IN_VAULT"
                        and item.gross_weight is None and item.net_weight==Decimal(row["net_weight"])
                        and item.purity_percentage==Decimal(row["purity"]) and item.allocated_principal==Decimal(row["remaining_principal"])
                        and item.monthly_interest_rate==Decimal(row["monthly_rate"]),"Collateral economics or custody differs.")
                cutover = date.fromisoformat(review["cutover"]["date"])
                balance = calculate_pawn_loan_balance(loan,events=events,collateral_items=tuple(items.values()),policy_snapshot=loan.policy_snapshot,as_of_date=cutover,pending_delivery_blocks=False)
                require(balance.principal_outstanding==Decimal(review["balances"]["principal"])
                    and balance.interest_outstanding==Decimal(review["balances"]["interest"])
                    and balance.fees_outstanding==Decimal(review["balances"]["fees"]),"Opening balance differs.")
                continuation = preview_opening_collection(loan,events=events,as_of_date=cutover)
                boundary = preview_opening_collection(loan,events=events,as_of_date=continuation.next_increase_on)
                breakdown = opening_interest_breakdown(review,as_of_date=continuation.next_increase_on)
                require(continuation.additional_interest==0 and breakdown["charge_months"]==review["continuation"]["additional_months"]+1
                    and boundary.baseline_as_of==(continuation.monthly_interest_unrounded*breakdown["charge_months"]).quantize(Decimal("1"),rounding=ROUND_HALF_EVEN),"Next monthly interest boundary differs.")
                schedules = list(loan.repayment_schedules.all())
                require(len(schedules)==1,"Unexpected schedules.")
                actual = sorted((str(o.due_date),o.principal_due,o.interest_due) for o in schedules[0].obligations.all())
                wanted = sorted((o["due"],Decimal(o["principal"]),Decimal(o["interest"])) for o in review["obligations"])
                require(actual==wanted,"Remaining obligations differ.")
                principal += balance.principal_outstanding
                interest += balance.interest_outstanding
            require(not loans.PawnLoanRelease.objects.exists() and not loans.CollateralAppraisal.objects.exists()
                    and not loans.PawnLoanDisbursalSnapshot.objects.exists(),"Unexpected servicing or historical disbursal/appraisal rows.")
            actual_closed = {e.source_id:e for e in loans.HistoricalLoanEvidence.objects.all().iterator(chunk_size=500)}
            require(len(actual_closed)==meta["closed"]==loans.HistoricalLoanEvidence.objects.count(),"Closed history counts differ.")
            closed_ids = set()
            for document in read_rows(root/schema/"closed.jsonl"):
                key = document["source"]["loan_id"]
                e = actual_closed[key]
                require(e.document==document and e.source_sha256==digest(document) and e.review==review_document(document),"Closed document/findings differ.")
                closed_ids.add(key)
            excluded = {r["source_id"] for r in read_rows(root/schema/"excluded.jsonl")}
            source_ids = {k for k in json.loads((root/schema/"source-index.json").read_text()) if k.startswith("girvi_loan:")}
            require(not(set(expected)&closed_ids or set(expected)&excluded or closed_ids&excluded)
                    and set(expected)|closed_ids|excluded==source_ids,"Source loan partition differs.")
            with connection.cursor() as cursor:
                for model in rls_models:
                    cursor.execute("SELECT count(*) FROM "+connection.ops.quote_name(model._meta.db_table)+" WHERE workspace_id<>%s",[wid])
                    require(cursor.fetchone()[0]==0,"Cross-Workspace RLS exposure.")
            report["workspaces"][schema] = {"workspace_id":wid,"party_counts":dict(counts),"openings":len(expected),"closed":len(closed_ids),"excluded":len(excluded),
                "principal":str(principal),"interest":str(interest),"all_source_ids_accounted_once":True}
            progress(f"{schema}: all Party, opening, archive and interest evidence reconciled",flush=True)
    with connection.cursor() as cursor:
        for model in rls_models:
            cursor.execute("SELECT count(*) FROM "+connection.ops.quote_name(model._meta.db_table))
            require(cursor.fetchone()[0]==0,"Missing-context RLS exposure.")
    report["state"] = "RECONCILED_DATABASE_ONLY"
    report["rls_verified"] = True
    save(Path(output_dir)/"verification.json",report)
    return report
