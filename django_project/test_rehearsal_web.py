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
        with override_settings(REHEARSAL_BROWSER=False, TICKET_TEMPLATE_SANDBOX=False):
            self.assertEqual(rehearsal_environment(None), {'rehearsal_browser':False, 'ticket_template_sandbox':False})
        with override_settings(REHEARSAL_BROWSER=True, TICKET_TEMPLATE_SANDBOX=False):
            self.assertEqual(rehearsal_environment(None), {'rehearsal_browser':True, 'ticket_template_sandbox':False})

    def test_billing_settings_isolate_keys_database_cookies_and_delivery(self):
        code = """
import json
from unittest.mock import patch
with patch('scripts.billing_rehearsal_credentials.read_private_json', side_effect=[
        {'key_id':'rzp_test_fixture', 'key_secret':'fixture'},
        {'django_secret':'fixture-local', 'webhook_secret':'fixture-webhook'}]):
    from django_project.settings import billing_rehearsal as web, dev
print(json.dumps({
 'database':web.DATABASES['default']['NAME'], 'normal_database':dev.DATABASES['default']['NAME'],
 'checkout':web.BILLING_CHECKOUT_ENABLED, 'trials':web.BILLING_ALLOW_TRIAL_START,
 'debug':web.DEBUG, 'mail':web.PLATFORM_EMAIL_ENABLED,
 'ses_keys':[web.PLATFORM_SES_ACCESS_KEY_ID, web.PLATFORM_SES_SECRET_ACCESS_KEY],
 'key':web.RAZORPAY_KEY_ID, 'secret_is_local':web.SECRET_KEY == 'fixture-local',
 'cookies':[web.SESSION_COOKIE_NAME,web.CSRF_COOKIE_NAME],
 'banner':web.BILLING_REHEARSAL,
}))
"""
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
            env={**os.environ, 'ROKKAD_REHEARSAL_DB_NAME':'rokkad_baseline_rehearsal_billing_fixture',
                 'DB_HOST':'127.0.0.1'}, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        values = json.loads(result.stdout)
        self.assertEqual(values['database'], 'rokkad_baseline_rehearsal_billing_fixture')
        self.assertEqual(values['normal_database'], 'rokkad_shared_dev')
        self.assertTrue(values['checkout'])
        self.assertFalse(values['trials'])
        self.assertFalse(values['debug'])
        self.assertFalse(values['mail'])
        self.assertEqual(values['ses_keys'], ['', ''])
        self.assertEqual(values['key'], 'rzp_test_fixture')
        self.assertTrue(values['secret_is_local'])
        self.assertEqual(values['cookies'], ['rokkad_billing_rehearsal_session','rokkad_billing_rehearsal_csrf'])
        self.assertTrue(values['banner'])

    @override_settings(BILLING_REHEARSAL=True, REHEARSAL_BROWSER=True)
    def test_billing_banner_identifies_fictional_test_data(self):
        self.assertTrue(rehearsal_environment(None)['billing_rehearsal'])
