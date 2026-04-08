from dataclasses import dataclass, field as dc_field
from typing import Optional


@dataclass
class TransitionResult:
    """Returned by transition command execution."""

    success: bool
    level: str
    message: str
    payment: Optional[object] = dc_field(default=None)
    created: bool = False
