from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.bulk_release import BulkReleaseService
from apps.tenant_apps.girvi.service_modules.release_lifecycle import ReleaseCreatePreview


class _FakeForm:
    def __init__(self, loan, *, release_date="2026-04-04", released_by=None, errors=None):
        self.loan_preview = loan
        self.initial = {
            "loan": loan,
            "release_date": release_date,
            "released_by": released_by,
        }
        self.cleaned_data = {}
        self.data = {}
        self.errors = errors or {}

    def add_prefix(self, name):
        return name


class _FakeFormSet:
    def __init__(self, forms):
        self.forms = forms


class BulkReleaseServicePreviewTests(SimpleTestCase):
    def test_build_review_context_exposes_preview_warnings_and_blockers(self):
        user = SimpleNamespace(profile=SimpleNamespace(workspace="tenant-1"))
        loan_ok = SimpleNamespace(loan_id="GL-001", borrower="Asha")
        loan_blocked = SimpleNamespace(loan_id="GL-002", borrower="Ravi")
        formset = _FakeFormSet([_FakeForm(loan_ok), _FakeForm(loan_blocked)])

        previews = [
            ReleaseCreatePreview(
                is_valid=True,
                loan=loan_ok,
                loan_id="GL-001",
                current_status="Disbursed",
                warnings=["No outstanding balance; accounting may be skipped."],
            ),
            ReleaseCreatePreview(
                is_valid=False,
                loan=loan_blocked,
                loan_id="GL-002",
                current_status="Released",
                errors=["Loan GL-002 cannot be released in status Released."],
            ),
        ]

        with patch(
            "apps.tenant_apps.girvi.service_modules.bulk_release.ReleaseLifecycleService.preview",
            side_effect=previews,
        ):
            context = BulkReleaseService.build_review_context(
                formset,
                summary={"total_loans": 2},
                commit_policy="strict",
                user=user,
            )

        self.assertTrue(context["has_preview_warnings"])
        self.assertTrue(context["has_preview_blockers"])
        self.assertEqual(context["preview_warning_count"], 1)
        self.assertEqual(context["preview_blocker_count"], 1)
        self.assertEqual(formset.forms[0].release_preview.warnings[0], "No outstanding balance; accounting may be skipped.")
        self.assertEqual(formset.forms[1].release_preview.errors[0], "Loan GL-002 cannot be released in status Released.")
