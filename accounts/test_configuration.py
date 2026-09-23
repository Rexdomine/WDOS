"""Settings import contract; no database or provider access."""
import os
import subprocess
import sys
from django.test import SimpleTestCase


class ProductionOriginTests(SimpleTestCase):
    def load(self, origin=None, environment='production'):
        env = {k: v for k, v in os.environ.items() if k not in ('DATABASE_URL', 'WDOS_PUBLIC_ORIGIN', 'WDOS_BREVO_API_KEY', 'WDOS_EMAIL_FROM')}
        env['WDOS_ENVIRONMENT'] = environment
        if origin is not None:
            env['WDOS_PUBLIC_ORIGIN'] = origin
        return subprocess.run([sys.executable, '-c', 'from wdos_project.settings import WDOS_PUBLIC_ORIGIN; print(WDOS_PUBLIC_ORIGIN)'], env=env, text=True, capture_output=True, timeout=10)

    def test_production_requires_explicit_non_staging_https_origin(self):
        for origin in (None, '', 'https://wdos-staging.onrender.com', 'http://wdos.example.org', 'https://', 'https://user:pass@wdos.example.org', 'https://wdos.example.org/#proof'):
            with self.subTest(origin=origin):
                result = self.load(origin)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('WDOS_PUBLIC_ORIGIN', result.stderr)

    def test_production_explicit_origin_is_used(self):
        result = self.load('https://wdos.example.org')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'https://wdos.example.org')

    def test_staging_default_is_preserved(self):
        result = self.load(environment='staging')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'https://wdos-staging.onrender.com')
