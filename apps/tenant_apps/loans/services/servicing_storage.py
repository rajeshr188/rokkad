"""Referenced physical locations and ordered movements for servicing version 3."""
from uuid import uuid5
from .servicing_bundle_contract import require


def validate_source_storage(document):
    tables = document['tables']
    locations = {row['id']:row for row in tables['PawnStorageLocation']}
    parents = {'BRANCH':None,'VAULT':'BRANCH','CABINET':'VAULT','BOX':'CABINET','SLOT':'BOX'}
    for row in locations.values():
        parent = locations.get(row['parent_id'])
        require((row['level']=='BRANCH' and row['parent_id'] is None)
            or (parent is not None and parent['level']==parents[row['level']] and parent['id']<row['id']),
            'Portable storage hierarchy is missing or out of order.')
    movements = {}
    for row in tables['PawnCollateralStorageMovement']:
        previous = movements.get(row['collateral_item_id'])
        expected = previous['to_location_id'] if previous else None
        require(row['from_location_id']==expected and row['from_location_id']!=row['to_location_id'],
            'Portable storage movement does not continue its original chain.')
        for key in ('from_location_id','to_location_id'):
            require(row[key] is None or locations[row[key]]['level'] in {'BOX','SLOT'},
                'Portable collateral storage requires a Box or Slot.')
        movements[row['collateral_item_id']]=row
    for item in tables['PawnCollateralItem']:
        last=movements.get(item['id'])
        require(item['current_storage_location_id']==(last['to_location_id'] if last else None),
            'Portable current physical location lacks its exact movement chain.')
        if item['custody_state']!='IN_VAULT':
            require(item['current_storage_location_id'] is None,
                'Collateral outside the vault cannot retain a physical vault location.')


def existing_location(workspace_id, namespace, source, values):
    """Shared source ancestors resolve by namespace identity, never by a name/code."""
    from apps.tenant_apps.loans.models import PawnStorageLocation
    values['public_id']=uuid5(namespace,f'portable-storage:{workspace_id}:{source["id"]}')
    existing = PawnStorageLocation.objects.filter(workspace_id=workspace_id,public_id=values['public_id']).first()
    if existing is not None:
        require(all(getattr(existing,key)==value for key,value in values.items()
            if key not in {'id','created_by_id'}),
            'Previously restored source storage configuration changed; review rather than overwrite it.')
    return existing
