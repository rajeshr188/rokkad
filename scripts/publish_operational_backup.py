"""Encrypt and verify one completed backup in the dedicated private R2 bucket.

Host-only operator. No Django, database writes, expiry, or private decryption key.
The existing dump service and retention stay unchanged until restore acceptance.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
import uuid

from retain_operational_backups import NAME, regular, catalogue

ROOT = Path('/home/rokkad/deploy/cutover-20260924')
BUCKET = 'rokkad-production-backups'
PREFIX = 'operational/v1/'
RELEASE_PREFIX = 'releases/v1/'
PROFILE = 'rokkad-encrypted-recovery/1'
CONFIG = Path('/etc/rokkad/backup-r2.json')


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'))+'\n').encode()


def validate_config(config):
    required = {'bucket','endpoint','access_key_id','secret_access_key','recipient'}
    if set(config) != required or any(not isinstance(config[k], str) or not config[k] for k in required):
        raise ValueError('Dedicated backup configuration is incomplete')
    if config['bucket'] != BUCKET:
        raise ValueError('Only the dedicated private backup bucket is supported')
    if not re.fullmatch(r'https://[0-9a-f]{32}\.r2\.cloudflarestorage\.com', config['endpoint']):
        raise ValueError('Expected the account R2 HTTPS endpoint')
    if not re.fullmatch(r'age1[023456789acdefghjklmnpqrstuvwxyz]{58}',config['recipient']):
        raise ValueError('An age X25519 public recipient is required, never a private key')
    return config


def load_config(path):
    info = path.stat()
    if path.is_symlink() or not stat.S_ISREG(info.st_mode):
        raise ValueError('Configuration must be a regular private file')
    if os.name == 'posix' and (info.st_uid != 0 or info.st_mode & 0o077):
        raise ValueError('Configuration must be root-owned and mode 0600')
    return validate_config(json.loads(path.read_text()))


def validate_latest(folder, now, check_catalogue=catalogue):
    latest = json.loads((folder/'latest.json').read_text())
    path = Path(latest['file'])
    fingerprint = regular(path, folder)
    match = NAME.fullmatch(path.name)
    if not match or not fingerprint[2]:
        raise ValueError('Expected a completed operational dump')
    stamp = datetime.strptime(match[1],'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
    if stamp > now+timedelta(minutes=5) or now-stamp > timedelta(minutes=120):
        raise ValueError('A fresh completed backup is required')
    sidecar = path.with_suffix('.dump.sha256')
    regular(sidecar,folder)
    digest = sha256(path)
    if (latest.get('created_utc') != match[1] or latest.get('sha256') != digest
            or latest.get('size_bytes') != fingerprint[2]
            or latest.get('archive_catalog_checked') is not True
            or sidecar.read_text().split()[0] != digest):
        raise ValueError('Backup checksum or completion metadata does not match')
    check_catalogue(path)
    if regular(path,folder) != fingerprint:
        raise ValueError('Backup changed during validation')
    return path, latest, fingerprint


def encrypt_package(dump, deployment, destination, recipient, age_binary='age'):
    """Stream a fixed package to age; no second plaintext database dump is written."""
    with destination.open('xb') as ciphertext:
        process = subprocess.Popen([age_binary,'--encrypt','--recipient',recipient],
                                   stdin=subprocess.PIPE,stdout=ciphertext,stderr=subprocess.DEVNULL)
        try:
            with tarfile.open(fileobj=process.stdin, mode='w|') as package:
                info = tarfile.TarInfo('database.dump')
                info.size = dump.stat().st_size
                info.mode = 0o600
                with dump.open('rb') as source:
                    package.addfile(info, source)
                for name, data in deployment.items():
                    if name not in {'recovery.json','runtime.env','production_settings.py',
                                    'production-compose.yml','production-release.json'}:
                        raise ValueError('Unrecognized recovery package member')
                    info = tarfile.TarInfo(name)
                    info.mode = 0o600
                    info.size = len(data)
                    package.addfile(info, io.BytesIO(data))
            process.stdin.close()
            if process.wait(timeout=120):
                raise ValueError('Backup encryption failed')
        except BaseException:
            process.kill()
            process.wait()
            raise
    with destination.open('rb') as incoming:
        if incoming.read(len(b'age-encryption.org/v1\n')) != b'age-encryption.org/v1\n':
            raise ValueError('Expected an encrypted age artifact')


def download_verified(client, key, destination, digest, size, *, prefix=PREFIX):
    if (prefix not in (PREFIX, RELEASE_PREFIX) or not key.startswith(prefix)
            or not re.fullmatch(r'[0-9a-f]{64}',digest) or type(size) is not int or size <= 0):
        raise ValueError('Invalid remote artifact evidence')
    response = client.get_object(Bucket=BUCKET,Key=key)
    stream = response['Body']
    total = 0
    hashed = hashlib.sha256()
    try:
        with destination.open('xb') as target:
            while chunk := stream.read(1024*1024):
                total += len(chunk)
                if total > size:
                    raise ValueError('Remote artifact exceeds its accepted size')
                target.write(chunk)
                hashed.update(chunk)
    finally:
        stream.close()
    if total != size or hashed.hexdigest() != digest:
        raise ValueError('Remote artifact checksum or size does not match')


def existing_completion(client, key):
    try:
        response = client.get_object(Bucket=BUCKET,Key=key)
    except Exception as error:
        # Only actual absence permits a fresh publication; access/network failures do not.
        code = getattr(error,'response',{}).get('Error',{}).get('Code')
        if code in ('NoSuchKey','404'):
            return None
        raise
    stream = response['Body']
    try:
        raw = stream.read(65537)
    finally:
        stream.close()
    if len(raw)>65536:
        raise ValueError('Remote completion record is oversized')
    return json.loads(raw)


def publish(client, dump, latest, deployment, image_id, config, staging,
            encrypt=encrypt_package):
    """Completion is published only after verifying downloaded encrypted bytes."""
    recipient_id = hashlib.sha256(config['recipient'].encode()).hexdigest()
    image_match = re.fullmatch(r'sha256:([0-9a-f]{64})',image_id)
    if not image_match:
        raise ValueError('An exact compatible runtime image is required')
    base = PREFIX+latest['created_utc']+'/'+latest['sha256']+'/'+recipient_id+'/'+image_match[1]+'/'
    marker_key = base+'complete.json'
    expected = {'profile':PROFILE,'created_utc':latest['created_utc'],
                'dump_sha256':latest['sha256'],'dump_bytes':latest['size_bytes'],
                'recipient':config['recipient'],'runtime_image':image_id}
    existing = existing_completion(client,marker_key)
    if existing is not None:
        if any(existing.get(k)!=v for k,v in expected.items()):
            raise ValueError('Existing completion belongs to different recovery evidence')
        if not existing.get('artifact_key','').startswith(base):
            raise ValueError('Existing artifact is outside its exact completion scope')
        download_verified(client,existing['artifact_key'],staging/'verified.age',
                          existing['artifact_sha256'],existing['artifact_bytes'])
        return existing
    ciphertext = staging/'recovery.tar.age'
    encrypt(dump,deployment,ciphertext,config['recipient'])
    if sha256(dump) != latest['sha256'] or dump.stat().st_size != latest['size_bytes']:
        raise ValueError('Source backup changed during encryption; upload refused')
    artifact_key = base+uuid.uuid4().hex+'.tar.age'
    digest = sha256(ciphertext)
    size = ciphertext.stat().st_size
    # Current archives are ~157 MiB. Refuse files requiring a new multipart workflow.
    if size > 4*1024**3:
        raise ValueError('Archive exceeds the supported single-object size')
    with ciphertext.open('rb') as body:
        client.put_object(Bucket=BUCKET,Key=artifact_key,Body=body,
                          ContentLength=size,ContentType='application/octet-stream')
    download_verified(client,artifact_key,staging/'verified.age',digest,size)
    marker = {**expected,'artifact_key':artifact_key,'artifact_sha256':digest,
              'artifact_bytes':size,'verified_at':datetime.now(timezone.utc).isoformat()}
    client.put_object(Bucket=BUCKET,Key=marker_key,Body=encoded(marker),
                      ContentType='application/json',IfNoneMatch='*')
    if existing_completion(client,marker_key) != marker:
        raise ValueError('Remote completion readback does not match')
    return marker


def capture_deployment(latest, config):
    live = json.loads(subprocess.check_output(['docker','inspect','rokkad-production-web-1']))[0]
    if not live['State']['Running']:
        raise ValueError('A running compatible application is required')
    stamp = datetime.strptime(latest['created_utc'],'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)
    started = datetime.fromisoformat(live['State']['StartedAt'].replace('Z','+00:00'))
    if started > stamp:
        raise ValueError('Create a fresh backup after the latest application switch or restart')
    env = dict(x.split('=',1) for x in live['Config']['Env'])
    if config['access_key_id'] in env.values() or config['secret_access_key'] in env.values():
        raise ValueError('Dedicated backup credentials must not be application credentials')
    if env.get('DB_NAME') != 'rokkad_production_20260924' or env.get('DB_USER') != 'rokkad_prod_runtime':
        raise ValueError('Unexpected production database or runtime role')
    if any(k.startswith('DB_MIGRATION_') and value for k,value in env.items()):
        raise ValueError('Owner credentials must not be present in the application')
    if any('\n' in k+v or '\r' in k+v for k,v in env.items()):
        raise ValueError('Runtime environment needs an explicit multiline recovery format')
    package = {name:(ROOT/name).read_bytes() for name in (
        'production_settings.py','production-compose.yml','production-release.json')}
    package['runtime.env'] = ''.join(k+'='+v+'\n' for k,v in sorted(env.items())).encode()
    metadata = {'profile':PROFILE,'database':env['DB_NAME'],'runtime_role':env['DB_USER'],
                'runtime_image':live['Image'],'backup':latest,
                'configuration_sha256':{k:hashlib.sha256(v).hexdigest() for k,v in package.items()},
                'image_availability':'Retained on host; independently recoverable image/source must be verified before retention activation',
                'restore':'Owner-only isolated database, then restricted runtime checks; never production'}
    package['recovery.json']=encoded(metadata)
    return live['Image'], package


def main():
    import fcntl
    import boto3
    from botocore.config import Config

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=CONFIG)
    args=parser.parse_args()
    os.umask(0o077)
    if os.geteuid()!=0:
        raise ValueError('The backup operator requires root-owned host configuration')
    config=load_config(args.config)
    folder=ROOT/'backups/operational'
    if folder.resolve()!=folder or any(p.is_symlink() for p in (folder,*folder.parents)):
        raise ValueError('Unexpected operational backup directory')
    regular(folder/'.backup.lock',folder)
    with (folder/'.backup.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        dump,latest,_ = validate_latest(folder,datetime.now(timezone.utc))
        if shutil.disk_usage(folder).free-2*dump.stat().st_size-128*1024**2 < 5*1024**3:
            raise ValueError('Insufficient guarded space for encryption and download verification')
        image_id,deployment=capture_deployment(latest,config)
        work=ROOT/'backups/off-server'
        work.mkdir(mode=0o700,exist_ok=True)
        if work.is_symlink() or work.resolve()!=work:
            raise ValueError('Unexpected private staging directory')
        client=boto3.client('s3',endpoint_url=config['endpoint'],region_name='auto',
            aws_access_key_id=config['access_key_id'],aws_secret_access_key=config['secret_access_key'],
            config=Config(connect_timeout=15,read_timeout=120,retries={'max_attempts':3},
                          request_checksum_calculation='when_required',response_checksum_validation='when_required'))
        with tempfile.TemporaryDirectory(prefix='publish-',dir=work) as temporary:
            marker=publish(client,dump,latest,deployment,image_id,config,Path(temporary))
        # This is upload acceptance only, never a retention/restore acceptance flag.
        report={**marker,'bucket':BUCKET,'download_checksum_verified':True,
                'actual_restore_accepted':False,'local_retention_changed':False}
        partial=work/'.remote-last.partial'
        partial.write_bytes(encoded(report))
        partial.replace(work/'remote-last.json')
        print(json.dumps({'remote_backup_verified':True,'actual_restore_accepted':False,
                          'local_retention_changed':False,'created_utc':latest['created_utc']}))


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        # Provider exceptions may contain URLs or credentials; never emit them to journals.
        print(json.dumps({'remote_backup_verified':False,'error_type':type(error).__name__,
                          'local_retention_changed':False}))
        raise SystemExit(1)
