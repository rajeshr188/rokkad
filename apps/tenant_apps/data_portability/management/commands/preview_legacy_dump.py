from django.core.management.base import BaseCommand, CommandError

from apps.tenant_apps.data_portability.legacy_dump import inspect_archive
from apps.tenant_apps.data_portability.legacy_profiles import PROFILES, get_profile
from apps.tenant_apps.data_portability.legacy_preview import build_preview, encode, namespace_uuid, propose_collateral_exclusions, write_preview
from apps.tenant_apps.data_portability.parsers import PortabilityError


class Command(BaseCommand):
    help = "Offline read-only preview of one legacy tenant in a PostgreSQL custom dump. No database access."
    requires_system_checks = []
    requires_migrations_checks = False

    def add_arguments(self, parser):
        parser.add_argument("--dump", required=True)
        parser.add_argument("--pg-restore", default="pg_restore")
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--list-schemas", action="store_true")
        mode.add_argument("--source-schema")
        parser.add_argument("--source-namespace")
        parser.add_argument("--source-profile", choices=sorted(PROFILES),
                            help="Apply a versioned Linode schema profile and its reviewed source corrections.")
        parser.add_argument("--output-dir")
        parser.add_argument("--reconciliation-as-of")
        parser.add_argument("--reconciliation-timezone")
        parser.add_argument("--owner-profile", choices=["jcl-owner/1", "jcl-owner/2", "linode-owner/1"],
                            help="Apply the source-scoped owner net-weight attestation and collection diagnostics.")
        parser.add_argument("--prepare-openings", action="store_true",
                            help="Prepare offline opening review records for retained unreleased loans.")
        parser.add_argument("--propose-skip-incomplete-collateral", action="store_true",
                            help="Add an unapproved exclusion proposal; retain all source rows in the report.")

    def handle(self, *args, **options):
        try:
            if options["owner_profile"]:
                from apps.tenant_apps.data_portability.legacy_owner_rules import check_profile
                check_profile({"source_namespace": options["source_namespace"], "source_schema": options["source_schema"],
                               "source_profile": options["source_profile"]}, options["owner_profile"])
                if not options["reconciliation_as_of"]:
                    raise PortabilityError("--owner-profile requires an explicit reconciliation date and timezone.")
            if options["source_profile"] and options["source_schema"] and get_profile(options["source_profile"]).schema != options["source_schema"]:
                raise PortabilityError("--source-profile must match --source-schema.")
            if (options["reconciliation_as_of"] or options["reconciliation_timezone"]) and not (
                    options["prepare_openings"] and options["reconciliation_as_of"] and options["reconciliation_timezone"]):
                raise PortabilityError("Reconciliation requires --prepare-openings, --reconciliation-as-of and --reconciliation-timezone.")
            if options["prepare_openings"] and (options["list_schemas"] or not options["propose_skip_incomplete_collateral"]):
                raise PortabilityError("--prepare-openings requires a tenant preview and --propose-skip-incomplete-collateral.")
            if options["list_schemas"]:
                if options["source_namespace"] or options["output_dir"] or options["propose_skip_incomplete_collateral"]:
                    raise PortabilityError("Schema inventory does not take a namespace or output directory.")
            elif not options["source_namespace"] or not options["output_dir"]:
                raise PortabilityError("Preview requires --source-namespace and a new --output-dir.")
            else:
                namespace_uuid(options["source_namespace"])
            extracted = inspect_archive(options["dump"], schema=options["source_schema"], pg_restore=options["pg_restore"])
            if options["list_schemas"]:
                self.stdout.write(encode(extracted))
                return
            summary, records = build_preview(extracted, schema=options["source_schema"], source_namespace=options["source_namespace"],
                                             source_profile=options["source_profile"])
            if options["propose_skip_incomplete_collateral"]:
                propose_collateral_exclusions(summary, records)
            opening_documents = None
            if options["prepare_openings"]:
                from apps.tenant_apps.data_portability.opening_review import prepare_openings
                opening_documents = prepare_openings(summary, records, owner_profile=options["owner_profile"])
            reconciliation = ({"as_of": options["reconciliation_as_of"], "business_timezone": options["reconciliation_timezone"],
                               "owner_profile": options["owner_profile"]}
                              if options["reconciliation_as_of"] else None)
            output = write_preview(options["output_dir"], summary, records, opening_documents=opening_documents, reconciliation=reconciliation)
            self.stdout.write(f"Read-only preview complete: {sum(summary['counts'].values())} source records; "
                              f"{summary['records_with_errors']} records with errors. Nothing imported.")
            self.stdout.write(str((output / "review.html").resolve()))
            if opening_documents is not None:
                self.stdout.write(f"{len(opening_documents)} opening review candidates: " + str((output / "opening-review.html").resolve()))
            if options["owner_profile"]:
                self.stdout.write("Owner rule review: " + str((output / "owner-rule-review.html").resolve()))
        except PortabilityError as exc:
            raise CommandError(str(exc)) from exc
