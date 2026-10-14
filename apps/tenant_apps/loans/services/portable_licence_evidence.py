"""A source verification/attestation is history, not destination-owner consent."""
import json
from uuid import UUID
from django.core.exceptions import ValidationError

PROFILE = 'licence-source-transfer/1'
KINDS = {'INITIAL','AMENDMENT','RENEWAL','LEGACY_REFERENCE','VERIFICATION','ATTESTATION','IMPORTED_SOURCE'}


def validate_source(evidence):
    try:
        if (type(evidence) is not dict or set(evidence) != {'profile','namespace','source_id','source_kind','original_evidence'}
                or evidence['profile'] != PROFILE or str(UUID(evidence['namespace']))!=evidence['namespace']
                or type(evidence['source_id']) is not int or evidence['source_id']<=0
                or evidence['source_kind'] not in KINDS or type(evidence['original_evidence']) is not dict
                or len(json.dumps(evidence))>1048576):
            raise ValueError
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError,RecursionError):
        raise ValidationError('Imported licence source evidence is malformed.') from None


def source_evidence(*, namespace, row):
    if row['kind']=='IMPORTED_SOURCE':
        validate_source(row['verification_evidence'])
        return row['verification_evidence']
    result=dict(profile=PROFILE,namespace=str(namespace),source_id=row['id'],source_kind=row['kind'],
        original_evidence=row['verification_evidence'])
    validate_source(result)
    return result
