from pathlib import Path

from django.test import SimpleTestCase


LOANS_ROOT = Path(__file__).resolve().parents[1]


class AccountingRetirementBoundaryTests(SimpleTestCase):
    def test_direct_dea_imports_are_confined_to_known_retirement_boundary(self):
        actual = set()
        for path in LOANS_ROOT.rglob("*.py"):
            if "tests" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            if "apps.tenant_apps.dea" in source:
                actual.add(path.relative_to(LOANS_ROOT).as_posix())

        self.assertEqual(actual, set())

    def test_target_runtime_has_no_standalone_accounting_import(self):
        target_roots = (
            LOANS_ROOT,
            LOANS_ROOT.parent / "party",
            LOANS_ROOT.parent / "notify_v2",
            LOANS_ROOT.parent / "rates",
        )
        offenders = []
        for root in target_roots:
            for path in root.rglob("*.py"):
                if "tests" in path.parts:
                    continue
                if "standalone_accounting" in path.read_text(encoding="utf-8"):
                    offenders.append(path.relative_to(LOANS_ROOT.parent).as_posix())

        self.assertEqual(offenders, [])

    def test_balance_fold_has_no_direct_retiring_app_import(self):
        source = (LOANS_ROOT / "selectors" / "balances.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("apps.tenant_apps.dea", source)
        self.assertNotIn("standalone_accounting", source)

    def test_event_recording_does_not_create_or_deliver_outbox_rows(self):
        source = (LOANS_ROOT / "services" / "event_recording.py").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("PawnLoanAccountingOutbox", source)
        self.assertNotIn("transaction.on_commit", source)
        self.assertNotIn("deliver_outbox_event", source)
        self.assertNotIn("retry_failed_outbox_event", source)

    def test_legacy_event_module_paths_are_deleted(self):
        self.assertFalse((LOANS_ROOT / "services" / "accounting_outbox.py").exists())
        self.assertFalse((LOANS_ROOT / "integrations" / "dea_payloads.py").exists())
        self.assertFalse((LOANS_ROOT / "tests" / "test_pawn_disbursal_service.py").exists())
        self.assertFalse((LOANS_ROOT / "services" / "accounting_readiness.py").exists())
        self.assertFalse((LOANS_ROOT / "tests" / "test_accounting_readiness.py").exists())

    def test_lifecycle_results_and_runtime_surfaces_do_not_use_outbox(self):
        offenders = []
        roots = (LOANS_ROOT / "services", LOANS_ROOT / "web", LOANS_ROOT / "documents")
        for root in roots:
            for path in root.rglob("*.py"):
                source = path.read_text(encoding="utf-8")
                if ".outbox" in source or "PawnLoanAccountingOutbox" in source:
                    offenders.append(path.relative_to(LOANS_ROOT).as_posix())

        self.assertEqual(offenders, [])

    def test_outbox_model_is_retired_from_current_schema_state(self):
        models_source = (LOANS_ROOT / "models" / "core.py").read_text(
            encoding="utf-8"
        )
        migration = (
            LOANS_ROOT / "migrations" / "0057_retire_accounting_outbox.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("class PawnLoanAccountingOutbox", models_source)
        self.assertIn("DeleteModel", migration)

    def test_event_spine_has_neutral_canonical_model_name(self):
        models_source = (LOANS_ROOT / "models" / "core.py").read_text(
            encoding="utf-8"
        )
        migration = (
            LOANS_ROOT
            / "migrations"
            / "0058_rename_pawnloanaccountingevent_pawnloanevent.py"
        ).read_text(encoding="utf-8")

        self.assertIn("class PawnLoanEvent(models.Model):", models_source)
        self.assertIn("RenameModel", migration)
        self.assertIn('new_name="PawnLoanEvent"', migration)

    def test_runtime_no_longer_uses_old_event_model_name(self):
        offenders = []
        for path in LOANS_ROOT.rglob("*.py"):
            if "tests" in path.parts or "migrations" in path.parts:
                continue
            if "PawnLoanAccountingEvent" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(LOANS_ROOT).as_posix())

        self.assertEqual(offenders, [])

    def test_runtime_no_longer_imports_legacy_event_modules(self):
        offenders = []
        for path in LOANS_ROOT.rglob("*.py"):
            if "tests" in path.parts or "migrations" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            if "accounting_outbox" in source or "dea_payloads" in source:
                offenders.append(path.relative_to(LOANS_ROOT).as_posix())

        self.assertEqual(offenders, [])

    def test_lifecycle_services_have_no_accounting_delivery_handler(self):
        lifecycle_modules = (
            "pawn_disbursal.py",
            "pawn_repayment.py",
            "pawn_interest.py",
            "pawn_reversal.py",
            "pawn_release.py",
            "pawn_renewals.py",
            "pawn_auctions.py",
            "event_recording.py",
        )
        offenders = []
        for module_name in lifecycle_modules:
            source = (LOANS_ROOT / "services" / module_name).read_text(
                encoding="utf-8"
            )
            if "delivery_handler" in source or "DeliveryHandler" in source:
                offenders.append(module_name)

        self.assertEqual(offenders, [])

    def test_runtime_has_no_accounting_event_field_name(self):
        offenders = []
        for path in LOANS_ROOT.rglob("*.py"):
            if "tests" in path.parts or "migrations" in path.parts:
                continue
            if "accounting_event" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(LOANS_ROOT).as_posix())

        self.assertEqual(offenders, [])

    def test_cash_only_runtime_has_no_recognition_policy_concept(self):
        offenders = []
        for path in LOANS_ROOT.rglob("*.py"):
            if "tests" in path.parts or "migrations" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            if "AccountingRecognition" in source or "accounting_recognition" in source:
                offenders.append(path.relative_to(LOANS_ROOT).as_posix())

        migration = (
            LOANS_ROOT
            / "migrations"
            / "0063_remove_loanpolicysnapshot_accounting_recognition_and_more.py"
        ).read_text(encoding="utf-8")
        self.assertEqual(offenders, [])
        self.assertEqual(migration.count("migrations.RemoveField("), 2)

    def test_runtime_has_no_accounting_delivery_readiness_contract(self):
        forbidden = (
            "PostingBlocker",
            "posting_ready",
            "posting_blockers",
            "accounting_mode",
            "ACCOUNTING_NOT_READY",
            "ACCOUNTING_BLOCKED",
        )
        offenders = []
        for path in LOANS_ROOT.rglob("*.py"):
            if "tests" in path.parts or "migrations" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            if any(term in source for term in forbidden):
                offenders.append(path.relative_to(LOANS_ROOT).as_posix())

        self.assertEqual(offenders, [])

    def test_risk_and_exposure_contracts_use_loans_vocabulary(self):
        targets = (
            LOANS_ROOT / "domain" / "risk.py",
            LOANS_ROOT / "selectors" / "risk.py",
            LOANS_ROOT / "selectors" / "exposure.py",
        )
        offenders = []
        for path in targets:
            source = path.read_text(encoding="utf-8")
            if any(
                term in source
                for term in (
                    "accounting_receivable",
                    "accounting_variance",
                    "ACCOUNTING_VARIANCE",
                )
            ):
                offenders.append(path.relative_to(LOANS_ROOT).as_posix())

        self.assertEqual(offenders, [])
