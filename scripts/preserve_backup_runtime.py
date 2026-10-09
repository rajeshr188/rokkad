"""Preserve one exact compatible runtime image outside hourly backup expiry.

Root-only operator. Streams docker save through gzip and age; no private key,
container restart, image deletion, or retention changes. Run once per release.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import publish_operational_backup as p


def encrypt_image(image_id, destination, recipient):
    with destination.open('xb') as output:
        saver = subprocess.Popen(['docker','save',image_id],stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL)
        encryptor = subprocess.Popen(['age','--encrypt','--recipient',recipient],
            stdin=subprocess.PIPE,stdout=output,stderr=subprocess.DEVNULL)
        try:
            with gzip.GzipFile(fileobj=encryptor.stdin,mode='wb',compresslevel=1,mtime=0) as compressed:
                shutil.copyfileobj(saver.stdout,compressed,1024*1024)
            saver.stdout.close()
            encryptor.stdin.close()
            if saver.wait(timeout=120) or encryptor.wait(timeout=120):
                raise ValueError('Runtime archive encryption failed')
        except BaseException:
            saver.kill(); encryptor.kill()
            saver.wait(); encryptor.wait()
            raise


def main():
    import fcntl
    import boto3
    from botocore.config import Config
    os.umask(0o077)
    if os.geteuid()!=0:
        raise ValueError('Root-only operator')
    config=p.load_config(p.CONFIG)
    live=json.loads(subprocess.check_output(['docker','inspect','rokkad-production-web-1']))[0]
    if not live['State']['Running']:
        raise ValueError('A running compatible application is required')
    image_id=live['Image']
    # image inspection also validates the exact immutable ID exists on this host.
    details=json.loads(subprocess.check_output(['docker','image','inspect',image_id]))[0]
    if details['Id']!=image_id:
        raise ValueError('Runtime identity mismatch')
    work=p.ROOT/'backups/off-server'
    if not work.is_dir() or work.is_symlink() or work.resolve()!=work:
        raise ValueError('Expected existing private backup staging')
    client=boto3.client('s3',endpoint_url=config['endpoint'],region_name='auto',
        aws_access_key_id=config['access_key_id'],aws_secret_access_key=config['secret_access_key'],
        config=Config(connect_timeout=15,read_timeout=120,retries={'max_attempts':3},
                      request_checksum_calculation='when_required',response_checksum_validation='when_required'))
    base=p.RELEASE_PREFIX+image_id.removeprefix('sha256:')+'/'+hashlib.sha256(config['recipient'].encode()).hexdigest()+'/'
    expected={'profile':'rokkad-encrypted-runtime/1','runtime_image':image_id,
              'recipient':config['recipient'],'ordinary_expiry':False}
    with (p.ROOT/'backups/operational/.backup.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if shutil.disk_usage(work).free-2*details['Size']-128*1024**2<5*1024**3:
            raise ValueError('Insufficient guarded runtime staging capacity')
        with tempfile.TemporaryDirectory(prefix='runtime-',dir=work) as temporary:
            folder=Path(temporary)
            marker=p.existing_completion(client,base+'complete.json')
            if marker is None:
                artifact=folder/'runtime.tar.gz.age'
                encrypt_image(image_id,artifact,config['recipient'])
                if artifact.stat().st_size>4*1024**3:
                    raise ValueError('Runtime exceeds supported single-object limit')
                digest=p.sha256(artifact)
                key=base+digest+'.tar.gz.age'
                with artifact.open('rb') as data:
                    client.put_object(Bucket=p.BUCKET,Key=key,Body=data,
                        ContentLength=artifact.stat().st_size,ContentType='application/octet-stream')
                marker={**expected,'artifact_key':key,'artifact_sha256':digest,
                        'artifact_bytes':artifact.stat().st_size}
                p.download_verified(client,key,folder/'verified.age',digest,marker['artifact_bytes'],prefix=p.RELEASE_PREFIX)
                client.put_object(Bucket=p.BUCKET,Key=base+'complete.json',Body=p.encoded(marker),ContentType='application/json',IfNoneMatch='*')
                if p.existing_completion(client,base+'complete.json')!=marker:
                    raise ValueError('Runtime completion readback mismatch')
            else:
                if any(marker.get(k)!=v for k,v in expected.items()) or not marker.get('artifact_key','').startswith(base):
                    raise ValueError('Runtime completion belongs to different evidence')
                p.download_verified(client,marker['artifact_key'],folder/'verified.age',marker['artifact_sha256'],marker['artifact_bytes'],prefix=p.RELEASE_PREFIX)
        partial=work/'.runtime-last.partial'
        partial.write_bytes(p.encoded(marker))
        partial.replace(work/'runtime-last.json')
    print(json.dumps({'runtime_encrypted_remote_bytes_verified':True,
                      'runtime_image':image_id,'decrypted_load_accepted':False,
                      'local_retention_changed':False}))


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'runtime_encrypted_remote_bytes_verified':False,'error_type':type(error).__name__}))
        raise SystemExit(1)
