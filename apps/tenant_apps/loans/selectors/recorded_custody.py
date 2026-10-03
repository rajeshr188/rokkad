"""Retain original custody rows while projecting explicit paper fact revisions."""


def current_custody_history(item):
    rows = tuple(item.custody_history.all())
    superseded = {getattr(row, "restatement_of_id", None) for row in rows} - {None}
    if not superseded:
        return rows
    return tuple(sorted((row for row in rows if row.pk not in superseded), key=lambda row: (row.effective_date, row.pk)))
