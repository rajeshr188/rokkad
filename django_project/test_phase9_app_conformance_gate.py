"""Single CI entry point for supported-app authorization conformance."""


PHASE9_CONFORMANCE_TEST_LABELS = (
    "django_project.test_phase9_app_conformance",
    "apps.tenant_apps.party.tests.test_party_access",
    "apps.tenant_apps.rates.test_access_conformance",
    "apps.tenant_apps.notify_v2.tests_access",
    "apps.tenant_apps.loans.tests.test_access",
)


def load_tests(loader, tests, pattern):
    for label in PHASE9_CONFORMANCE_TEST_LABELS:
        tests.addTests(loader.loadTestsFromName(label))
    return tests
