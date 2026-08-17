"""Single CI entry point for all exact control-plane contract evidence."""

from django_project.control_plane_contract_registry import CONTRACT_TEST_LABELS


def load_tests(loader, tests, pattern):
    labels = sorted(
        {
            label
            for contract_labels in CONTRACT_TEST_LABELS.values()
            for label in contract_labels
        }
    )
    tests.addTests(loader.loadTestsFromNames(labels))
    return tests
