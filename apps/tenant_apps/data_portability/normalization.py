"""Explicit, versioned source normalization, separate from column mapping."""
from .contracts import issue


def normalize(record, rules):
    result, issues = dict(record), []
    for rule in rules:
        key, operation = rule["field"], rule["rule"]
        before = result.get(key)
        if before is None:
            continue
        after = before
        if operation == "trim" and isinstance(before, str):
            after = before.strip()
        elif operation == "upper" and isinstance(before, str):
            after = before.upper()
        elif operation == "empty_to_null" and before == "":
            after = None
        elif operation == "boolean" and isinstance(before, str):
            if before not in {"true", "false"}:
                issues.append(issue("INVALID_BOOLEAN", key, "Use literal true or false."))
            else:
                after = before == "true"
        if before != after or type(before) is not type(after):
            result[key] = after
            issues.append(issue("NORMALIZED", key, f"Applied {operation} v1.", "INFO", before, after))
    return result, issues
