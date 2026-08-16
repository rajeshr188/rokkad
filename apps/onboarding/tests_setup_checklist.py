from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.onboarding.services.setup_checklist import (
    COMPLETE,
    INCOMPLETE,
    UNKNOWN,
    WorkspaceSetupMetrics,
    build_workspace_setup_checklist,
    collect_workspace_setup_metrics,
)
from apps.orgs.models import Company


class WorkspaceSetupChecklistTests(SimpleTestCase):
    def _workspace(self, name="Demo Workspace"):
        return SimpleNamespace(name=name, schema_name="demo_workspace")

    def _items_by_key(self, checklist):
        return {item.key: item for item in checklist.items}

    def test_empty_workspace_metrics_keep_checklist_non_blocking_and_incomplete(self):
        checklist = build_workspace_setup_checklist(
            workspace=self._workspace(),
            metrics=WorkspaceSetupMetrics(
                member_count=1,
                invitation_count=0,
                party_count=0,
                rate_count=0,
                transaction_count=0,
            ),
        )
        items = self._items_by_key(checklist)

        self.assertEqual(COMPLETE, items["business_profile"].status)
        self.assertEqual(INCOMPLETE, items["parties"].status)
        self.assertEqual(INCOMPLETE, items["invite_team"].status)
        self.assertEqual(1, checklist.completed_count)
        self.assertEqual(4, checklist.total_count)
        self.assertFalse(checklist.is_complete)
        self.assertEqual(25, checklist.completion_percentage)

    def test_complete_metrics_mark_every_setup_item_complete(self):
        checklist = build_workspace_setup_checklist(
            workspace=self._workspace(),
            metrics=WorkspaceSetupMetrics(
                member_count=2,
                invitation_count=0,
                party_count=1,
                rate_count=1,
                transaction_count=1,
            ),
        )

        self.assertTrue(checklist.is_complete)
        self.assertEqual(100, checklist.completion_percentage)
        self.assertEqual(
            {
                "business_profile",
                "parties",
                "invite_team",
                "rates",
            },
            {item.key for item in checklist.items if item.is_complete},
        )

    def test_unknown_tenant_metrics_render_unknown_instead_of_complete(self):
        checklist = build_workspace_setup_checklist(
            workspace=self._workspace(name=""),
            metrics=WorkspaceSetupMetrics(
                member_count=None,
                invitation_count=None,
                party_count=None,
                rate_count=None,
                transaction_count=None,
            ),
        )
        items = self._items_by_key(checklist)

        self.assertEqual(INCOMPLETE, items["business_profile"].status)
        self.assertEqual(UNKNOWN, items["parties"].status)
        self.assertEqual(UNKNOWN, items["invite_team"].status)
        self.assertEqual(3, checklist.unknown_count)
        self.assertEqual(0, checklist.completed_count)

    def test_pending_invitation_counts_toward_team_setup(self):
        checklist = build_workspace_setup_checklist(
            workspace=self._workspace(),
            metrics=WorkspaceSetupMetrics(
                member_count=1,
                invitation_count=1,
                party_count=0,
                rate_count=0,
                transaction_count=0,
            ),
        )

        self.assertEqual(COMPLETE, self._items_by_key(checklist)["invite_team"].status)

    def test_collect_metrics_uses_best_effort_model_counts(self):
        workspace = Company(id=1, name="Demo Workspace", schema_name="demo_workspace")

        with (
            patch(
                "apps.onboarding.services.setup_checklist._safe_queryset_count",
                return_value=1,
            ) as safe_queryset_count,
            patch(
                "apps.onboarding.services.setup_checklist._safe_model_count",
                return_value=1,
            ) as safe_model_count,
        ):
            metrics = collect_workspace_setup_metrics(workspace=workspace)

        self.assertEqual(1, metrics.member_count)
        self.assertEqual(1, metrics.invitation_count)
        self.assertEqual(1, metrics.party_count)
        self.assertEqual(2, metrics.rate_count)
        self.assertEqual(1, metrics.transaction_count)
        self.assertGreaterEqual(safe_queryset_count.call_count, 2)
        safe_model_count.assert_any_call("party", "Party")
        safe_model_count.assert_any_call("rates", "Rate")
        safe_model_count.assert_any_call("loans", "PawnLoanEvent")
