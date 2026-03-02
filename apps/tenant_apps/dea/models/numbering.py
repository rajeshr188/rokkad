from django.db import models, transaction
from django.core.exceptions import ValidationError

from .ledger import Ledger, AccountType

SEGMENT_WIDTH = 2  # 01, 02, ...
SEPARATOR = "."


class LedgerCodeSequence(models.Model):
    """
    Holds the next sequence per (parent, root-scope) to allocate hierarchical segments safely.
    For root ledgers, parent is NULL and we scope by account_type.
    For children, we scope by parent.
    """

    parent = models.ForeignKey(
        Ledger,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="child_code_seq",
    )
    account_type = models.ForeignKey(
        AccountType, null=True, blank=True, on_delete=models.CASCADE
    )
    next_seq = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = (("parent", "account_type"),)


def _pad(n: int) -> str:
    return str(n).zfill(SEGMENT_WIDTH)


@transaction.atomic
def _allocate_segment(parent: Ledger | None, account_type: AccountType | None) -> int:
    seq, _ = LedgerCodeSequence.objects.select_for_update().get_or_create(
        parent=parent,
        account_type=account_type,
        defaults={"next_seq": 1},
    )
    n = seq.next_seq
    seq.next_seq = n + 1
    seq.save(update_fields=["next_seq"])
    return n


def generate_ledger_code(ledger: Ledger) -> str:
    """
    Generate a predictable hierarchical code:
      - root: <prefix>.<NN> (e.g., 1.01)
      - child: <parent.code>.<NN> (e.g., 1.01.02)
    Code is allocated once and must remain immutable.
    """
    if ledger.pk:
        # If already saved without a code, we still allow generation exactly once.
        pass

    parent = ledger.parent if hasattr(ledger, "parent") else None

    if parent:
        # Use parent's existing code and allocate a per-parent sequence
        if not parent.code:
            raise ValidationError(
                "Parent ledger must have a code before assigning child code."
            )
        n = _allocate_segment(parent=parent, account_type=None)
        return SEPARATOR.join([parent.code, _pad(n)])
    else:
        # Root level: require AccountType.code_prefix (e.g., '1', '2', '4', '5')
        prefix = (ledger.AccountType.code_prefix or "").strip()
        if not prefix:
            # You can fallback by deriving from AccountType label, but explicit prefix is safer
            raise ValidationError(
                "AccountType.code_prefix is required for root ledger numbering."
            )
        n = _allocate_segment(parent=None, account_type=ledger.AccountType)
        return SEPARATOR.join([prefix, _pad(n)])
