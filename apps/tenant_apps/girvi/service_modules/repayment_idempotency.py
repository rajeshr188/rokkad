import hashlib


def build_repayment_idempotency_marker(loan, payload, *, loan_kind="given"):
    supplied_key = (payload.get("idempotency_key") or "").strip()
    if supplied_key:
        key = supplied_key
    else:
        fingerprint = "|".join(
            str(payload.get(name, ""))
            for name in (
                "total_amount",
                "interest_amount",
                "principal_amount",
                "payment_date",
                "payment_method",
                "description",
                "is_final_payment",
            )
        )
        key = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:24]
    loan_pk = getattr(loan, "pk", None) or getattr(loan, "id", "")
    return f"REPAYMENT-{loan_kind.upper()}-{loan_pk}-{key}"
