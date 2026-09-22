"""Run feature checks against an explicitly isolated local test database.

Use the existing local development env file explicitly; credentials are read into
this process only. Never copy a rehearsal/production environment into the worktree.
"""

import argparse
import os
from pathlib import Path
import sys

import environ


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("labels", nargs="*", default=[
        "apps.tenant_apps.loans.tests.test_document_layouts",
        "apps.tenant_apps.loans.tests.test_document_overlay_v4",
        "apps.tenant_apps.loans.tests.test_document_layout_models",
        "apps.tenant_apps.loans.tests.test_document_issuance",
        "apps.tenant_apps.loans.tests.test_print_profiles",
        "apps.tenant_apps.loans.tests.test_documents",
        "apps.tenant_apps.loans.tests.test_setup_ui",
    ])
    args = parser.parse_args()
    if not args.env_file.is_file():
        parser.error("The explicit local development env file does not exist.")
    environ.Env.read_env(args.env_file)
    if os.environ.get("DB_HOST") not in {"localhost", "127.0.0.1", "::1"}:
        parser.error("Feature tests require a local PostgreSQL host.")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    os.environ.update({
        "DJANGO_SETTINGS_MODULE": "django_project.settings.test",
        "DB_NAME": "rokkad_ticket_template_feature",
        "DB_MIGRATION_NAME": "rokkad_ticket_template_feature",
        "DEBUG": "False",
        "SECRET_KEY": "isolated-ticket-template-tests-only-not-for-serving",
        "DJANGO_ALLOWED_HOSTS": "testserver,localhost,127.0.0.1",
    })
    from django.conf import settings

    settings.DATABASES["default"]["TEST"] = {
        "NAME": "test_rokkad_ticket_template_feature",
    }
    settings.MEDIA_ROOT = str(root / "outputs" / "ticket-template-tests" / "media")
    settings.STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    import django
    django.setup()
    from django.core.management import call_command

    print("Isolated tests: test_rokkad_ticket_template_feature; worktree-local media; no web server.", flush=True)
    call_command("test", *args.labels, interactive=False, keepdb=True, verbosity=1)


if __name__ == "__main__":
    main()
