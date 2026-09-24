from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from apps.configuration.models import LegacyGlobalPreference, LegacyUserPreference


class LegacyPreferenceRetentionTests(TestCase):
    def test_existing_values_survive_adoption_without_deserialization(self):
        user = get_user_model().objects.create_user(username="legacy-pref-retention")
        raw = '{"unrecognized_old_setting": "retain exactly"}'
        global_row = LegacyGlobalPreference.objects.create(section="retired", name="global", raw_value=raw)
        user_row = LegacyUserPreference.objects.create(instance=user, section="retired", name="user", raw_value="False")
        retain = import_module("apps.configuration.migrations.0003_retain_legacy_preference_data").retain_or_create_tables
        with connection.schema_editor(atomic=False) as editor:
            retain(apps, editor)
        global_row.refresh_from_db()
        user_row.refresh_from_db()
        self.assertEqual(global_row.raw_value, raw)
        self.assertEqual(user_row.raw_value, "False")
        self.assertFalse(apps.is_installed("dynamic_preferences"))

    def test_user_deletion_still_collects_retained_user_rows(self):
        user = get_user_model().objects.create_user(username="legacy-pref-deletion")
        row = LegacyUserPreference.objects.create(instance=user, section="ui", name="theme", raw_value="dark")
        pk = row.pk
        user.delete()
        self.assertFalse(LegacyUserPreference.objects.filter(pk=pk).exists())
