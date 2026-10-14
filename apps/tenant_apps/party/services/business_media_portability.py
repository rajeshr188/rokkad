"""Customer files and register codes accompanying a reviewed fresh transfer."""
from uuid import UUID
from django.core.exceptions import ValidationError
from apps.tenant_apps.party.models import Party, PartyDocument, PartyPhoto


def export_customers(*, workspace_id, identities, child_identities, save_file):
    records = []
    for party in Party.objects.filter(workspace_id=workspace_id).order_by('pk').iterator():
        photos = [dict(id=obj.pk, file=save_file(obj.file)['sha256'], created_at=obj.created_at.isoformat())
            for obj in party.photos.order_by('pk')]
        documents = []
        for obj in party.documents.order_by('pk'):
            documents.append(dict(id=obj.pk, document_type=obj.document_type, title=obj.title,
                file=save_file(obj.file)['sha256'] if obj.file.name else '',
                identifier=child_identities.get(obj.identifier_id) if obj.identifier_id else None,
                source_is_verified=obj.is_verified, source_verified_at=obj.verified_at.isoformat() if obj.verified_at else None,
                expires_on=obj.expires_on.isoformat() if obj.expires_on else None, metadata=obj.metadata))
            if obj.identifier_id and not documents[-1]['identifier']:
                raise ValidationError('Customer document lacks its exported identifier identity.')
        records.append(dict(id=str(identities[party.pk]), code=party.party_code, metadata=party.metadata,
            profile=save_file(party.profile_photo)['sha256'] if party.profile_photo.name else '',
            photos=photos, documents=documents))
    return records


def restore_customer(*, workspace_id, actor, record, party, identifiers, load_file, save_file):
    if party.workspace_id != workspace_id or set(record) != {'id','code','metadata','profile','photos','documents'}:
        raise ValidationError('Customer media scope or fields differ.')
    UUID(record['id'])
    party.party_code, party.metadata = record['code'], record['metadata']
    if record['profile']:
        save_file(party.profile_photo, load_file(record['profile']))
    party.full_clean()
    party.save(update_fields=['party_code','metadata','profile_photo'])
    for row in record['photos']:
        if set(row) != {'id','file','created_at'}:
            raise ValidationError('Invalid customer photograph fields.')
        obj = PartyPhoto(workspace_id=workspace_id, party=party, created_by=actor)
        save_file(obj.file, load_file(row['file']))
        obj.full_clean()
        obj.save()
    for row in record['documents']:
        if set(row) != {'id','document_type','title','file','identifier','source_is_verified','source_verified_at','expires_on','metadata'}:
            raise ValidationError('Invalid customer document fields.')
        identifier = identifiers.get(row['identifier']) if row['identifier'] else None
        if row['identifier'] and (identifier is None or identifier.party_id != party.pk):
            raise ValidationError('Customer document identifier differs.')
        metadata = dict(row['metadata'])
        metadata['package_source_verification'] = dict(is_verified=row['source_is_verified'], verified_at=row['source_verified_at'])
        obj = PartyDocument(workspace_id=workspace_id, party=party, identifier=identifier,
            document_type=row['document_type'], title=row['title'], expires_on=row['expires_on'],
            metadata=metadata, is_verified=False)
        if row['file']:
            save_file(obj.file, load_file(row['file']))
        obj.full_clean()
        obj.save()
