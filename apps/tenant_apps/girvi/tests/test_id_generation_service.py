from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.id_generation import (
    GirviNumberSequenceService,
    LoanIDGenerator,
    ReleaseIDGenerator,
    validate_loan_id_unique_across_loan_tables,
)


class LoanIDGeneratorTests(SimpleTestCase):
    def test_generate_allocates_given_sequence_by_default(self):
        series = SimpleNamespace(id=1)

        class FakeSequence:
            class DocumentKind:
                GIVEN_LOAN = "GIVEN_LOAN"
                TAKEN_LOAN = "TAKEN_LOAN"

        with patch(
            "apps.tenant_apps.girvi.service_modules.id_generation._sequence_model",
            return_value=FakeSequence,
        ), patch.object(
            GirviNumberSequenceService,
            "allocate",
            return_value="I00008",
        ) as mock_allocate:
            next_id = LoanIDGenerator.generate(series)

        self.assertEqual(next_id, "I00008")
        mock_allocate.assert_called_once_with(series, "GIVEN_LOAN")

    def test_generate_allocates_taken_sequence_for_taken_model(self):
        series = SimpleNamespace(id=1)
        taken_model = type("TakenLoan", (), {})

        class FakeSequence:
            class DocumentKind:
                GIVEN_LOAN = "GIVEN_LOAN"
                TAKEN_LOAN = "TAKEN_LOAN"

        with patch(
            "apps.tenant_apps.girvi.service_modules.id_generation._sequence_model",
            return_value=FakeSequence,
        ), patch.object(
            GirviNumberSequenceService,
            "allocate",
            return_value="T00001",
        ) as mock_allocate:
            next_id = LoanIDGenerator.generate(series, loan_model=taken_model)

        self.assertEqual(next_id, "T00001")
        mock_allocate.assert_called_once_with(series, "TAKEN_LOAN")

    def test_preview_does_not_allocate(self):
        series = SimpleNamespace(id=1)

        class FakeSequence:
            class DocumentKind:
                GIVEN_LOAN = "GIVEN_LOAN"
                TAKEN_LOAN = "TAKEN_LOAN"

        with patch(
            "apps.tenant_apps.girvi.service_modules.id_generation._sequence_model",
            return_value=FakeSequence,
        ), patch.object(
            GirviNumberSequenceService,
            "preview",
            return_value="I00008",
        ) as mock_preview:
            next_id = LoanIDGenerator.preview(series)

        self.assertEqual(next_id, "I00008")
        mock_preview.assert_called_once_with(series, "GIVEN_LOAN")

    def test_preview_skips_existing_ids_when_sequence_row_is_stale(self):
        series = SimpleNamespace(id=1)
        sequence = SimpleNamespace(
            series=series,
            document_kind="GIVEN_LOAN",
            is_active=True,
            next_number=5,
            format_number=lambda number: f"A{int(number):05d}",
        )

        with patch.object(
            GirviNumberSequenceService,
            "ensure_sequence",
            return_value=sequence,
        ), patch.object(
            GirviNumberSequenceService,
            "_existing_ids",
            return_value=["A00005", "A00006"],
        ):
            next_id = GirviNumberSequenceService.preview(series, "GIVEN_LOAN")

        self.assertEqual(next_id, "A00007")

    def test_allocate_skips_existing_ids_when_sequence_row_is_stale(self):
        series = SimpleNamespace(id=1)
        sequence = SimpleNamespace(
            series=series,
            document_kind="GIVEN_LOAN",
            is_active=True,
            next_number=5,
            format_number=lambda number: f"A{int(number):05d}",
            mark_allocated=MagicMock(),
        )

        fake_get = MagicMock(return_value=sequence)
        fake_select_related = MagicMock(get=fake_get)
        fake_select_for_update = MagicMock(
            return_value=MagicMock(select_related=MagicMock(return_value=fake_select_related))
        )

        class FakeSequence:
            objects = MagicMock(select_for_update=fake_select_for_update)

        with patch(
            "apps.tenant_apps.girvi.service_modules.id_generation._sequence_model",
            return_value=FakeSequence,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.id_generation.transaction.atomic",
            return_value=nullcontext(),
        ), patch.object(
            GirviNumberSequenceService,
            "ensure_sequence",
            return_value=sequence,
        ), patch.object(
            GirviNumberSequenceService,
            "_existing_ids",
            return_value=["A00005", "A00006"],
        ):
            next_id = GirviNumberSequenceService.allocate(series, "GIVEN_LOAN")

        self.assertEqual(next_id, "A00007")
        sequence.mark_allocated.assert_called_once_with(7, updated_by=None)

    def test_release_id_generator_uses_release_sequence(self):
        series = SimpleNamespace(id=1)

        class FakeSequence:
            class DocumentKind:
                GIVEN_LOAN_RELEASE = "GIVEN_LOAN_RELEASE"

        with patch(
            "apps.tenant_apps.girvi.service_modules.id_generation._sequence_model",
            return_value=FakeSequence,
        ), patch.object(
            GirviNumberSequenceService,
            "allocate",
            return_value="RL00001",
        ) as mock_allocate:
            release_id = ReleaseIDGenerator.generate(series)

        self.assertEqual(release_id, "RL00001")
        mock_allocate.assert_called_once_with(series, "GIVEN_LOAN_RELEASE")

    def test_validate_loan_id_checks_given_and_taken_tables(self):
        given_manager = MagicMock()
        taken_manager = MagicMock()
        given_qs = MagicMock()
        taken_qs = MagicMock()
        given_manager.objects.filter.return_value = given_qs
        taken_manager.objects.filter.return_value = taken_qs
        given_qs.exists.return_value = False
        taken_qs.exists.return_value = True

        with patch(
            "apps.tenant_apps.girvi.service_modules.id_generation.apps.get_model",
            side_effect=[given_manager, taken_manager],
        ):
            with self.assertRaises(ValidationError):
                validate_loan_id_unique_across_loan_tables("I00008")

        given_manager.objects.filter.assert_called_once_with(loan_id="I00008")
        taken_manager.objects.filter.assert_called_once_with(loan_id="I00008")

    def test_ensure_sequence_initializes_missing_row_from_existing_ids(self):
        series = SimpleNamespace(pk=7, id=7)
        sequence = SimpleNamespace(is_active=True, preview_value="A00001")

        class FakeDoesNotExist(Exception):
            pass

        fake_manager = MagicMock()
        fake_manager.get.side_effect = [FakeDoesNotExist(), sequence]

        class FakeSequence:
            DoesNotExist = FakeDoesNotExist
            objects = fake_manager

        with patch(
            "apps.tenant_apps.girvi.service_modules.id_generation._sequence_model",
            return_value=FakeSequence,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.id_generation.transaction.atomic",
            return_value=nullcontext(),
        ), patch.object(
            GirviNumberSequenceService,
            "sync_from_existing",
        ) as sync_from_existing:
            resolved = GirviNumberSequenceService.ensure_sequence(
                series,
                "GIVEN_LOAN",
                updated_by="user",
            )

        self.assertIs(resolved, sequence)
        sync_from_existing.assert_called_once_with(
            series,
            "GIVEN_LOAN",
            apply=True,
            updated_by="user",
        )
        fake_manager.get.assert_called_with(series_id=7, document_kind="GIVEN_LOAN")
