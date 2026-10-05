"""Reserve a real paper number without allowing the live counter to reuse it."""
import unicodedata

from apps.tenant_apps.loans import models as m


def identity(value):
    return " ".join(unicodedata.normalize("NFKC", str(value)).split()).casefold()


def reject_existing_source(workspace_id, number, *, archive_ids=(), existing_loan_id=None):
    key = identity(number)
    if any(identity(n) == key for n in m.PawnLoan.objects.filter(workspace_id=workspace_id).exclude(pk=existing_loan_id).values_list("loan_number", flat=True)):
        raise ValueError(f"Loan number {number} already exists. Open the existing loan instead.")
    for source_number in m.HistoricalLoanEvidence.objects.filter(workspace_id=workspace_id).exclude(pk__in=archive_ids).values_list("document__facts__loan_number", flat=True):
        if source_number is not None and identity(source_number) == key:
            raise ValueError(f"{number} is retained in historical evidence. Use reviewed archive admission; do not enter it twice.")
    for doc in m.HistoricalLoanImport.objects.filter(workspace_id=workspace_id).values_list("document", flat=True):
        numbers = (doc.get("source", {}).get("number"), doc.get("loan", {}).get("number"),
                   doc.get("loan", {}).get("loan_number"), doc.get("review", {}).get("source", {}).get("number"),
                   doc.get("history", {}).get("number"))
        if key in {identity(n) for n in numbers if n is not None}:
            raise ValueError(f"{number} already has an imported financial origin. Reconcile its identity first.")


def claim_number(series, number, *, kind, actor, archive_ids=(), existing_loan_id=None):
    """Atomic caller locks the Workspace first, then sequences in primary-key order."""
    if not isinstance(number, str) or not number.strip() or len(number) > 64 or number != number.strip():
        raise ValueError("Enter the original number, up to 64 characters without surrounding spaces.")
    if any(ord(c) < 32 or ord(c) == 127 for c in number):
        raise ValueError("Original numbers cannot contain control characters.")
    changes = []
    sequences = list(m.LoanNumberSequence.objects.select_for_update().filter(
        workspace_id=series.workspace_id, document_kind=kind).order_by("pk"))
    # Check after obtaining the locks: a current-date allocator may just have
    # committed a number while this admission was waiting for its sequence.
    if kind == "PAWN_LOAN":
        reject_existing_source(series.workspace_id, number, archive_ids=archive_ids, existing_loan_id=existing_loan_id)
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
    return changes
