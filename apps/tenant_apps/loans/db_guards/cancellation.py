import decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


CANCELLATION_GUARD_SQL = r"""
CREATE TRIGGER loans_funding_cancellation_immutable
BEFORE UPDATE OR DELETE ON loans_fundingloancancellation
FOR EACH ROW EXECUTE FUNCTION loans_guard_funding_immutable();
"""

CANCELLATION_GUARD_REVERSE_SQL = r"""
DROP TRIGGER IF EXISTS loans_funding_cancellation_immutable
ON loans_fundingloancancellation;
"""

