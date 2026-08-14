import re
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _


@dataclass(frozen=True)
class ProofDocumentValue:
    proof_type: str
    number: str

    VALIDATORS = {
        "AA": RegexValidator(regex=r"^\d{12}$", message=_("Aadhaar must be 12 digits")),
        "PN": RegexValidator(
            regex=r"^[A-Z]{5}[0-9]{4}[A-Z]$",
            message=_("PAN must be in format: ABCDE1234F"),
        ),
        "DL": RegexValidator(
            regex=r"^[A-Z]{2}[0-9]{13}$",
            message=_("Driving License format: TN1234567890123"),
        ),
    }

    @classmethod
    def from_raw(cls, proof_type, number):
        return cls(proof_type=proof_type, number=normalize_proof_number(proof_type, number))

    def validate(self):
        validator = self.VALIDATORS.get(self.proof_type)
        if not validator:
            return

        try:
            validator(self.number)
        except ValidationError as exc:
            raise ValidationError({"proof_number": exc.message})

    @property
    def masked_number(self):
        return mask_proof_number(self.proof_type, self.number)


def normalize_proof_number(proof_type, number):
    value = str(number or "").strip()

    if proof_type == "AA":
        return re.sub(r"\D", "", value)

    if proof_type in {"PN", "DL", "VI", "PP"}:
        return re.sub(r"\s+", "", value).upper()

    return value


def mask_proof_number(proof_type, number):
    normalized = normalize_proof_number(proof_type, number)

    if proof_type == "AA" and len(normalized) == 12:
        return f"XXXX-XXXX-{normalized[-4:]}"

    if proof_type == "PN" and len(normalized) == 10:
        return f"{normalized[:2]}XXX{normalized[5:9]}X"

    if len(normalized) <= 4:
        return normalized

    return f"{'*' * (len(normalized) - 4)}{normalized[-4:]}"


def find_duplicate_proofs(proof):
    from .models import Proof

    normalized = normalize_proof_number(proof.proof_type, proof.proof_number)
    queryset = Proof.objects.filter(
        proof_type=proof.proof_type,
        proof_number=normalized,
    )
    if proof.pk:
        queryset = queryset.exclude(pk=proof.pk)
    return queryset
