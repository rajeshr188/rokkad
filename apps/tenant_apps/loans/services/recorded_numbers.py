"""Reserve a real paper number without allowing the live counter to reuse it."""
import unicodedata
from collections import defaultdict

from django.db import connection
from apps.orgs.models import Company

from apps.tenant_apps.loans import models as m


def identity(value):
    return " ".join(unicodedata.normalize("NFKC", str(value)).split()).casefold()


class LockedNumberClaims:
    """Current collision index for one bounded, Workspace/sequence-locked batch.

    Shares the normal claim/range rules. Never cache across transactions; ordinary
    allocators take the same sequence locks before issuing a number.
    """
    def __init__(self, workspace_id):
        if not connection.in_atomic_block:
            raise ValueError("Batch number claims require an atomic transaction.")
        Company.all_objects.select_for_update().get(pk=workspace_id)
        self.atomic_root = connection.atomic_blocks[0]
        self.workspace_id = workspace_id
        self.sequences = list(m.LoanNumberSequence.objects.select_for_update().filter(
            workspace_id=workspace_id, document_kind="PAWN_LOAN").order_by("pk"))
        self.numbers = {identity(n) for n in m.PawnLoan.objects.filter(workspace_id=workspace_id).values_list("loan_number", flat=True)}
        self.archives = defaultdict(set)
        for pk, number in m.HistoricalLoanEvidence.objects.filter(workspace_id=workspace_id).values_list("pk", "search_loan_number"):
            if number is not None:
                self.archives[identity(number)].add(pk)
        # Extract only aliases in SQL, never load all retained source graphs.
        paths = ("source__number", "loan__number", "loan__loan_number", "review__source__number", "history__number", "position__loan__number")
        # Guarded closed-position number equals its ordinary loan number above;
        # it has no separate aliases. Avoid decompressing its source graphs.
        for numbers in m.HistoricalLoanImport.objects.filter(workspace_id=workspace_id,
                loan__is_imported_closed_position=False).values_list(*(f"document__{p}" for p in paths)):
            self.numbers.update(identity(n) for n in numbers if n is not None)

    def reject(self, number, archive_ids):
        key = identity(number)
        if key in self.numbers:
            raise ValueError(f"Loan number {number} already exists or has an imported origin.")
        if self.archives[key] - set(archive_ids):
            raise ValueError(f"{number} has other retained source evidence. Reconcile its identity first.")


def reject_existing_source(workspace_id, number, *, archive_ids=(), existing_loan_id=None):
    key = identity(number)
    if any(identity(n) == key for n in m.PawnLoan.objects.filter(workspace_id=workspace_id).exclude(pk=existing_loan_id).values_list("loan_number", flat=True)):
        raise ValueError(f"Loan number {number} already exists. Open the existing loan instead.")
    for source_number in m.HistoricalLoanEvidence.objects.filter(workspace_id=workspace_id).exclude(pk__in=archive_ids).values_list("search_loan_number", flat=True):
        if source_number is not None and identity(source_number) == key:
            raise ValueError(f"{number} is retained in historical evidence. Use reviewed archive admission; do not enter it twice.")
    paths = ("source__number", "loan__number", "loan__loan_number", "review__source__number", "history__number")
    for numbers in m.HistoricalLoanImport.objects.filter(workspace_id=workspace_id,
            loan__is_imported_closed_position=False).values_list(*(f"document__{p}" for p in paths)):
        if key in {identity(n) for n in numbers if n is not None}:
            raise ValueError(f"{number} already has an imported financial origin. Reconcile its identity first.")


def claim_number(series, number, *, kind, actor, archive_ids=(), existing_loan_id=None, _claims=None):
    """Atomic caller locks the Workspace first, then sequences in primary-key order."""
    if not isinstance(number, str) or not number.strip() or len(number) > 64 or number != number.strip():
        raise ValueError("Enter the original number, up to 64 characters without surrounding spaces.")
    if any(ord(c) < 32 or ord(c) == 127 for c in number):
        raise ValueError("Original numbers cannot contain control characters.")
    changes = []
    if _claims is not None:
        if (not isinstance(_claims, LockedNumberClaims) or _claims.workspace_id != series.workspace_id
                or kind != "PAWN_LOAN" or existing_loan_id is not None or not connection.in_atomic_block):
            raise ValueError("Invalid locked batch number context.")
        if _claims.atomic_root is not connection.atomic_blocks[0]:
            raise ValueError("Batch number claims cannot be reused across transactions.")
        sequences = _claims.sequences
    else:
        sequences = list(m.LoanNumberSequence.objects.select_for_update().filter(
            workspace_id=series.workspace_id, document_kind=kind).order_by("pk"))
    # Check after obtaining the locks: a current-date allocator may just have
    # committed a number while this admission was waiting for its sequence.
    if kind == "PAWN_LOAN":
        if _claims is None:
            reject_existing_source(series.workspace_id, number, archive_ids=archive_ids, existing_loan_id=existing_loan_id)
        else:
            _claims.reject(number, archive_ids)
    elif any(identity(n) == identity(number) for n in m.PawnLoanRelease.objects.filter(
            workspace_id=series.workspace_id).values_list("release_number", flat=True)):
        raise ValueError(f"Release number {number} already exists.")
    for seq in sequences:
        canonical_number, canonical_prefix = identity(number), identity(seq.prefix)
        if not canonical_number.startswith(canonical_prefix):
            continue
        suffix = canonical_number[len(canonical_prefix):]
        if not suffix.isascii() or not suffix.isdigit() or len(suffix) > 18:
            continue
        counter = int(suffix)
        if f"{counter:0{seq.width}d}" != suffix:
            continue
        if seq.series_id != series.pk and counter >= seq.next_number and counter <= seq.maximum_number:
            raise ValueError(f"{number} overlaps another series' future numbers. Reconcile the numbering setup first.")
        if seq.series_id == series.pk and counter >= seq.next_number:
            if counter > seq.maximum_number:
                raise ValueError(f"{number} exceeds this series' configured range. Review numbering setup first.")
            changes.append(dict(kind=kind, before=seq.next_number, after=counter + 1))
            m.LoanNumberSequence.objects.filter(pk=seq.pk).update(next_number=counter + 1, updated_by=actor)
            seq.next_number = counter + 1
    if _claims is not None:
        _claims.numbers.add(identity(number))
    return changes
