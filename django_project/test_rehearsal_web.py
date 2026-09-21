"""The opt-in browser configuration must preserve rehearsal isolation."""
import json
import os
import subprocess
import sys

from django.test import SimpleTestCase, override_settings

from django_project.context_processors import rehearsal_environment


class RehearsalWebSettingsTests(SimpleTestCase):
    def inspect_settings(self, database):
        code = """
import json
from django_project.settings import baseline_rehearsal_web as web, dev
print(json.dumps({
 'database':web.DATABASES['default']['NAME'],
 'normal_database':dev.DATABASES['default']['NAME'],
 'hosts':web.ALLOWED_HOSTS,
 'cookies':[web.SESSION_COOKIE_NAME,web.CSRF_COOKIE_NAME],
 'secure':[web.SESSION_COOKIE_SECURE,web.CSRF_COOKIE_SECURE,web.SECURE_SSL_REDIRECT],
 'normal_cookies_secure':[dev.SESSION_COOKIE_SECURE,dev.CSRF_COOKIE_SECURE],
 'storage':web.STORAGES['default']['BACKEND'],
 'media':str(web.MEDIA_ROOT),
 'cache':web.CACHES['default']['BACKEND'],
 'email':web.EMAIL_BACKEND,
 'context':web.TEMPLATES[0]['OPTIONS']['context_processors'],
 'normal_context':dev.TEMPLATES[0]['OPTIONS']['context_processors'],
 'middleware':web.MIDDLEWARE,
}))
"""
        return subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
            env={**os.environ, "ROKKAD_REHEARSAL_DB_NAME":database}, timeout=30)

    def test_browser_settings_are_isolated_without_changing_normal_settings(self):
        result = self.inspect_settings("rokkad_baseline_rehearsal_fixture")
        self.assertEqual(result.returncode, 0, result.stderr)
        values = json.loads(result.stdout)
        self.assertEqual(values['database'], 'rokkad_baseline_rehearsal_fixture')
        self.assertEqual(values['normal_database'], 'rokkad_shared_dev')
        self.assertEqual(values['hosts'], ['127.0.0.1', 'localhost', '[::1]'])
        self.assertEqual(values['cookies'], ['rokkad_rehearsal_session','rokkad_rehearsal_csrf'])
        self.assertEqual(values['secure'], [False,False,False])
        self.assertEqual(values['normal_cookies_secure'], [True,True])
        self.assertEqual(values['storage'], 'django.core.files.storage.FileSystemStorage')
        self.assertIn('rokkad_baseline_rehearsal_fixture', values['media'])
        self.assertEqual(values['cache'], 'django.core.cache.backends.locmem.LocMemCache')
        self.assertEqual(values['email'], 'django.core.mail.backends.locmem.EmailBackend')
        context = 'django_project.context_processors.rehearsal_environment'
        self.assertIn(context, values['context'])
        self.assertNotIn(context, values['normal_context'])
        self.assertNotIn('debug_toolbar.middleware.DebugToolbarMiddleware', values['middleware'])

    def test_normal_or_unspecified_database_is_rejected(self):
        for name in ('rokkad_shared_dev', ''):
            with self.subTest(name=name):
                result = self.inspect_settings(name)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('ROKKAD_REHEARSAL_DB_NAME must start with', result.stderr)

    def test_banner_requires_explicit_rehearsal_setting(self):
        with override_settings(REHEARSAL_BROWSER=False):
            self.assertEqual(rehearsal_environment(None), {'rehearsal_browser':False})
        with override_settings(REHEARSAL_BROWSER=True):
            self.assertEqual(rehearsal_environment(None), {'rehearsal_browser':True})
