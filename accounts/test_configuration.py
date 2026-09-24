"""Settings import contract; no database or provider access."""
import os
import json
import subprocess
import sys
from django.test import SimpleTestCase, override_settings

from .onboarding_policy import current_policy


class UploadBoundaryTests(SimpleTestCase):
    def test_request_body_cap_precedes_profile_photo_parsing(self):
        from django.conf import settings
        self.assertEqual(settings.DATA_UPLOAD_MAX_MEMORY_SIZE, 2 * 1024 * 1024)
        self.assertEqual(settings.FILE_UPLOAD_HANDLERS[0], 'wdos_project.upload_handlers.UploadSizeLimitHandler')

    def test_upload_handler_rejects_oversized_content_length(self):
        from django.core.files.uploadhandler import StopUpload
        from wdos_project.upload_handlers import UploadSizeLimitHandler, MAX_REQUEST_BYTES
        with self.assertRaises(StopUpload):
            UploadSizeLimitHandler().handle_raw_input(None, {}, MAX_REQUEST_BYTES + 1, b'--', 'utf-8')

    def test_upload_handler_rejects_oversized_chunk_stream(self):
        from django.core.files.uploadhandler import StopUpload
        from wdos_project.upload_handlers import UploadSizeLimitHandler, MAX_REQUEST_BYTES
        handler = UploadSizeLimitHandler()
        with self.assertRaises(StopUpload):
            handler.receive_data_chunk(b'x' * (MAX_REQUEST_BYTES + 1), 0)

    def test_upload_handler_allows_bounded_multipart_overhead(self):
        from wdos_project.upload_handlers import UploadSizeLimitHandler, MAX_UPLOAD_BYTES, MAX_REQUEST_BYTES
        handler = UploadSizeLimitHandler()
        handler.handle_raw_input(None, {}, MAX_UPLOAD_BYTES + 1024, b'--', 'utf-8')
        self.assertLess(MAX_UPLOAD_BYTES + 1024, MAX_REQUEST_BYTES)


class ProductionOriginTests(SimpleTestCase):
    def load(self, origin=None, environment='production'):
        env = {k: v for k, v in os.environ.items() if k not in ('DATABASE_URL', 'WDOS_PUBLIC_ORIGIN', 'WDOS_BREVO_API_KEY', 'WDOS_EMAIL_FROM')}
        env['WDOS_ENVIRONMENT'] = environment
        if origin is not None:
            env['WDOS_PUBLIC_ORIGIN'] = origin
        return subprocess.run([sys.executable, '-c', 'from wdos_project.settings import WDOS_PUBLIC_ORIGIN; print(WDOS_PUBLIC_ORIGIN)'], env=env, text=True, capture_output=True, timeout=10)

    def test_production_requires_explicit_non_staging_https_origin(self):
        for origin in (None, '', 'https://wdos-staging.onrender.com', 'https://wdos-staging.onrender.com.', 'https://wdos.example.org.', 'http://wdos.example.org', 'https://', 'https://user:pass@wdos.example.org', 'https://wdos.example.org/#proof', 'https://wdos.example.org?', 'https://wdos.example.org#'):
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

    def test_policy_scope_lengths_fit_access_grant_columns(self):
        base = {
            'version': 'operator-v1', 'approval_reference': 'approved', 'privacy_notice': 'notice',
            'review_role': 'reviewer', 'review_function': 'onboarding',
            'eligibility': [{'code': 'adult', 'label': 'Adult', 'network': 'WGMN', 'basis': 'verified'}],
            'homes': [{'code': 'lagos', 'label': 'Lagos', 'network': 'WGMN', 'country': 'Nigeria', 'region': 'Lagos', 'district': 'Ikeja', 'kind': 'chapter'}],
        }
        for key, value in (('review_role', 'r' * 65), ('review_function', 'f' * 65)):
            candidate = dict(base, **{key: value})
            with self.subTest(key=key), override_settings(WDOS_ONBOARDING_POLICY=candidate):
                self.assertIsNone(current_policy())
        candidate = dict(base, homes=[dict(base['homes'][0], country='N' * 101)])
        with override_settings(WDOS_ONBOARDING_POLICY=candidate):
            self.assertIsNone(current_policy())

        policy = {'version': 'operator-v1', 'approval_reference': 'approved', 'privacy_notice': 'notice', 'review_role': 'reviewer', 'review_function': 'onboarding', 'eligibility': [], 'homes': []}
        env = {k: v for k, v in os.environ.items() if k not in ('DATABASE_URL', 'WDOS_PUBLIC_ORIGIN', 'WDOS_BREVO_API_KEY', 'WDOS_EMAIL_FROM')}
        env['WDOS_ONBOARDING_POLICY_JSON'] = json.dumps(policy)
        result = subprocess.run([sys.executable, '-c', 'from wdos_project.settings import WDOS_ONBOARDING_POLICY; print(WDOS_ONBOARDING_POLICY["version"])'], env=env, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'operator-v1')
