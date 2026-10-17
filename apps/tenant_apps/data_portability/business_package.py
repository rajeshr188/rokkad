"""Owner-reviewed atomic fresh-Workspace package using released domain services."""

import json
import re
from pathlib import Path
from uuid import uuid4

from django.apps import apps
from django.core import signing
from django.core.files.base import ContentFile
from django.db import connection, transaction

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company, Membership
from apps.orgs.services.business_presentation import restore_business_presentation
from apps.subscriptions.access_policy import is_unactivated_destination
from apps.tenant_apps.loans import models as loans
from apps.tenant_apps.loans.services import business_setup_portability as setup
from apps.tenant_apps.loans.services import (
    servicing_bundle,
    closed_position_portability as closed,
)
from apps.tenant_apps.loans.services.history_setup import require_history_setup_access
from apps.tenant_apps.loans.services.history_contract import _pairs
from apps.tenant_apps.party.services import business_media_portability as customer_media
from . import exchange, services, contracts, child_contracts, children, loan_restore
from .access import require_access
from .models import (
    BusinessPackageReceipt,
    PartyIdentity,
    ChildIdentity,
    ChildSourceIdentity,
)
from .parsers import PortabilityError

PROFILE = "rokkad-business-package/1"
GRAPH_PROFILE = "rokkad-business-package/2"
MONITORING_PROFILE = "rokkad-business-package/3"
LIFECYCLE_PROFILE = "rokkad-business-package/4"
SETUP_VERSIONS = {
    PROFILE: 1,
    GRAPH_PROFILE: 2,
    MONITORING_PROFILE: 3,
    LIFECYCLE_PROFILE: 4,
}
PROFILES = set(SETUP_VERSIONS)
SALT = "fresh-business-package-review-v1"
MAX_FILE = 32 * 1024 * 1024
MAX_MEDIA = 200000
EXCLUSIONS = [
    "Users, memberships, portal grants, passwords and sessions",
    "Workspace routing/ownership, destination name and account preferences",
    "Subscriptions, commercial access decisions and provider secrets",
    "Notify settings, queued messages and delivery jobs",
    "Unpaid drafts, undisbursed proposals and unused retained historical evidence",
    "Khata, funding, storage and unsupported correction graphs (presence is held)",
    "Legacy licence verification/attestation transfer (presence is held)",
    "Source book completeness and future capture choices are not destination approval",
]
GRAPH_EXCLUSIONS = [
    *EXCLUSIONS[:4],
    "Unpaid pawn drafts, undisbursed proposals, unconnected funding drafts/cancellations and unused retained historical evidence",
    "Khata, physical verification and unsupported correction graphs (presence is held)",
    "Source licence verifications/attestations are retained claims, not destination approval",
    EXCLUSIONS[7],
]


def _access(workspace_id, actor, exporting=False):
    workspace = require_access(workspace_id, actor, "export" if exporting else "import")
    require_history_setup_access(workspace_id, actor, read_only=exporting)
    if not exporting:
        from apps.tenant_apps.loans.services.action_access import (
            require_setup_administration,
        )

        require_setup_administration(workspace_id, actor)
    return workspace


def _unsupported(workspace_id):
    for model in apps.get_app_config("loans").get_models():
        if (
            model.__name__.startswith(("Khata", "PawnPhysicalVerification"))
            and model.objects.filter(workspace_id=workspace_id).exists()
        ):
            raise PortabilityError(
                "Business package holds unsupported "
                + model.__name__
                + " data; use its reviewed adapter/recovery, never omit it."
            )


def _fresh(workspace, actor):
    # Keep ordinary HTTP recovery-only until the operator explicitly activates
    # the restored business. No billing/lifecycle override or staff grant is made.
    if not is_unactivated_destination(workspace):
        raise PortabilityError(
            "Use a fresh destination without subscription/access grants; activate it only after reconciliation."
        )
    if (
        Membership.objects.filter(company=workspace)
        .exclude(user_id=workspace.owner_id)
        .exists()
    ):
        raise PortabilityError(
            "Remove destination staff access before fresh business restoration."
        )
    if workspace.logo:
        raise PortabilityError(
            "Fresh destination already has business media; review rather than replace it."
        )
    for app_label in ("party", "loans", "rates", "notify_v2", "data_portability"):
        for model in apps.get_app_config(app_label).get_models():
            if model.objects.filter(workspace_id=workspace.pk).exists():
                raise PortabilityError(
                    "Destination business data/setup is not empty: "
                    + model._meta.label
                    + "."
                )


def _read(path, limit):
    with path.open("rb") as stream:
        content = stream.read(limit + 1)
    exchange._require(len(content) <= limit, "Business package file exceeds its bound.")
    return content


@transaction.atomic
def write_package(*, workspace_id, actor, directory, _consistent_snapshot=False):
    workspace = _access(workspace_id, actor, exporting=True)
    root = Path(directory).resolve()
    exchange._require(
        _consistent_snapshot,
        "Business package export requires the fresh repeatable-read command.",
    )
    services.require_export_snapshot()
    _unsupported(workspace_id)
    doc = exchange.write_exchange(
        workspace_id=workspace_id,
        actor=actor,
        directory=root,
        _consistent_snapshot=True,
    )
    funding_ids = set()
    for entry in doc["chunks"]:
        if entry["profile"] in {
            servicing_bundle.FUNDING_PROFILE,
            *servicing_bundle.IDENTITY_PROFILES,
        }:
            graph, _ = servicing_bundle.read_bundle(exchange.chunk_bytes(root, entry))
            ids = {r["id"] for r in graph["tables"].get("FundingLoan", [])}
            exchange._require(
                not funding_ids.intersection(ids),
                "Funding graph overlaps financial chunks.",
            )
            funding_ids.update(ids)
    required = set(
        loans.FundingLoan.objects.filter(workspace_id=workspace_id)
        .exclude(state__in=["DRAFT", "CANCELLED"])
        .values_list("pk", flat=True)
    )
    exchange._require(
        required <= funding_ids,
        "Posted funding is missing a supported connected pawn graph; use recovery rather than omit it.",
    )
    (root / "media").mkdir(mode=0o700)
    files, total = {}, sum(c["bytes"] for c in doc["chunks"])

    def save_file(field):
        nonlocal total
        with field.open("rb") as stream:
            data = stream.read(MAX_FILE + 1)
        exchange._require(
            0 < len(data) <= MAX_FILE,
            "Required package media is empty or exceeds 32 MiB.",
        )
        checksum = exchange.sha(data)
        claim = dict(
            sha256=checksum,
            bytes=len(data),
            suffix=Path(field.name).suffix.lower()[:12],
        )
        exchange._require(
            not claim["suffix"] or re.fullmatch(r"\.[a-z0-9]{1,11}", claim["suffix"]),
            "Unsafe package media extension.",
        )
        if checksum not in files:
            total += len(data)
            exchange._require(
                len(files) < MAX_MEDIA and total <= exchange.MAX_TOTAL_BYTES,
                "Package media exceeds its bounded inventory.",
            )
            files[checksum] = claim
            (root / "media" / checksum).write_bytes(data)
        return files[checksum]

    lifecycle = setup.needs_version_four(workspace_id)
    monitoring = lifecycle or setup.needs_version_three(workspace_id)
    graph = (
        monitoring
        or setup.needs_version_two(workspace_id)
        or any(
            entry["profile"] in servicing_bundle.PROFILES - {servicing_bundle.PROFILE}
            for entry in doc["chunks"]
        )
    )
    profile = (
        LIFECYCLE_PROFILE
        if lifecycle
        else MONITORING_PROFILE if monitoring else GRAPH_PROFILE if graph else PROFILE
    )
    tables = setup.export_setup(
        workspace_id=workspace_id,
        actor=actor,
        save_file=save_file,
        version=SETUP_VERSIONS[profile],
    )
    raw = contracts.dump(tables).encode()
    exchange._require(len(raw) <= setup.MAX_BYTES, "Business setup exceeds 16 MiB.")
    (root / "setup.json").write_bytes(raw)
    identities = dict(
        PartyIdentity.objects.filter(workspace_id=workspace_id).values_list(
            "party_id", "public_id"
        )
    )
    identifiers = {
        pk: str(uid)
        for pk, uid in ChildIdentity.objects.filter(
            workspace_id=workspace_id, profile=child_contracts.IDENTIFIER
        ).values_list("identifier_id", "public_id")
    }
    customers = customer_media.export_customers(
        workspace_id=workspace_id,
        identities=identities,
        child_identities=identifiers,
        save_file=save_file,
    )
    source_ids = [pk for entry in doc["chunks"] for pk in entry["source_loan_ids"]]
    bindings = {
        str(row.pk): dict(
            series=row.series_id,
            revision=row.license_revision_id,
            product=row.product_version_id,
        )
        for row in loans.PawnLoan.objects.filter(
            workspace_id=workspace_id, pk__in=source_ids
        )
    }
    presentation = dict(
        source_name=workspace.name,
        theme=str(workspace.theme),
        loan_workflow=workspace.loan_workflow,
        logo=save_file(workspace.logo)["sha256"] if workspace.logo else "",
    )
    package = dict(
        profile=profile,
        exchange_sha256=doc["sha256"],
        setup_sha256=exchange.sha(raw),
        source_namespace=doc["source_namespace"],
        snapshot=doc["snapshot"],
        counts=doc["counts"],
        setup_counts={key: len(rows) for key, rows in tables.items()},
        customers=customers,
        bindings=bindings,
        files=files,
        presentation=presentation,
        exclusions=GRAPH_EXCLUSIONS if graph else EXCLUSIONS,
    )
    package["sha256"] = contracts.digest(package)
    raw = contracts.dump(package).encode()
    exchange._require(
        len(raw) <= MAX_FILE
        and total + len(raw) + (root / "setup.json").stat().st_size
        <= exchange.MAX_TOTAL_BYTES,
        "Business package exceeds its manifest or aggregate size bound.",
    )
    (root / "package.json").write_bytes(raw)
    AuditLog.log(
        "DATA_EXPORT",
        company=workspace,
        user=actor,
        description="Prepared fresh business package from one repeatable-read snapshot.",
        data=dict(profile=profile, sha256=package["sha256"], counts=package["counts"]),
    )
    return package


def read_package(directory, *, expected_sha256):
    root = Path(directory).resolve()
    exchange._require(
        root.is_dir()
        and not (root / "package.json").is_symlink()
        and not (root / "setup.json").is_symlink(),
        "Invalid private business package directory.",
    )
    package = json.loads(
        _read(root / "package.json", MAX_FILE), object_pairs_hook=_pairs
    )
    exchange._require(
        type(package) is dict
        and set(package)
        == {
            "profile",
            "exchange_sha256",
            "setup_sha256",
            "source_namespace",
            "snapshot",
            "counts",
            "setup_counts",
            "customers",
            "bindings",
            "files",
            "presentation",
            "exclusions",
            "sha256",
        },
        "Invalid business package manifest fields.",
    )
    exchange._require(
        package["profile"] in PROFILES
        and package["exclusions"]
        == (EXCLUSIONS if package["profile"] == PROFILE else GRAPH_EXCLUSIONS)
        and package["sha256"]
        == expected_sha256
        == contracts.digest({k: v for k, v in package.items() if k != "sha256"}),
        "Business package checksum or profile differs.",
    )
    doc = exchange.read_manifest(root, expected_sha256=package["exchange_sha256"])
    exchange._require(
        package["profile"] != PROFILE
        or all(
            entry["profile"]
            not in servicing_bundle.PROFILES - {servicing_bundle.PROFILE}
            for entry in doc["chunks"]
        ),
        "Version-one package cannot contain wider financial profiles.",
    )
    exchange._require(
        doc["include_loans"]
        and all(
            package[k] == doc[k] for k in ("source_namespace", "snapshot", "counts")
        ),
        "Business package exchange coverage differs.",
    )
    raw = _read(root / "setup.json", setup.MAX_BYTES)
    exchange._require(
        exchange.sha(raw) == package["setup_sha256"], "Business setup bytes changed."
    )
    tables = setup.validate_tables(
        json.loads(raw, object_pairs_hook=_pairs),
        version=SETUP_VERSIONS[package["profile"]],
    )
    exchange._require(
        package["setup_counts"] == {k: len(v) for k, v in tables.items()},
        "Business setup counts differ.",
    )
    exchange._require(
        type(package["customers"]) is list
        and len(package["customers"]) == doc["counts"][contracts.PROFILE]
        and len({row["id"] for row in package["customers"]})
        == len(package["customers"]),
        "Customer media/register coverage differs.",
    )
    exchange._require(
        type(package["files"]) is dict and len(package["files"]) <= MAX_MEDIA,
        "Invalid package file inventory.",
    )
    exchange._require(
        type(package["presentation"]) is dict
        and set(package["presentation"])
        == {"source_name", "theme", "loan_workflow", "logo"}
        and all(type(value) is str for value in package["presentation"].values())
        and package["presentation"]["loan_workflow"] in {"SIMPLE", "EXTENDED"}
        and (
            not package["presentation"]["logo"]
            or package["presentation"]["logo"] in package["files"]
        ),
        "Invalid business presentation settings.",
    )
    total = (
        sum(e["bytes"] for e in doc["chunks"])
        + len(raw)
        + (root / "package.json").stat().st_size
    )
    for checksum, claim in package["files"].items():
        exchange._require(
            type(claim) is dict
            and set(claim) == {"sha256", "bytes", "suffix"}
            and re.fullmatch(r"[0-9a-f]{64}", checksum)
            and claim["sha256"] == checksum
            and type(claim["bytes"]) is int
            and 0 < claim["bytes"] <= MAX_FILE
            and (
                claim["suffix"] == ""
                or re.fullmatch(r"\.[a-z0-9]{1,11}", claim["suffix"])
            ),
            "Invalid package file claim.",
        )
        _file(root, package, checksum)
        total += claim["bytes"]
    exchange._require(
        total <= exchange.MAX_TOTAL_BYTES, "Business package exceeds 20 GiB."
    )
    exchange._require(
        set(package["bindings"])
        == {str(pk) for c in doc["chunks"] for pk in c["source_loan_ids"]},
        "Loan setup binding coverage differs.",
    )
    for entry in doc["chunks"]:
        exchange.chunk_bytes(root, entry)
    return package, doc, tables


def _file(root, package, checksum):
    exchange._require(
        type(checksum) is str and checksum in package["files"],
        "Missing package media claim.",
    )
    path = root / "media" / checksum
    exchange._require(
        path.resolve().is_relative_to(root) and not path.is_symlink(),
        "Package media path escapes its directory.",
    )
    data = _read(path, MAX_FILE)
    claim = package["files"][checksum]
    exchange._require(
        exchange.sha(data) == checksum and len(data) == claim["bytes"],
        "Required package media is missing or changed.",
    )
    return data


def _restore(workspace, actor, root, package, doc, tables, saved_files):
    def save_file(field, data):
        checksum = exchange.sha(data)
        suffix = package["files"].get(checksum, {}).get("suffix", ".json")
        field.save(f"package-{uuid4().hex}{suffix}", ContentFile(data), save=False)
        saved_files.append((field.storage, field.name))

    version = SETUP_VERSIONS[package["profile"]]
    refs = setup.restore_setup(
        workspace_id=workspace.pk,
        actor=actor,
        tables=tables,
        version=version,
        namespace=doc["source_namespace"],
        load_file=lambda key: _file(root, package, key),
        save_file=save_file,
    )
    restore_business_presentation(
        workspace=workspace,
        actor=actor,
        values=package["presentation"],
        load_file=lambda key: _file(root, package, key),
        save_file=save_file,
    )
    role_map = {row["key"]: row["key"] for row in tables["party.PartyRoleType"]}
    summary, results = (
        dict(
            profile=package["profile"],
            counts=package["counts"],
            setup_counts=package["setup_counts"],
            files=len(package["files"]),
            loans=[],
            disabled_licences=len(tables["loans.LoanLicense"]),
            presentation=package["presentation"],
            exclusions=package["exclusions"],
        ),
        [],
    )
    for entry in doc["chunks"]:
        content = exchange.chunk_bytes(root, entry)
        if entry["profile"] in exchange.PARTY_MODELS:
            batch = services.stage_import(
                workspace_id=workspace.pk,
                actor=actor,
                content=content,
                filename=entry["path"],
                source_system="rokkad:" + doc["source_namespace"],
            )
            mapping = (
                dict(role_type_map=role_map)
                if entry["profile"] == child_contracts.ROLE
                else {}
            )
            batch = services.validate_import(
                workspace_id=workspace.pk,
                actor=actor,
                batch_id=batch.public_id,
                mapping=mapping,
            )
            exchange._require(
                batch.state == "READY",
                "Customer source conflicts require individual review; package will not infer merges or duplicate exceptions.",
            )
            services.commit_import(
                workspace_id=workspace.pk,
                actor=actor,
                batch_id=batch.public_id,
                approval_digest=batch.approval_digest,
                acknowledge_warnings=True,
                _preserve_business_codes=True,
            )
        else:
            profile, metadata = loan_restore.classify(content)
            selected = {}
            for source, row in zip(entry["source_loan_ids"], metadata["loans"]):
                binding = package["bindings"][str(source)]
                exchange._require(
                    type(binding) is dict
                    and set(binding) == {"series", "revision", "product"},
                    "Invalid source setup binding.",
                )
                parent = children.parent_for(
                    dict(
                        party_source_system=row["borrower"]["system"],
                        party_external_id=row["borrower"]["id"],
                    ),
                    workspace.pk,
                )
                exchange._require(
                    parent is not None, "Missing exact package borrower identity."
                )
                values = dict(
                    borrower_id=parent.party_id,
                    series_id=refs["loans.LoanSeries"][binding["series"]].pk,
                )
                if profile in servicing_bundle.PROFILES:
                    values.update(
                        revision_id=refs["loans.LoanLicenseRevision"][
                            binding["revision"]
                        ].pk,
                        product_version_id=refs["loans.LoanProductVersion"][
                            binding["product"]
                        ].pk,
                    )
                selected[row["key"]] = values
            args = dict(workspace_id=workspace.pk, actor=actor, content=content)
            if profile in servicing_bundle.PROFILES:
                review = servicing_bundle.restore_servicing_bundle(
                    **args, mapping=selected
                )
                result = servicing_bundle.restore_servicing_bundle(
                    **args,
                    mapping=selected,
                    expected_sha256=review["sha256"],
                    confirmed=True,
                    _outer_saved_files=saved_files,
                )
                results.extend(result["loans"])
                summary["loans"].extend(review["summary"]["loans"])
            else:
                values = next(iter(selected.values()))
                review, token = closed.preview_closed_position_file(**args, **values)
                loan, _ = closed.admit_closed_position_file(
                    **args,
                    **values,
                    review_token=token,
                    confirmed=True,
                    _outer_saved_files=saved_files,
                )
                results.append(loan.pk)
                summary["loans"].append(
                    dict(source_number=metadata["loans"][0]["number"], position=review)
                )
    identifiers = {
        source.external_id: source.identity.identifier
        for source in ChildSourceIdentity.objects.filter(
            workspace_id=workspace.pk,
            profile=child_contracts.IDENTIFIER,
            source_system="rokkad:" + doc["source_namespace"],
        ).select_related("identity__identifier")
    }
    for record in package["customers"]:
        parent = children.parent_for(
            dict(
                party_source_system="rokkad:" + doc["source_namespace"],
                party_external_id=record["id"],
            ),
            workspace.pk,
        )
        exchange._require(parent is not None, "Missing customer media parent.")
        customer_media.restore_customer(
            workspace_id=workspace.pk,
            actor=actor,
            record=record,
            party=parent.party,
            identifiers=identifiers,
            load_file=lambda key: _file(root, package, key),
            save_file=save_file,
        )
    exchange._require(
        len(set(results)) == len(results) == package["counts"]["loans"]
        and loans.PawnLoan.objects.filter(workspace_id=workspace.pk).count()
        == len(results),
        "Financial reconciliation count differs.",
    )
    for profile, model in exchange.PARTY_MODELS.items():
        exchange._require(
            model.objects.filter(workspace_id=workspace.pk).count()
            == package["counts"][profile],
            "Customer reconciliation count differs.",
        )
    for label, model in setup.models(version).items():
        exchange._require(
            model.objects.filter(workspace_id=workspace.pk).count()
            == package["setup_counts"][label],
            "Business setup reconciliation count differs: " + label,
        )
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cursor.execute("SET CONSTRAINTS ALL DEFERRED")
    return summary, results


def preview_package(*, workspace_id, actor, directory, expected_sha256):
    saved_files = []
    try:
        with transaction.atomic():
            workspace = Company.all_objects.select_for_update().get(pk=workspace_id)
            _access(workspace_id, actor)
            _fresh(workspace, actor)
            package, doc, tables = read_package(
                directory, expected_sha256=expected_sha256
            )
            summary, _ = _restore(
                workspace,
                actor,
                Path(directory).resolve(),
                package,
                doc,
                tables,
                saved_files,
            )
            transaction.set_rollback(True)
        approval = signing.dumps(
            dict(
                workspace=workspace_id,
                actor=actor.pk,
                source=expected_sha256,
                summary=contracts.digest(summary),
            ),
            salt=SALT,
        )
        return dict(summary=summary, approval=approval)
    finally:
        for storage, name in saved_files:
            storage.delete(name)


def restore_package(
    *,
    workspace_id,
    actor,
    directory,
    expected_sha256,
    approval,
    confirmed=False,
    _outer_saved_files=None,
):
    _access(workspace_id, actor)
    exchange._require(
        confirmed is True, "Confirm the reviewed package before restoration."
    )
    try:
        token = signing.loads(approval, salt=SALT, max_age=3600)
    except signing.BadSignature, TypeError, ValueError:
        raise PortabilityError(
            "Review the business package again; approval is missing or expired."
        ) from None
    exchange._require(
        token.get("workspace") == workspace_id
        and token.get("actor") == actor.pk
        and token.get("source") == expected_sha256,
        "Package approval belongs to another actor, Workspace or source.",
    )
    saved_files, committed = [], False
    try:
        with transaction.atomic():
            workspace = Company.all_objects.select_for_update().get(pk=workspace_id)
            _access(workspace_id, actor)
            existing = BusinessPackageReceipt.objects.filter(
                workspace_id=workspace_id
            ).first()
            if existing:
                exchange._require(
                    existing.source_sha256 == expected_sha256
                    and contracts.digest(existing.summary) == token["summary"],
                    "Destination already has a different accepted package.",
                )
                with existing.source.open("rb") as source:
                    retained = source.read(2 * MAX_FILE + setup.MAX_BYTES + 1)
                exchange._require(
                    len(retained) <= 2 * MAX_FILE + setup.MAX_BYTES
                    and exchange.sha(retained) == existing.source_file_sha256,
                    "Retained package evidence is missing or changed; no records were reapplied.",
                )
                return existing
            _fresh(workspace, actor)
            package, doc, tables = read_package(
                directory, expected_sha256=expected_sha256
            )
            summary, results = _restore(
                workspace,
                actor,
                Path(directory).resolve(),
                package,
                doc,
                tables,
                saved_files,
            )
            exchange._require(
                contracts.digest(summary) == token["summary"],
                "Reconciliation changed after review; restore rolled back.",
            )
            source = contracts.dump(
                dict(package=package, exchange=doc, setup=tables)
            ).encode()
            receipt = BusinessPackageReceipt(
                workspace_id=workspace_id,
                source_sha256=expected_sha256,
                source_file_sha256=exchange.sha(source),
                summary=summary,
                results=results,
                created_by=actor,
            )
            receipt.source.save("source.json", ContentFile(source), save=False)
            saved_files.append((receipt.source.storage, receipt.source.name))
            receipt.save()
            AuditLog.log(
                "DATA_IMPORT",
                company=workspace,
                user=actor,
                content_object=receipt,
                description="Restored and reconciled an atomic fresh business package; lending and commercial activation remain separate.",
                data=dict(
                    profile=package["profile"],
                    sha256=expected_sha256,
                    receipt=str(receipt.public_id),
                    counts=summary["counts"],
                ),
            )
        committed = True
        if _outer_saved_files is not None:
            _outer_saved_files.extend(saved_files)
        return receipt
    finally:
        if not committed:
            for storage, name in saved_files:
                storage.delete(name)
