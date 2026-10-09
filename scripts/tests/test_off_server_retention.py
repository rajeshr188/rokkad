"""Destructive boundaries use fictional objects/files only."""
from datetime import datetime,timedelta,timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import finish_off_server_backup as finisher
from test_publish_operational_backup import Store,Missing


class RemoteStore(Store):
    def __init__(self):
        super().__init__()
        self.deleted=[]

    def get_paginator(self,name):
        assert name=='list_objects_v2'
        return self

    def paginate(self,*,Bucket,Prefix):
        if self.denied:raise PermissionError('denied')
        yield {'Contents':[{'Key':key} for key in sorted(self.objects) if key.startswith(Prefix)]}

    def head_object(self,*,Bucket,Key):
        if Key not in self.objects:raise Missing()
        data=self.objects[Key]
        return {'ContentLength':len(data),'ETag':hashlib.sha256(data).hexdigest()}

    def delete_object(self,*,Bucket,Key):
        self.deleted.append(Key)
        del self.objects[Key]


class RemoteRetentionTests(unittest.TestCase):
    def setUp(self):
        self.store=RemoteStore()
        self.now=datetime(2026,10,10,12,tzinfo=timezone.utc)
        self.recipient='age1'+'q'*58
        self.config={'recipient':self.recipient}

    def create(self,stamp,index=1,recipient=None):
        recipient=recipient or self.recipient
        created=stamp.strftime('%Y%m%dT%H%M%SZ')
        digest=hashlib.sha256(created.encode()).hexdigest()
        image='b'*64
        base=finisher.p.PREFIX+created+'/'+digest+'/'+hashlib.sha256(recipient.encode()).hexdigest()+'/'+image+'/'
        data=b'fictional encrypted backup '+created.encode()
        artifact=base+f'{index:032x}'+'.tar.age'
        marker={'profile':finisher.p.PROFILE,'created_utc':created,'dump_sha256':digest,
                'dump_bytes':100,'recipient':recipient,'runtime_image':'sha256:'+image,
                'artifact_key':artifact,'artifact_bytes':len(data),
                'artifact_sha256':hashlib.sha256(data).hexdigest(),'verified_at':stamp.isoformat()}
        self.store.objects[artifact]=data
        self.store.objects[base+'complete.json']=finisher.p.encoded(marker)
        return base+'complete.json',marker

    def plan(self):
        return finisher.plan_remote(self.store,self.config,self.now)

    def test_hourly_daily_union_and_exact_expiry_scope(self):
        for hour in range(35*24,-1,-1):self.create(self.now-timedelta(hours=hour))
        release=finisher.p.RELEASE_PREFIX+'protected.age'
        orphan=finisher.p.PREFIX+'orphan.age'
        self.store.objects[release]=self.store.objects[orphan]=b'protected'
        plan=self.plan()
        self.assertTrue({row['key'] for row in plan['records'][-24:]}<=plan['retained'])
        for day in range(30):
            date=self.now.date()-timedelta(days=day)
            newest=max(row['key'] for row in plan['records'] if row['stamp'].date()==date)
            self.assertIn(newest,plan['retained'])
        finisher.apply_remote(self.store,plan)
        self.assertEqual(self.store.objects[release],b'protected')
        self.assertEqual(self.store.objects[orphan],b'protected')
        self.assertEqual(self.store.deleted[0],plan['removed'][0]['key'])
        self.assertTrue(all(row['key'] in self.store.objects for row in plan['records'] if row['key'] in plan['retained']))

    def test_denied_future_stale_missing_and_corrupt_evidence_refuse_expiry(self):
        key,marker=self.create(self.now)
        for field,value in [('dump_sha256','0'*64),('artifact_key','media/photo'),
                            ('artifact_bytes',1),('verified_at','not-a-date')]:
            with self.subTest(field=field):
                self.store.objects[key]=finisher.p.encoded({**marker,field:value})
                with self.assertRaises((ValueError,Missing)):self.plan()
                self.assertEqual(self.store.deleted,[])
        self.store.objects[key]=finisher.p.encoded(marker)
        self.store.denied=True
        with self.assertRaises(PermissionError):self.plan()
        self.store.denied=False
        self.now+=timedelta(hours=3)
        with self.assertRaises(ValueError):self.plan()
        self.now-=timedelta(hours=4)
        with self.assertRaises(ValueError):self.plan()
        self.now+=timedelta(hours=1)
        del self.store.objects[marker['artifact_key']]
        with self.assertRaises(Missing):self.plan()
        self.assertEqual(self.store.deleted,[])

    def test_changed_remote_refuses_before_first_delete(self):
        self.create(self.now-timedelta(days=35))
        key,marker=self.create(self.now)
        plan=self.plan()
        self.store.objects[marker['artifact_key']]=b'changed'
        with self.assertRaises(ValueError):finisher.apply_remote(self.store,plan)
        self.assertEqual(self.store.deleted,[])

    def test_foreign_recipient_is_preserved(self):
        self.create(self.now)
        foreign,_=self.create(self.now-timedelta(days=35),recipient='age1'+'p'*58)
        plan=self.plan()
        finisher.apply_remote(self.store,plan)
        self.assertIn(foreign,self.store.objects)

    def test_local_six_plus_uncovered_and_binding_are_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            for hour in range(20,-1,-1):
                stamp=self.now-timedelta(hours=hour)
                path=folder/('production-'+stamp.strftime('%Y%m%dT%H%M%SZ')+'.dump')
                path.write_bytes(b'PGDMP fictional '+path.name.encode())
                digest=finisher.p.sha256(path)
                path.with_suffix('.dump.sha256').write_text(digest)
                (folder/'latest.json').write_bytes(finisher.p.encoded({'file':str(path),'sha256':digest,'size_bytes':path.stat().st_size,'archive_catalog_checked':True}))
                key,marker=self.create(stamp)
                # Bind the fictional encrypted object to exactly this local snapshot.
                del self.store.objects[key]
                old_artifact=marker['artifact_key'];body=self.store.objects.pop(old_artifact)
                base=old_artifact.rsplit('/',1)[0].replace(marker['dump_sha256'],digest)+'/'
                marker.update(dump_sha256=digest,dump_bytes=path.stat().st_size,artifact_key=base+'1'*32+'.tar.age')
                self.store.objects[marker['artifact_key']]=body
                self.store.objects[base+'complete.json']=finisher.p.encoded(marker)
            remote=self.plan()
            original=finisher.local.plan_retention(folder,self.now,lambda path:None)
            # A missing/mismatching remote binding may never authorize local deletion.
            first=remote['records'].pop(0)
            protected=original['copies'][0]
            result=finisher.covered_local_plan(original,remote,lambda path:None)
            self.assertEqual(result['retained'],set(original['copies'][-6:])|{protected})
            self.assertIn(protected,result['uncovered'])
            self.assertEqual(len(result['removed']),14)
            finisher.local.apply_plan(folder,result)
            self.assertTrue(protected.exists())
            self.assertTrue(original['latest'].exists())

    def test_acceptance_requires_custody_restore_image_and_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'acceptance.json'
            image='sha256:'+'b'*64
            accepted={'policy':finisher.POLICY,'recipient':self.recipient,'runtime_image':image,
                      'actual_database_restore':True,'exact_runtime_image_recovery':True,
                      'owner_password_manager_copy':True,'owner_offline_copy':True,'retention_selected':True}
            path.write_text(json.dumps(accepted));path.chmod(0o600)
            finisher.load_acceptance(path,self.config,image)
            for field in ('actual_database_restore','exact_runtime_image_recovery','owner_password_manager_copy','owner_offline_copy','retention_selected'):
                path.write_text(json.dumps({**accepted,field:False}))
                with self.assertRaises(ValueError):finisher.load_acceptance(path,self.config,image)
            path.write_text(json.dumps(accepted))
            with self.assertRaises(ValueError):finisher.load_acceptance(path,self.config,'sha256:'+'c'*64)

    def test_failed_publisher_stops_before_remote_or_local_expiry(self):
        import subprocess
        # The orchestration must stop at its failed child, before planning any
        # deletion or constructing a remote client. No real API/file operation.
        with patch.object(sys,'argv',['finish','--apply']), \
             patch.object(finisher.os,'geteuid',return_value=0), \
             patch.object(finisher.p,'load_config',return_value=self.config), \
             patch.object(finisher,'load_acceptance'), \
             patch.object(finisher.subprocess,'check_output',return_value=b'[{"State":{"Running":true},"Image":"test"}]'), \
             patch.object(finisher.subprocess,'run',side_effect=subprocess.CalledProcessError(1,['publisher'])), \
             patch.object(finisher,'plan_remote') as remote, \
             patch.object(finisher.local,'apply_plan') as local_apply:
            with self.assertRaises(subprocess.CalledProcessError):finisher.main()
            remote.assert_not_called();local_apply.assert_not_called()


if __name__=='__main__':
    unittest.main()
