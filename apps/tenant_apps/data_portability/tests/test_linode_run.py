import copy
from contextlib import nullcontext
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.core.management import call_command, CommandError
from django.test import SimpleTestCase

from apps.tenant_apps.data_portability import linode_run as run
from apps.tenant_apps.data_portability.parsers import PortabilityError
from .fixtures import PortabilityFixture
from .test_loan_archive import document as archive_document


class LinodeRunTests(SimpleTestCase):
    def package(self, directory):
        root = Path(directory)/"package"
        root.mkdir()
        manifest = {"profile":run.PROFILE,"archive_sha256":"a"*64,"source_database":"accepted",
                    "workspaces":{},"files":[]}
        for schema in run.SCHEMAS:
            (root/schema).mkdir()
            manifest["workspaces"][schema] = {"party_batches":[]}
            for name in ("source-index.json","setup.json","openings.jsonl","closed.jsonl","excluded.jsonl"):
                path = root/schema/name
                path.write_text("{}" if path.suffix==".json" else "")
                manifest["files"].append({"path":f"{schema}/{name}","sha256":run.sha_file(path)})
        run.save(root/"manifest.json",manifest)
        return root,manifest,run.sha_file(root/"manifest.json")

    def test_manifest_and_file_tampering_fail_before_loading_inputs(self):
        with TemporaryDirectory() as directory:
            root,manifest,sha = self.package(directory)
            self.assertEqual(run.load_package(root,sha)[1],manifest)
            with self.assertRaisesRegex(PortabilityError,"checksum changed"):
                run.load_package(root,"b"*64)
            (root/"jcl"/"setup.json").write_text('{"changed":true}')
            with self.assertRaisesRegex(PortabilityError,"file changed"):
                run.load_package(root,sha)

    def test_path_escape_duplicate_and_unhashed_input_are_rejected(self):
        for kind in ("escape","duplicate","unhashed"):
            with self.subTest(kind=kind),TemporaryDirectory() as directory:
                root,manifest,_ = self.package(directory)
                if kind=="escape":manifest['files'][0]['path']='../outside.json'
                elif kind=="duplicate":manifest['files'].append(manifest['files'][0])
                else:manifest['workspaces']['jcl']['party_batches']=[{'path':'jcl/unhashed.jsonl'}]
                run.save(root/'manifest.json',manifest)
                with self.assertRaises(PortabilityError):run.load_package(root,run.sha_file(root/'manifest.json'))

    def test_source_diff_distinguishes_new_changed_removed_and_unchanged_rows(self):
        self.assertEqual(run.compare_index({'loan:1':'a','loan:2':'b','loan:3':'c'}, {'loan:1':'a','loan:2':'d','loan:4':'e'}),
                         {'added':['loan:4'],'removed':['loan:3'],'changed':['loan:2']})

    def test_mapping_cannot_merge_source_schemas(self):
        for value in ({'jcl':1},{'jcl':1,'jsk':1,'lakshmipawnbroker':3},{'jcl':True,'jsk':2,'lakshmipawnbroker':3}):
            with self.assertRaises(PortabilityError):run.validate_workspace_map(value)

    def test_rebinding_changes_only_destination_ids_and_preserves_approved_money_and_evidence(self):
        row={'opening':{'profile':'loan-opening-commit/1','review':{'source':{'loan_id':'girvi_loan:9'},
              'mapping':{'workspace_id':1,'borrower_id':2,'licence_revision_id':3,'series_id':4,'product_version_id':5,'evidence_reference':'owner'},
              'balances':{'principal':'1000','interest':'37','fees':'0'}},'setup':{'local_loan_number':'A009'}},
             'source_evidence':{'records':[{'source':{'external_id':'girvi_loan:9'},'facts':{'series_id':'7'}}],'payment_exclusion':{'reason':'owner'}}}
        original=copy.deepcopy(row)
        actual=run.rebind_opening(row,workspace_id=11,borrower_id=12,setup_map={'series':{'7':{'revision_id':13,'series_id':14}},'product_version_id':15})
        wanted=copy.deepcopy(original['opening'])
        wanted['review']['mapping'].update(workspace_id=11,borrower_id=12,licence_revision_id=13,series_id=14,product_version_id=15)
        self.assertEqual(actual,wanted)
        self.assertEqual(row,original)

    def test_replay_rejects_changed_dump_source_destination_and_missing_confirmation_before_setup(self):
        with TemporaryDirectory() as directory:
            root,manifest,sha=self.package(directory)
            archive=Path(directory)/'source.dump';archive.write_bytes(b'changed snapshot')
            args=dict(directory=root,expected_sha256=sha,archive_path=archive,workspaces={'jcl':1,'jsk':2,'lakshmipawnbroker':3},
                actor=object(),expected_database='new-target',output_dir=Path(directory)/'out',confirmed=True)
            with patch.object(run,'runtime_guard'),patch.object(run,'workspace_context',return_value=nullcontext()),\
                 patch.object(run,'require_history_setup_access'),patch.object(run,'require_access'),patch.object(run,'_setup') as setup:
                for changes, message in (({},'snapshot changed'),({'confirmed':False},'Explicitly confirm'),({'expected_database':'accepted'},'not a replay destination')):
                    with self.subTest(changes=changes),self.assertRaisesRegex(PortabilityError,message):run.replay_package(**{**args,**changes})
                setup.assert_not_called()
                self.assertFalse((Path(directory)/'out').exists())

    def test_all_workspace_access_checks_precede_writes(self):
        with TemporaryDirectory() as directory:
            root,_,sha=self.package(directory)
            with patch.object(run,'runtime_guard'),patch.object(run,'workspace_context',return_value=nullcontext()),\
                 patch.object(run,'require_history_setup_access',side_effect=[object(),PermissionDenied('denied')]),\
                 patch.object(run,'require_access'),patch.object(run,'_setup') as setup:
                with self.assertRaises(PermissionDenied):run.replay_package(directory=root,expected_sha256=sha,archive_path='unused',
                    workspaces={'jcl':1,'jsk':2,'lakshmipawnbroker':3},actor=object(),expected_database='new',output_dir=Path(directory)/'out',confirmed=True)
                setup.assert_not_called()

    def test_cli_without_confirmation_cannot_start_replay(self):
        with self.assertRaisesRegex(CommandError,'--commit'):
            call_command('linode_migration','replay',package_dir='unused',expected_package_sha256='a'*64,dump='unused',
                actor_id=1,expected_database='new',workspace_map_file='unused',output_dir='unused',stdout=io.StringIO())


class LinodeReconciliationTests(PortabilityFixture):
    def test_extra_version_of_a_closed_source_record_cannot_hide_in_unique_id_counts(self):
        self.assert_archive_rejected(extra_version=True,message='Closed history counts differ')

    def test_matching_document_from_another_source_branch_cannot_pass_reconciliation(self):
        self.assert_archive_rejected(wrong_schema=True,message='Closed source provenance differs')

    def assert_archive_rejected(self, *, message, extra_version=False, wrong_schema=False):
        from django.db import connection
        from apps.orgs.audit import AuditLog

        with TemporaryDirectory() as directory:
            root,manifest,_ = LinodeRunTests().package(directory)
            expected = archive_document()
            expected['source']['loan_id'] = 'girvi_loan:1'
            manifest['namespace'] = expected['source']['namespace']
            earlier = copy.deepcopy(expected)
            earlier['source']['snapshot_reference'] = 'earlier-source-snapshot'
            run.write_rows(root/'jcl'/'closed.jsonl',[expected])
            run.save(root/'jcl'/'source-index.json',{'girvi_loan:1':'a'*64})
            for meta in manifest['workspaces'].values():
                meta.update(source_system='another-schema' if wrong_schema else 'paper-register-a',party_counts={},closed=0)
            manifest['workspaces']['jcl']['closed'] = 1
            for entry in manifest['files']:
                entry['sha256'] = run.sha_file(root/entry['path'])
            run.save(root/'manifest.json',manifest)
            sha = run.sha_file(root/'manifest.json')
            mapping = {'jcl':self.a.pk,'jsk':self.b.pk,'lakshmipawnbroker':self.b.pk+1000}
            out = Path(directory)/'report';out.mkdir()
            run.save(out/'binding.json',{'package_sha256':sha,'database':connection.settings_dict['NAME'],'workspaces':mapping})
            with self.scoped():
                # Valid archive claims must still match this replay's exact
                # snapshot and source-branch boundary.
                for value in ([earlier,expected] if extra_version else [expected]):
                    run.accept_evidence(workspace_id=self.a.pk,actor=self.actor,document=value,
                        expected_sha256=run.digest(value),confirmed=True)
                AuditLog.log('DATA_IMPORT',company=self.a,user=self.actor,data={
                    'linode_run':sha,'phase':'setup','config_sha256':run.digest({}),'mapping':{}})
                with self.assertRaisesRegex(PortabilityError,message):
                    run.verify_package(directory=root,expected_sha256=sha,workspaces=mapping,actor=self.actor,
                        expected_database=connection.settings_dict['NAME'],output_dir=out,progress=lambda *a,**k:None)
            self.assertFalse((out/'verification.json').exists())
