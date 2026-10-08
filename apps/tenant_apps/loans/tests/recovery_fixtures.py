"""Arrange offline archive locks before TestCase fixture/catalogue writes."""
from django.db import connection

from apps.tenant_apps.loans.services.pawn_recovery import _models


def lock_recovery_fixture_tables():
    if not connection.settings_dict["NAME"].startswith("test_") or not connection.in_atomic_block:
        raise ValueError("Recovery fixture locks require a transactional test database.")
    # Offline commands lock before writing. TestCase normally does the opposite:
    # fixture writes can leave autovacuum waiting on our transaction while we wait
    # on its table lock. Call from setUpTestData, before class-level role grants
    # as well as fixture rows; per-test setUp is too late for catalogue writes.
    tables = ", ".join(connection.ops.quote_name(model._meta.db_table) for model in _models())
    with connection.cursor() as cursor:
        cursor.execute("LOCK TABLE " + tables + " IN SHARE ROW EXCLUSIVE MODE")
