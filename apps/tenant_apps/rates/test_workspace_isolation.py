from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.tenant_apps.rates.models import Rate, RateSource


class RateWorkspaceIsolationTests(SimpleTestCase):
    def test_rate_inherits_workspace_from_source(self):
        rate = Rate(
            rate_source=RateSource(id=1, workspace_id=7),
            buying_rate="1.00",
            selling_rate="2.00",
        )

        with patch.object(Rate.__mro__[1], "save", autospec=True):
            rate.save()

        self.assertEqual(rate.workspace_id, 7)

    def test_rate_rejects_source_from_another_workspace(self):
        rate = Rate(
            workspace_id=8,
            rate_source=RateSource(id=1, workspace_id=7),
            buying_rate="1.00",
            selling_rate="2.00",
        )

        with self.assertRaises(ValidationError):
            rate.save()
