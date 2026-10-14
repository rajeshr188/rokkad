"""Retain an imported quote's frozen source definition without redating its price."""
import json
from hashlib import sha256
from uuid import UUID
from django.core.exceptions import ValidationError

PROFILE = 'rate-source-transfer/1'


def snapshot_hash(snapshot):
    return sha256(json.dumps(snapshot,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()


def validate_source(evidence, *, snapshot):
    try:
        if (type(evidence) is not dict or set(evidence) != {'profile','namespace','source_id','snapshot','sha256'}
                or evidence['profile'] != PROFILE or str(UUID(evidence['namespace'])) != evidence['namespace']
                or type(evidence['source_id']) is not int or evidence['source_id']<=0
                or type(snapshot) is not dict or evidence['snapshot']!=snapshot
                or not {'name','location','tax_included'} <= set(snapshot)
                or any(type(snapshot[key]) is not str or len(snapshot[key])>30 for key in ('name','location'))
                or type(snapshot['tax_included']) is not bool
                or len(json.dumps(evidence))>65536 or evidence['sha256']!=snapshot_hash(snapshot)):
            raise ValueError
    except (KeyError,TypeError,ValueError,AttributeError,OverflowError,RecursionError):
        raise ValidationError('Imported quote source evidence is malformed or differs from its frozen snapshot.') from None


def source_evidence(*, namespace, row):
    if row.get('portable_source'):
        validate_source(row['portable_source'],snapshot=row['source_snapshot'])
        return row['portable_source']
    result=dict(profile=PROFILE,namespace=str(namespace),source_id=row['id'],
        snapshot=row['source_snapshot'],sha256=snapshot_hash(row['source_snapshot']))
    validate_source(result,snapshot=row['source_snapshot'])
    return result
