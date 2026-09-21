"""Repeatable, reviewed three-Workspace conversion without SQL restoration."""
import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import PermissionDenied, ValidationError

from apps.tenant_apps.data_portability import linode_run as run


class Command(BaseCommand):
    help = "Package accepted inputs, compare a fresh dump, replay to clean Workspaces, or reconcile a Linode migration."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("action", choices=["package","check-source","replay","verify"])
        parser.add_argument("--package-dir",required=True)
        parser.add_argument("--expected-package-sha256")
        parser.add_argument("--dump")
        parser.add_argument("--pg-restore",default="pg_restore")
        parser.add_argument("--workspace-map-file")
        parser.add_argument("--actor-id",type=int)
        parser.add_argument("--expected-database")
        parser.add_argument("--source-namespace")
        parser.add_argument("--approval-reference")
        parser.add_argument("--exclusions-file")
        parser.add_argument("--output-dir")
        parser.add_argument("--commit",action="store_true")

    def handle(self, *args, **options):
        action = options["action"]
        required = ["dump"] if action == "check-source" else ["actor_id","expected_database","workspace_map_file"]
        required += (["dump","source_namespace","approval_reference","exclusions_file"] if action == "package" else ["expected_package_sha256"])
        if action in {"replay","verify"}:required.append("output_dir")
        if action == "replay":required += ["dump","commit"]
        if any(not options.get(k) for k in required):
            raise CommandError("Required for this action: "+", ".join("--"+k.replace("_","-") for k in required))
        try:
            shared = {"directory":options["package_dir"]}
            if action != "package":shared["expected_sha256"] = options["expected_package_sha256"]
            if action in {"package","check-source","replay"}:
                shared.update(archive_path=options["dump"],pg_restore=options["pg_restore"])
            if action != "check-source":
                shared.update(actor=get_user_model().objects.get(pk=options["actor_id"]),expected_database=options["expected_database"],
                    workspaces=json.loads(Path(options["workspace_map_file"]).read_text(encoding="utf-8")))
            if action == "package":
                sha,manifest = run.build_package(**shared,namespace=options["source_namespace"],approval_reference=options["approval_reference"],
                    exclusions=json.loads(Path(options["exclusions_file"]).read_text(encoding="utf-8")))
                result = {"package_sha256":sha,"schemas":list(manifest["workspaces"]),"media":manifest["media"],"production_ready":False}
            elif action == "check-source":
                result = run.check_source(**shared)
                if options["output_dir"]:
                    out = Path(options["output_dir"]);out.mkdir(parents=True,exist_ok=True)
                    (out/".gitignore").write_text("*\n")
                    run.save(out/"source-comparison.json",result)
                result = {**result,"schemas":{schema:{key:len(ids) for key,ids in values.items()} for schema,values in result["schemas"].items()}}
            elif action == "replay":
                run.replay_package(**shared,output_dir=options["output_dir"],confirmed=options["commit"])
                result = {"state":"ADMITTED_RECONCILIATION_REQUIRED","production_ready":False}
            else:
                result = run.verify_package(**shared,output_dir=options["output_dir"])
            self.stdout.write(json.dumps(result,indent=2))
        except (ValueError,KeyError,OSError,PermissionDenied,ValidationError,get_user_model().DoesNotExist) as exc:
            raise CommandError(str(exc)) from exc
