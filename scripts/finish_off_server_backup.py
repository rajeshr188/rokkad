"""Accepted hourly R2 completion and conservative remote/local retention.

Dry run unless --apply. Only recognized completed operational artifacts expire.
Release images, orphan objects and local backups without retained remote coverage
are protected. Requires root-only actual restore/image/key-custody acceptance.
"""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import publish_operational_backup as p
import retain_operational_backups as local

ACCEPTANCE=Path('/etc/rokkad/backup-acceptance.json')
POLICY='remote-24-hourly-30-UTC-daily-local-6-plus-uncovered/1'


def load_acceptance(path,config,image_id):
    info=path.stat()
    if path.is_symlink() or info.st_uid!=0 or info.st_mode & 0o077:
        raise ValueError('Acceptance must be a private root-owned operator file')
    accepted=json.loads(path.read_text())
    if (accepted.get('policy')!=POLICY or accepted.get('recipient')!=config['recipient']
            or accepted.get('runtime_image')!=image_id
            or any(accepted.get(k) is not True for k in (
                'actual_database_restore','exact_runtime_image_recovery',
                'owner_password_manager_copy','owner_offline_copy','retention_selected'))):
        raise ValueError('Actual recovery/custody/policy acceptance is required for this recipient and image')
    return accepted


def head_fingerprint(client,key,size):
    response=client.head_object(Bucket=p.BUCKET,Key=key)
    if response['ContentLength']!=size or not response.get('ETag'):
        raise ValueError('Remote artifact is absent or changed')
    # ETag is used only to detect changes, never as a SHA-256 verification.
    return response['ContentLength'],response['ETag'],response.get('LastModified')


def plan_remote(client,config,now):
    records=[]
    recipient_hash=hashlib.sha256(config['recipient'].encode()).hexdigest()
    expression=re.compile(re.escape(p.PREFIX)+r'(\d{8}T\d{6}Z)/([0-9a-f]{64})/([0-9a-f]{64})/([0-9a-f]{64})/complete\.json\Z')
    for page in client.get_paginator('list_objects_v2').paginate(Bucket=p.BUCKET,Prefix=p.PREFIX):
        for entry in page.get('Contents',[]):
            key=entry['Key']
            if not key.endswith('/complete.json'):
                continue # Orphans and unknown objects have no expiry authority.
            match=expression.fullmatch(key)
            if not match:
                raise ValueError('Unrecognized operational completion path')
            if match[3]!=recipient_hash:
                continue # Other keys/recipients need their own custody review.
            marker=p.existing_completion(client,key)
            if not isinstance(marker,dict):
                raise ValueError('Listed completion is missing')
            stamp=datetime.strptime(match[1],'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
            base=key.removesuffix('complete.json')
            if (stamp>now+timedelta(minutes=5) or marker.get('profile')!=p.PROFILE
                    or marker.get('created_utc')!=match[1] or marker.get('dump_sha256')!=match[2]
                    or marker.get('recipient')!=config['recipient']
                    or marker.get('runtime_image')!='sha256:'+match[4]
                    or type(marker.get('dump_bytes')) is not int or marker['dump_bytes']<=0
                    or type(marker.get('artifact_bytes')) is not int or marker['artifact_bytes']<=0
                    or not re.fullmatch(r'[0-9a-f]{64}',marker.get('artifact_sha256',''))
                    or not re.fullmatch(re.escape(base)+r'[0-9a-f]{32}\.tar\.age',marker.get('artifact_key',''))):
                raise ValueError('Remote completion is inconsistent with its exact artifact scope')
            verified=datetime.fromisoformat(marker['verified_at'])
            if verified.tzinfo is None or verified>now+timedelta(minutes=5) or verified<stamp-timedelta(minutes=5):
                raise ValueError('Invalid remote verification time')
            head=head_fingerprint(client,marker['artifact_key'],marker['artifact_bytes'])
            records.append({'key':key,'marker':marker,'stamp':stamp,'head':head})
    records.sort(key=lambda row:(row['stamp'],row['key']))
    if not records or now-records[-1]['stamp']>timedelta(minutes=120):
        raise ValueError('A fresh completed remote backup is required before expiry')
    retained={row['key'] for row in records[-24:]}
    daily={}
    first=now.date()-timedelta(days=29)
    for row in records:
        if first<=row['stamp'].date()<=now.date():
            daily[row['stamp'].date()]=row['key']
    retained.update(daily.values())
    return {'records':records,'retained':retained,'removed':[row for row in records if row['key'] not in retained]}


def covered_local_plan(local_plan,remote_plan,check_catalogue=local.catalogue):
    coverage={}
    for row in remote_plan['records']:
        if row['key'] in remote_plan['retained']:
            marker=row['marker']
            coverage[(marker['created_utc'],marker['dump_sha256'],marker['dump_bytes'])]=row
    keep=set(local_plan['copies'][-6:]);uncovered=set();removed=[];covered={}
    for path in local_plan['copies']:
        stamp=local.NAME.fullmatch(path.name)[1]
        binding=(stamp,local_plan['digests'][path],local_plan['fingerprints'][path][2])
        row=coverage.get(binding)
        if row is None:
            keep.add(path);uncovered.add(path)
        elif path not in keep:
            removed.append(path);covered[path]=row
    for path in sorted(keep):
        check_catalogue(path)
    return {**local_plan,'retained':keep,'removed':removed,'uncovered':uncovered,'coverage':covered}


def recheck_remote(client,plan):
    # Validate every completion and artifact before the first expiry action.
    for row in plan['records']:
        if (p.existing_completion(client,row['key'])!=row['marker']
                or head_fingerprint(client,row['marker']['artifact_key'],row['marker']['artifact_bytes'])!=row['head']):
            raise ValueError('Remote evidence changed; expiry refused')


def apply_remote(client,plan):
    recheck_remote(client,plan)
    for row in plan['removed']:
        # Marker first: an interrupted artifact deletion leaves a protected orphan,
        # never a false completed restore point with missing encrypted bytes.
        client.delete_object(Bucket=p.BUCKET,Key=row['key'])
        client.delete_object(Bucket=p.BUCKET,Key=row['marker']['artifact_key'])


def main():
    import fcntl
    import boto3
    from botocore.config import Config
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    os.umask(0o077)
    if os.geteuid()!=0:
        raise ValueError('Root-only operator')
    config=p.load_config(p.CONFIG)
    live=json.loads(subprocess.check_output(['docker','inspect','rokkad-production-web-1']))[0]
    if not live['State']['Running']:
        raise ValueError('A running accepted runtime is required')
    load_acceptance(ACCEPTANCE,config,live['Image'])
    if args.apply:
        # A failed publication stops both remote and local expiry.
        subprocess.run(['python3',str(Path(__file__).with_name('publish_operational_backup.py'))],check=True)
    folder=local.FOLDER
    if folder.resolve()!=folder or any(path.is_symlink() for path in (folder,*folder.parents)):
        raise ValueError('Unexpected fixed operational directory')
    local.regular(folder/'.backup.lock',folder)
    client=boto3.client('s3',endpoint_url=config['endpoint'],region_name='auto',
        aws_access_key_id=config['access_key_id'],aws_secret_access_key=config['secret_access_key'],
        config=Config(connect_timeout=15,read_timeout=120,retries={'max_attempts':3},
                      request_checksum_calculation='when_required',response_checksum_validation='when_required'))
    with (folder/'.backup.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        now=datetime.now(timezone.utc)
        original=local.plan_retention(folder,now)
        remote=plan_remote(client,config,now)
        local_plan=covered_local_plan(original,remote)
        latest=json.loads((folder/'latest.json').read_text())
        matching=[row for row in remote['records'] if row['key'] in remote['retained']
                  and row['marker']['created_utc']==latest['created_utc']
                  and row['marker']['dump_sha256']==latest['sha256']
                  and row['marker']['dump_bytes']==latest['size_bytes']
                  and row['marker']['runtime_image']==live['Image']]
        if not matching:
            raise ValueError('Newest local snapshot lacks exact accepted retained remote coverage')
        work=p.ROOT/'backups/off-server'
        if work.is_symlink() or work.resolve()!=work:
            raise ValueError('Unexpected private verification directory')
        if shutil.disk_usage(work).free-2*latest['size_bytes']-128*1024**2<5*1024**3:
            raise ValueError('Insufficient guarded download verification capacity')
        with tempfile.TemporaryDirectory(prefix='retention-',dir=work) as temporary:
            verify=[matching[-1],*local_plan['coverage'].values()]
            unique={row['key']:row for row in verify}
            for index,row in enumerate(unique.values()):
                marker=row['marker']
                downloaded=Path(temporary)/(str(index)+'.age')
                p.download_verified(client,marker['artifact_key'],downloaded,marker['artifact_sha256'],marker['artifact_bytes'])
                downloaded.unlink()
        report={'checked_at':now.isoformat(),'policy':POLICY,'apply':args.apply,
                'remote_total':len(remote['records']),'remote_retained':len(remote['retained']),
                'remote_expired':len(remote['removed']),'local_total':len(local_plan['copies']),
                'local_retained':len(local_plan['retained']),'local_uncovered_protected':len(local_plan['uncovered']),
                'local_expired':len(local_plan['removed']),'latest':original['latest'].name,
                'latest_remote_download_verified':True,'local_expiry_remote_bytes_verified':True,
                'release_checkpoints_and_orphans_protected':True,'actual_recovery_accepted':True}
        audit=p.ROOT/'backups/off-server/retention-audit.jsonl'
        with audit.open('a') as log:
            log.write(json.dumps({**report,'phase':'validated',
                'remote_expiry_keys':[row['key'] for row in remote['removed']],
                'local_expiry_names':[path.name for path in local_plan['removed']]})+'\n')
            log.flush();os.fsync(log.fileno())
        if args.apply:
            # Recheck local fingerprints before remote changes as well as unlink.
            for path,fingerprint in original['fingerprints'].items():
                if local.regular(path,folder)!=fingerprint:
                    raise ValueError('Local evidence changed; all expiry refused')
            apply_remote(client,remote)
            # Covered candidates belong only to the retained remote set.
            recheck_remote(client,{'records':[row for row in remote['records'] if row['key'] in remote['retained']]})
            local.apply_plan(folder,local_plan)
        report['free_bytes']=shutil.disk_usage(folder).free
        report['low_space']=report['free_bytes']<8*1024**3
        with audit.open('a') as log:
            log.write(json.dumps({**report,'phase':'completed'})+'\n')
        partial=work/'.retention-last.partial'
        partial.write_bytes(p.encoded(report));partial.replace(work/'retention-last.json')
        print(json.dumps(report))


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'off_server_completion':False,'error_type':type(error).__name__,
                          'local_expiry_permitted':False}))
        raise SystemExit(1)
