from dataclasses import dataclass
from typing import Any, Optional
import hashlib
import json


@dataclass(frozen=True)
class PostingContext:
    voucher: Any
    user_id: int
    doc: Optional[Any] = None
    tenant_id: Optional[int] = None


def compute_fingerprint(payload: Any, rule_version: str) -> str:
    """
    Deterministic hash from payload + rule version.
    """

    def default(obj):
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
        return str(obj)

    packed = json.dumps(
        {"rule_version": rule_version, "payload": payload},
        sort_keys=True,
        default=default,
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(packed).hexdigest()
