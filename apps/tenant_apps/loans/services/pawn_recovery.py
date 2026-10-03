"""Native, exact-identity ordinary Loans disaster recovery; never a paper-loan importer.

Restore is an offline table-owner operation into an empty ordinary Loans Workspace in a
matching restored database. Runtime code cannot disable evidence triggers. The
independently retained ZIP checksum is mandatory; this is a trusted backup, not
an admission path for edited or third-party financial records.
"""
import hashlib
import json
from datetime import date
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.db import connection
from django.utils import timezone

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from .action_access import require_workspace_action

FORMAT = "ordinary-loans-native-recovery/1"
MODEL_NAMES = (
    "LoanLicense",
    "LoanSeries",
    "PawnLoanEconomicPolicy",
    "PawnMetalInterestRatePolicy",
    "PawnLoanFeePolicy",
    "LoanNumberSequence",
    "PawnLoan",
    "PawnCollateralItem",
    "LoanPolicySnapshot",
    "LoanChangeLog",
    "PawnLoanApprovalSnapshot",
    "PawnLoanEvent",
    "PawnLoanDisbursalSnapshot",
    "PawnLoanInterestAccrual",
    "PawnLoanInterestAccrualLine",
    "PawnLoanRepaymentAllocationLine",
    "PawnLoanPrincipalClosingLine",
    "PawnLoanPrincipalOpeningLine",
    "PawnLoanRelease",
    "PawnLoanReleaseItem",
    "PawnCollateralCustodyEvent",
    "PawnLoanReleaseReversal",
    "PawnLoanNotice",
    "PawnLoanAuction",
    "PawnLoanAuctionItem",
    "PawnLoanAuctionReversal",
    "PawnLoanRenewal",
    "PawnLoanRenewalReversal",
    "LoanDocumentLayout",
    "LoanDocumentLayoutRevision",
    "LoanDocumentAsset",
    "LoanDocumentLayoutAssignment",
    "LoanDocumentPrintProfile",
    "LoanDocumentPrintProfileRevision",
    "LoanDocumentPrintProfileAssignment",
    "LoanDocumentIssue",
    "FundingLoanSequence",
    "FundingLoan",
    "FundingLoanDraftTerms",
    "FundingLoanDraftCollateral",
    "FundingLoanCancellation",
    "FundingLoanTermsSnapshot",
    "FundingLoanEvent",
    "FundingPledge",
    "FundingPledgeItem",
    "FundingReturn",
    "FundingReturnItem",
    "FundingPledgeReversal",
    "FundingReturnReversal",
    "LoanLicenseRevision",
    "PawnCollateralPhoto",
    "PawnCollateralLabelIssue",
    "PawnStorageLocation",
    "PawnCollateralStorageMovement",
    "PawnPhysicalVerificationSession",
    "PawnPhysicalVerificationExpectation",
    "PawnPhysicalVerificationObservation",
    "PawnPhysicalVerificationResolution",
    "LoanOperationalNotice",
    "StatutoryAuctionNotice",
    "StatutoryNoticeEvidence",
    "LoanProduct",
    "LoanProductVersion",
    "RepaymentScheduleVersion",
    "RepaymentObligation",
    "RepaymentScheduleChange",
    "ObligationAllocation",
    "CollateralAppraisal",
    "PawnLoanCommunicationConsent",
    "PawnLoanCommunicationPolicy",
    "LoanMonitoringPolicy",
    "LoanRiskSnapshot",
    "LoanRiskEvent",
    "LoanRiskAlert",
    "PawnReleaseBatch",
    "PawnReleaseBatchLine",
    "PaperClosureTransition",
    "LoanOriginationSettings",
    "HistoricalLoanImport",
    "PledgeBook",
    "PledgeBookReview",
    "PledgeBookBatch",
    "PledgeBookEntry",
    "AuctioneerHandover",
    "AuctioneerHandoverRevision",
    "HistoricalLoanEvidence",
    "HistoricalLoanAttachment",
    "LoanTransactionReview",
    "PaperBacklogCheckpoint",
)
MAX_BYTES = 256 * 1024 * 1024
MAX_ROWS = 50000


class _PreviewRollback(Exception):
    def __init__(self, result):
        self.result = result


def _models():
    models = tuple(apps.get_model("loans", name) for name in MODEL_NAMES)
    ordinary = {m for m in apps.get_app_config("loans").get_models() if not m.__name__.startswith("Khata")}
    if set(models) != ordinary:
        raise ValueError("Ordinary Loans recovery inventory changed; update the versioned profile first.")
    return models


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def _row(obj, fields=None):
    fields = fields or obj._meta.concrete_fields
    return {f.attname: None if getattr(obj, f.attname) is None else
        f.value_from_object(obj) if f.get_internal_type() == "JSONField" else f.value_to_string(obj) for f in fields}


def _schema():
    return {m._meta.label: [[f.attname, f.get_internal_type(), f.max_length,
        getattr(f, "max_digits", None), getattr(f, "decimal_places", None)] for f in m._meta.concrete_fields] for m in _models()}


def _guards():
    """Refuse same-field schemas whose financial guard definitions have changed."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT c.relname, t.tgname, pg_get_triggerdef(t.oid), pg_get_functiondef(t.tgfoid) "
            "FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid WHERE t.tgrelid = ANY(%s::regclass[]) "
            "AND NOT t.tgisinternal ORDER BY c.relname, t.tgname", [[m._meta.db_table for m in _models()]])
        triggers = cursor.fetchall()
        tables = [m._meta.db_table for m in _models()]
        cursor.execute("SELECT c.relname, x.conname, pg_get_constraintdef(x.oid) FROM pg_constraint x "
            "JOIN pg_class c ON c.oid=x.conrelid WHERE x.conrelid = ANY(%s::regclass[]) ORDER BY c.relname,x.conname", [tables])
        constraints = cursor.fetchall()
        cursor.execute("SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid = ANY(%s::regclass[]) ORDER BY relname", [tables])
        rls = cursor.fetchall()
        cursor.execute("SELECT tablename,policyname,permissive,roles,cmd,qual,with_check FROM pg_policies "
            "WHERE schemaname='public' AND tablename=ANY(%s) ORDER BY tablename,policyname", [tables])
        return _digest(_json(dict(triggers=triggers, constraints=constraints, rls=rls, policies=cursor.fetchall())))


def _identity(workspace):
    return dict(id=workspace.pk, slug=workspace.slug, schema_name=workspace.schema_name)


def _reference(obj):
    # Authentication secrets and mutable login details are never backup content.
    if obj._meta.app_label == "auth" or isinstance(obj, get_user_model()):
        fields = [obj._meta.pk, obj._meta.get_field(obj.USERNAME_FIELD), obj._meta.get_field("date_joined")]
        data = _row(obj, fields)
    elif isinstance(obj, Company):
        data = _identity(obj)
    else:
        data = _row(obj)
    return dict(model=obj._meta.label, id=obj.pk, sha256=_digest(_json(data)))


def _position(workspace, as_of):
    from apps.tenant_apps.loans.models import PawnLoan
    from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
    from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness, transaction_fingerprint
    from .recorded_collections import recording_for, collection_balance
    rows = []
    for loan in PawnLoan.objects.filter(workspace=workspace).order_by("pk"):
        balance = get_pawn_loan_balance(loan, as_of_date=as_of)
        agreed = collection_balance(loan, as_of) if recording_for(loan) and as_of >= loan.loan_date else balance
        rows.append(dict(id=loan.pk, state=loan.state, fingerprint=transaction_fingerprint(loan),
            principal=str(balance.principal_outstanding), interest=str(balance.interest_outstanding),
            fees=str(balance.fees_outstanding), agreed_total=str(agreed.total_due),
            coverage=transaction_completeness(loan, as_of).evidence(),
            collateral=[dict(id=item.pk, custody=item.custody_state, storage=item.current_storage_location_id,
                predecessor=item.renewed_from_id) for item in loan.collateral_items.order_by("pk")]))
    return rows


def _file_evidence(obj, field, data):
    name = getattr(obj, field.name).name
    path = PurePosixPath(name)
    owned_prefix = ("loans/", f"legacy_import/{obj.workspace_id}/")
    if not name.startswith(owned_prefix) or path.is_absolute() or ".." in path.parts or "\\" in name:
        raise ValueError("Recovery media path is outside Loans evidence storage.")
    if field.name == "artifact":
        expected = getattr(obj, "artifact_sha256", None) or getattr(obj, "pdf_hash", None)
    elif field.name == "attachment":
        expected = obj.attachment_sha256
    else:
        expected = obj.sha256
    if not expected or _digest(data) != expected or (hasattr(obj, "byte_size") and len(data) != obj.byte_size):
        raise ValueError("Retained ordinary Loans file is missing or corrupt.")


def _lock(workspace):
    Company.objects.select_for_update().get(pk=workspace.pk)
    with connection.cursor() as cursor:
        cursor.execute("LOCK TABLE " + ", ".join(connection.ops.quote_name(m._meta.db_table) for m in _models()) + " IN SHARE ROW EXCLUSIVE MODE")


def export_archive(*, workspace, actor):
    """Capture all ordinary Loans rows and original file bytes under a stable write lock."""
    with workspace_context(workspace.pk):
        require_workspace_action(workspace, actor, "data.export")
        _lock(workspace)
        models = _models()
        tables, references, files = {}, {}, {}
        count = 0
        file_bytes = 0
        for model in models:
            rows = []
            for obj in model.objects.filter(workspace=workspace).order_by("pk").iterator():
                count += 1
                if count > MAX_ROWS:
                    raise ValueError("Ordinary Loans archive exceeds the bounded row count; use full database/media recovery.")
                rows.append(_row(obj))
                for field in model._meta.concrete_fields:
                    if field.is_relation and field.related_model not in models and getattr(obj, field.attname) is not None:
                        related = getattr(obj, field.name)
                        if hasattr(related, "workspace_id") and related.workspace_id != workspace.pk:
                            raise ValueError("Ordinary Loans prerequisite belongs to another Workspace.")
                        references[(related._meta.label, related.pk)] = _reference(related)
                    if field.get_internal_type() == "FileField":
                        value = getattr(obj, field.name)
                        if not value.name:
                            continue
                        with value.open("rb") as stream:
                            content = stream.read(MAX_BYTES + 1)
                        _file_evidence(obj, field, content)
                        if value.name not in files:
                            file_bytes += len(content)
                            if file_bytes > MAX_BYTES:
                                raise ValueError("Ordinary Loans media exceeds the bounded archive size.")
                        files[value.name] = content
            tables[model._meta.label] = rows
        manifest = dict(format=FORMAT, workspace=_identity(workspace), exported_at=timezone.now().isoformat(),
            as_of=timezone.localdate().isoformat(), schema=_schema(), guards_sha256=_guards(), tables=tables,
            prerequisites=sorted(references.values(), key=lambda r: (r["model"], r["id"])),
            reconciliation=_position(workspace, timezone.localdate()),
            files={name: dict(size=len(content), sha256=_digest(content)) for name, content in files.items()})
        raw = _json(manifest)
        if len(raw) + sum(map(len, files.values())) > MAX_BYTES:
            raise ValueError("Ordinary Loans archive exceeds the bounded byte size; use full database/media recovery.")
        buffer = BytesIO()
        with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
            archive.writestr("manifest.json", raw)
            for name, content in files.items():
                archive.writestr("media/" + name, content)
        return buffer.getvalue()


def _read(content, expected_sha256):
    if not expected_sha256 or _digest(content) != expected_sha256.lower():
        raise ValueError("Archive SHA-256 does not match the independently retained backup checksum.")
    if len(content) > MAX_BYTES:
        raise ValueError("Archive is too large.")
    try:
        with ZipFile(BytesIO(content)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or sum(i.file_size for i in archive.infolist()) > MAX_BYTES:
                raise ValueError("Duplicate ZIP members or excessive expanded archive size.")
            for name in names:
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts or "\\" in name:
                    raise ValueError("Unsafe archive member path.")
            manifest = json.loads(archive.read("manifest.json"))
            if manifest["format"] != FORMAT or manifest["schema"] != _schema() or manifest["guards_sha256"] != _guards():
                raise ValueError("Unsupported recovery format or changed model schema.")
            if set(manifest["tables"]) != set(_schema()) or sum(map(len, manifest["tables"].values())) > MAX_ROWS:
                raise ValueError("Incorrect recovery table inventory or excessive rows.")
            if set(names) != {"manifest.json", *("media/" + name for name in manifest["files"])}:
                raise ValueError("Archive file inventory differs from its manifest.")
            files = {}
            for name, evidence in manifest["files"].items():
                data = archive.read("media/" + name)
                if len(data) != evidence["size"] or _digest(data) != evidence["sha256"]:
                    raise ValueError("Archive media bytes differ from their manifest.")
                files[name] = data
            return manifest, files
    except (BadZipFile, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid native ordinary Loans archive.") from exc


def _owner_only():
    with connection.cursor() as cursor:
        cursor.execute("SELECT c.relname, pg_has_role(current_user, c.relowner, 'USAGE') FROM pg_class c WHERE c.oid = ANY(%s::regclass[])",
            [[m._meta.db_table for m in _models()]])
        result = cursor.fetchall()
        if len(result) != len(MODEL_NAMES) or not all(owns for _, owns in result):
            raise ValueError("Ordinary Loans restore requires the offline table-owner connection, never the runtime role.")
        cursor.execute("SELECT tgname, tgenabled FROM pg_trigger WHERE tgrelid = ANY(%s::regclass[]) AND NOT tgisinternal",
            [[m._meta.db_table for m in _models()]])
        if any(enabled != "O" for _, enabled in cursor.fetchall()):
            raise ValueError("Ordinary Loans evidence triggers must all be enabled before recovery.")


def restore_archive(*, workspace, actor, content, expected_sha256, commit=False):
    """Preview by performing and rolling back an exact restore and reconciliation.

    The destination must contain no ordinary Loans rows. All prerequisite identities must
    already match from full database recovery. No merge, key remapping, historical
    cash replay or ordinary-loan numbering mutation is supported.
    """
    manifest, files = _read(content, expected_sha256)
    if manifest["workspace"] != _identity(workspace):
        raise ValueError("Restore requires the original Workspace identity in a recovered database.")
    created = []
    try:
        with workspace_context(workspace.pk):
            require_workspace_action(workspace, actor, "workspace.transfer", "data.export")
            _owner_only()
            _lock(workspace)
            for model in _models():
                if model.objects.filter(workspace=workspace).exists():
                    raise ValueError("Destination already contains ordinary Loans evidence; restore never overwrites or merges it.")
            for evidence in manifest["prerequisites"]:
                model = apps.get_model(evidence["model"])
                obj = model._base_manager.filter(pk=evidence["id"]).first()
                if obj is None or _reference(obj) != evidence:
                    raise ValueError("A required Workspace, borrower, actor, licence or rate identity differs from the backup.")
            # PostgreSQL enforces owner-only ALTER TABLE. FK/CHECK/UNIQUE and forced
            # RLS stay enabled. Restore preserves final projections, not fake events.
            with connection.cursor() as cursor:
                for model in _models():
                    cursor.execute(f"ALTER TABLE {connection.ops.quote_name(model._meta.db_table)} DISABLE TRIGGER USER")
                for model in _models():
                    fields = model._meta.concrete_fields
                    expected_fields = {f.attname for f in fields}
                    columns = ", ".join(connection.ops.quote_name(f.column) for f in fields)
                    for row in manifest["tables"][model._meta.label]:
                        if set(row) != expected_fields or int(row["workspace_id"]) != workspace.pk:
                            raise ValueError("Recovery row inventory or Workspace ownership mismatch.")
                        values = [f.get_db_prep_save(f.target_field.to_python(row[f.attname]) if f.is_relation else f.to_python(row[f.attname]), connection=connection) for f in fields]
                        cursor.execute(f"INSERT INTO {connection.ops.quote_name(model._meta.db_table)} ({columns}) VALUES ({', '.join(['%s'] * len(fields))})", values)
                connection.check_constraints()
                # Validate all typed references while rows are visible under RLS.
                for model in _models():
                    for obj in model.objects.filter(workspace=workspace).iterator():
                        for field in model._meta.concrete_fields:
                            if field.is_relation and getattr(obj, field.attname) is not None:
                                related = getattr(obj, field.name)
                                if hasattr(related, "workspace_id") and related.workspace_id != workspace.pk:
                                    raise ValueError("Recovery reference crosses Workspace ownership.")
                        for field in model._meta.concrete_fields:
                            if field.get_internal_type() != "FileField":
                                continue
                            file = getattr(obj, field.name)
                            if not file.name:
                                continue
                            if file.name not in files:
                                raise ValueError("Recovery file is absent from the archive.")
                            data = files[file.name]
                            _file_evidence(obj, field, data)
                            if file.storage.exists(file.name):
                                with file.storage.open(file.name, "rb") as stream:
                                    original = stream.read(len(data) + 1)
                                if original != data:
                                    raise ValueError("Existing destination media conflicts with the backup.")
                            elif commit:
                                saved = file.storage.save(file.name, ContentFile(data))
                                created.append((file.storage, saved))
                                if saved != file.name:
                                    raise ValueError("Destination media was concurrently created; exact restore refused.")
                for model in _models():
                    restored = [_row(obj) for obj in model.objects.filter(workspace=workspace).order_by("pk")]
                    if restored != manifest["tables"][model._meta.label]:
                        raise ValueError("Restored typed evidence differs from the backup.")
                if _position(workspace, date.fromisoformat(manifest["as_of"])) != manifest["reconciliation"]:
                    raise ValueError("Restored financial balance, transaction coverage or custody differs from the backup.")
                for model in _models():
                    cursor.execute(f"ALTER TABLE {connection.ops.quote_name(model._meta.db_table)} ENABLE TRIGGER USER")
                    if commit:
                        # Explicit restored PKs must not collide with future IDs;
                        # sequence values never move backwards, including rollback.
                        table = model._meta.db_table
                        cursor.execute("SELECT pg_get_serial_sequence(%s, 'id')", [table])
                        sequence = cursor.fetchone()[0]
                        cursor.execute(f"SELECT max(id) FROM {connection.ops.quote_name(table)}")
                        maximum = cursor.fetchone()[0] or 1
                        cursor.execute("SELECT pg_sequence_last_value(%s::regclass)", [sequence])
                        current = cursor.fetchone()[0] or 1
                        cursor.execute("SELECT setval(%s::regclass, %s, true)", [sequence, max(maximum, current)])
            result = dict(format=FORMAT, workspace=workspace.pk, committed=commit,
                rows={name: len(rows) for name, rows in manifest["tables"].items()},
                media=len(files), reconciliation=manifest["reconciliation"], sha256=_digest(content))
            if not commit:
                raise _PreviewRollback(result)
            return result
    except _PreviewRollback as preview:
        return preview.result
    except BaseException:
        for storage, name in reversed(created):
            storage.delete(name)
        raise
