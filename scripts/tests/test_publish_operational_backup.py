"""Fictional artifacts only; real age roundtrip on the Linux operator host."""
from datetime import datetime,timezone,timedelta
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest

SCRIPTS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SCRIPTS))
spec=importlib.util.spec_from_file_location('publisher',SCRIPTS/'publish_operational_backup.py')
publisher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


class Missing(Exception):
    response={'Error':{'Code':'NoSuchKey'}}


class Store:
    def __init__(self):
        self.objects={}
        self.puts=[]
        self.corrupt=False
        self.denied=False
        self.fail_completion=False

    def get_object(self,*,Bucket,Key):
        assert Bucket==publisher.BUCKET
        if self.denied:
            raise PermissionError('denied')
        if Key not in self.objects:
            raise Missing()
        data=self.objects[Key]
        if self.corrupt and Key.endswith('.age'):
            data=b'x'+data[1:]
        return {'Body':io.BytesIO(data)}

    def put_object(self,*,Bucket,Key,Body,**kwargs):
        assert Bucket==publisher.BUCKET
        if Key.endswith('complete.json') and self.fail_completion:
            raise PermissionError('completion denied')
        if kwargs.get('IfNoneMatch')=='*' and Key in self.objects:
            raise FileExistsError('immutable completion')
        data=Body.read() if hasattr(Body,'read') else Body
        self.objects[Key]=data
        self.puts.append(Key)


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        self.now=datetime(2026,10,10,0,tzinfo=timezone.utc)
        self.dump=self.folder/'production-20261010T000000Z.dump'
        self.dump.write_bytes(b'PGDMP fictional recovery facts')
        self.latest={'created_utc':'20261010T000000Z','file':str(self.dump),
                     'sha256':publisher.sha256(self.dump),'size_bytes':self.dump.stat().st_size,
                     'archive_catalog_checked':True}
        self.dump.with_suffix('.dump.sha256').write_text(self.latest['sha256']+'  '+self.dump.name)
        (self.folder/'latest.json').write_text(json.dumps(self.latest))
        self.config={'bucket':publisher.BUCKET,'endpoint':'https://'+'a'*32+'.r2.cloudflarestorage.com',
                     'access_key_id':'fictional-backup-id','secret_access_key':'fictional-backup-secret',
                     'recipient':'age1'+'q'*58}
        self.image='sha256:'+'b'*64
        self.store=Store()

    def encrypt(self,dump,package,destination,recipient):
        destination.write_bytes(b'fictional ciphertext '+dump.read_bytes())

    def publish(self,encrypt=None):
        work=self.folder/('work-'+str(len(list(self.folder.glob('work-*')))))
        work.mkdir()
        return publisher.publish(self.store,self.dump,self.latest,{'recovery.json':b'{}'},
                                 self.image,self.config,work,encrypt or self.encrypt)

    def test_fresh_validated_dump_and_catalogue(self):
        checked=[]
        publisher.validate_latest(self.folder,self.now,checked.append)
        self.assertEqual(checked,[self.dump])

    def test_stale_checksum_and_incomplete_metadata_refused(self):
        for field,value in [('sha256','0'*64),('size_bytes',1),('archive_catalog_checked',False),
                            ('created_utc','20261009T000000Z')]:
            with self.subTest(field=field):
                data={**self.latest,field:value}
                (self.folder/'latest.json').write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    publisher.validate_latest(self.folder,self.now,lambda p:None)
        (self.folder/'latest.json').write_text(json.dumps(self.latest))
        with self.assertRaises(ValueError):
            publisher.validate_latest(self.folder,self.now+timedelta(hours=3),lambda p:None)
        self.dump.write_bytes(b'damaged')
        with self.assertRaises(ValueError):
            publisher.validate_latest(self.folder,self.now,lambda p:None)

    def test_media_bucket_foreign_endpoint_private_identity_and_extra_config_refused(self):
        for field,value in [('bucket','rokkad-production-media'),('endpoint','https://example.com'),
                            ('recipient','AGE-SECRET-KEY-1FICTIONAL'),('unknown','bypass')]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                publisher.validate_config({**self.config,field:value})

    def test_publish_orders_verified_artifact_before_completion_and_idempotent_retry(self):
        marker=self.publish()
        self.assertTrue(self.store.puts[0].endswith('.age'))
        self.assertTrue(self.store.puts[1].endswith('complete.json'))
        self.assertNotIn(self.config['secret_access_key'],json.dumps(marker))
        self.assertEqual(self.publish(),marker)
        self.assertEqual(len(self.store.puts),2)

    def test_corrupt_download_never_publishes_completion(self):
        self.store.corrupt=True
        with self.assertRaises(ValueError):
            self.publish()
        self.assertFalse(any(k.endswith('complete.json') for k in self.store.objects))
        self.assertTrue(self.dump.exists())

    def test_failed_upload_completion_has_no_local_or_retention_side_effect(self):
        self.store.fail_completion=True
        with self.assertRaises(PermissionError):
            self.publish()
        self.assertTrue(self.dump.exists())
        self.assertFalse(any(k.endswith('complete.json') for k in self.store.objects))
        self.assertFalse((self.folder/'remote-last.json').exists())

    def test_denied_lookup_does_not_become_fresh_upload(self):
        self.store.denied=True
        with self.assertRaises(PermissionError):
            self.publish()
        self.assertEqual(self.store.puts,[])

    def test_changed_source_refuses_upload(self):
        def changed(dump,package,destination,recipient):
            self.encrypt(dump,package,destination,recipient)
            dump.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.publish(changed)
        self.assertEqual(self.store.puts,[])

    def test_existing_completion_mismatch_or_corruption_refuses_retry(self):
        marker=self.publish()
        key=self.store.puts[-1]
        self.store.objects[key]=publisher.encoded({**marker,'dump_bytes':1})
        with self.assertRaises(ValueError):
            self.publish()
        self.store.objects[key]=publisher.encoded(marker)
        self.store.corrupt=True
        with self.assertRaises(ValueError):
            self.publish()
        self.assertEqual(len(self.store.puts),2)

    def test_out_of_scope_artifact_size_and_path_refused(self):
        marker=self.publish()
        key=self.store.puts[-1]
        for field,value in [('artifact_key','media/customer-photo'),('artifact_bytes',0),
                            ('artifact_sha256','not-a-checksum')]:
            with self.subTest(field=field):
                self.store.objects[key]=publisher.encoded({**marker,field:value})
                with self.assertRaises(ValueError):
                    self.publish()

    def test_release_artifacts_require_explicit_fixed_recovery_scope(self):
        key=publisher.RELEASE_PREFIX+'fictional/runtime.age'
        data=b'fictional encrypted runtime'
        self.store.objects[key]=data
        digest=hashlib.sha256(data).hexdigest()
        with self.assertRaises(ValueError):
            publisher.download_verified(self.store,key,self.folder/'wrong.age',digest,len(data))
        with self.assertRaises(ValueError):
            publisher.download_verified(self.store,key,self.folder/'wrong.age',digest,len(data),prefix='releases/')
        publisher.download_verified(self.store,key,self.folder/'right.age',digest,len(data),prefix=publisher.RELEASE_PREFIX)
        self.assertEqual((self.folder/'right.age').read_bytes(),data)

    @unittest.skipUnless(shutil.which('age') and shutil.which('age-keygen'),'Linux age integration required')
    def test_real_age_tar_roundtrip_wrong_key_and_tampered_ciphertext(self):
        identity=self.folder/'test-identity.txt'
        subprocess.run(['age-keygen','-o',str(identity)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        recipient=subprocess.check_output(['age-keygen','-y',str(identity)],text=True).strip()
        package=self.folder/'real.tar.age'
        publisher.encrypt_package(self.dump,{'recovery.json':b'{}','runtime.env':b'TEST=fake\n'},package,recipient)
        restored=self.folder/'restored.tar'
        subprocess.run(['age','--decrypt','--identity',str(identity),'--output',str(restored),str(package)],check=True,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        with tarfile.open(restored) as archive:
            self.assertEqual(set(archive.getnames()),{'database.dump','recovery.json','runtime.env'})
            self.assertEqual(archive.extractfile('database.dump').read(),self.dump.read_bytes())
        wrong=self.folder/'wrong-identity.txt'
        subprocess.run(['age-keygen','-o',str(wrong)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        bad=self.folder/'bad-output'
        self.assertNotEqual(subprocess.run(['age','--decrypt','-i',str(wrong),'-o',str(bad),str(package)],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode,0)
        data=bytearray(package.read_bytes());data[-1]^=1;package.write_bytes(data)
        self.assertNotEqual(subprocess.run(['age','--decrypt','-i',str(identity),'-o',str(bad),str(package)],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode,0)


if __name__=='__main__':
    unittest.main()
