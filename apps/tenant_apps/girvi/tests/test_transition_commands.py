from django.test import SimpleTestCase

from apps.tenant_apps.girvi.transitions.commands import (
    DisburseTransitionCommand,
    GenericForwardTransitionCommand,
    MarkAuctionedTransitionCommand,
    MarkSoldTransitionCommand,
    UndoDisburseTransitionCommand,
    UndoReleaseTransitionCommand,
    UndoRepledgeTransitionCommand,
    get_transition_command_class,
)
from apps.tenant_apps.girvi.transition_registry import TRANSITION_REGISTRY


class TransitionCommandRegistryTests(SimpleTestCase):
    def test_transition_command_lookup(self):
        self.assertIs(get_transition_command_class("approve"), GenericForwardTransitionCommand)
        self.assertIs(get_transition_command_class("disburse"), DisburseTransitionCommand)
        self.assertIs(get_transition_command_class("mark_auctioned"), MarkAuctionedTransitionCommand)
        self.assertIs(get_transition_command_class("mark_sold"), MarkSoldTransitionCommand)
        self.assertIs(get_transition_command_class("undo_disburse"), UndoDisburseTransitionCommand)
        self.assertIs(get_transition_command_class("undo_release"), UndoReleaseTransitionCommand)
        self.assertIs(get_transition_command_class("undo_repledge"), UndoRepledgeTransitionCommand)

    def test_registry_binds_command_classes_for_core_transitions(self):
        self.assertIs(TRANSITION_REGISTRY["approve"].command_class, GenericForwardTransitionCommand)
        self.assertIs(TRANSITION_REGISTRY["disburse"].command_class, DisburseTransitionCommand)
        self.assertIs(TRANSITION_REGISTRY["undo_release"].command_class, UndoReleaseTransitionCommand)
        self.assertIs(TRANSITION_REGISTRY["undo_repledge"].command_class, UndoRepledgeTransitionCommand)
