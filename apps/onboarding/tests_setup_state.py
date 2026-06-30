from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.onboarding.services.setup_state import (
    build_workspace_setup_display_state,
    dismiss_workspace_setup,
    mark_workspace_setup_complete,
    reopen_workspace_setup,
)


class WorkspaceSetupStateServiceTests(SimpleTestCase):
    def test_display_state_hides_dashboard_card_when_dismissed(self):
        state_row = SimpleNamespace(
            is_dismissed=True,
            is_marked_complete=False,
        )
        queryset = MagicMock()
        queryset.order_by.return_value.first.return_value = state_row
        checklist = SimpleNamespace(is_complete=False)

        with patch(
            "apps.onboarding.services.setup_state.WorkspaceSetupState.objects.filter",
            return_value=queryset,
        ):
            state = build_workspace_setup_display_state(
                user=SimpleNamespace(id=1),
                workspace=SimpleNamespace(id=2),
                checklist=checklist,
            )

        self.assertTrue(state.is_dismissed)
        self.assertFalse(state.is_complete)
        self.assertFalse(state.should_show_dashboard_card)

    def test_display_state_hides_dashboard_card_when_marked_complete(self):
        state_row = SimpleNamespace(
            is_dismissed=False,
            is_marked_complete=True,
        )
        queryset = MagicMock()
        queryset.order_by.return_value.first.return_value = state_row
        checklist = SimpleNamespace(is_complete=False)

        with patch(
            "apps.onboarding.services.setup_state.WorkspaceSetupState.objects.filter",
            return_value=queryset,
        ):
            state = build_workspace_setup_display_state(
                user=SimpleNamespace(id=1),
                workspace=SimpleNamespace(id=2),
                checklist=checklist,
            )

        self.assertTrue(state.is_complete)
        self.assertFalse(state.should_show_dashboard_card)

    def test_display_state_shows_dashboard_card_for_incomplete_active_setup(self):
        queryset = MagicMock()
        queryset.order_by.return_value.first.return_value = None
        checklist = SimpleNamespace(is_complete=False)

        with patch(
            "apps.onboarding.services.setup_state.WorkspaceSetupState.objects.filter",
            return_value=queryset,
        ):
            state = build_workspace_setup_display_state(
                user=SimpleNamespace(id=1),
                workspace=SimpleNamespace(id=2),
                checklist=checklist,
            )

        self.assertFalse(state.is_complete)
        self.assertTrue(state.should_show_dashboard_card)

    def test_state_mutators_update_expected_timestamps(self):
        state_row = SimpleNamespace(
            dismissed_at=None,
            marked_complete_at=None,
            save=MagicMock(),
        )

        with patch(
            "apps.onboarding.services.setup_state.WorkspaceSetupState.objects.get_or_create",
            return_value=(state_row, True),
        ), patch(
            "apps.onboarding.services.setup_state.timezone.now",
            return_value="now",
        ):
            dismiss_workspace_setup(user=SimpleNamespace(), workspace=SimpleNamespace())
            mark_workspace_setup_complete(
                user=SimpleNamespace(),
                workspace=SimpleNamespace(),
            )
            reopen_workspace_setup(user=SimpleNamespace(), workspace=SimpleNamespace())

        self.assertIsNone(state_row.dismissed_at)
        self.assertIsNone(state_row.marked_complete_at)
        self.assertEqual(3, state_row.save.call_count)
