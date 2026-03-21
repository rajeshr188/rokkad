from decimal import Decimal

from django.db import DatabaseError, connection


def _get_subject_type(subject):
    return "ITEM" if subject._meta.model_name == "stockitem" else "LOT"


def get_subject_balance(subject, fallback):
    """Read balance from the canonical inventory view, with fallback to Python aggregation."""
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT balance_qty, balance_wt
                FROM inventory_balance
                WHERE subject_type = %s AND subject_id = %s
                """,
                [_get_subject_type(subject), subject.pk],
            )
            row = cursor.fetchone()
    except DatabaseError:
        row = None

    if row is None:
        return fallback()

    return {
        "qty": int(row[0] or 0),
        "wt": row[1] if row[1] is not None else Decimal("0.000"),
    }