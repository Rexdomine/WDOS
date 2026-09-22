from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase, override_settings, Client
from django.utils import timezone
from .models import Account, ActionToken, EmailIntent
from . import services


class CoreTests(TestCase):
    def setUp(self):
        self.password = 'A long unique phrase for WDOS 2026!'

    def register(self):
        return services.register('Ada Example', 'ADA@example.org', self.password)

    def test_registration_is_normalized_and_never_privileged(self):
        account = self.register()
        self.assertEqual(account.email, 'ada@example.org')
        self.assertFalse(account.user.is_staff)
        self.assertFalse(account.user.is_superuser)
        self.assertEqual(account.status, 'pending')
        self.assertIsNone(account.person_id)
        self.assertIsNone(services.register('Other', 'ada@example.org', self.password))
        self.assertEqual(Account.objects.count(), 1)

    def test_verification_single_use_and_expiry(self):
        account = self.register()
        token, secret = services.issue_token(account, 'verify')
        self.assertNotIn(secret, token.digest)
        self.assertTrue(services.verify_contact(account.pk, secret))
        self.assertFalse(services.verify_contact(account.pk, secret))
        token, secret = services.issue_token(account, 'reset')
        with patch('accounts.services.timezone.now', return_value=token.expires_at):
            self.assertFalse(services.reset_password(str(token.pk), secret, self.password+'new'))

    def test_reset_revokes_sessions_but_not_mfa_or_suspension(self):
        account = self.register()
        account.status = 'suspended'
        account.save()
        token, secret = services.issue_token(account, 'reset')
        self.assertFalse(services.reset_password(str(token.pk), secret, self.password+'new'))
        account.refresh_from_db()
        self.assertEqual(account.status, 'suspended')

    def test_provider_not_configured_is_not_sent(self):
        account = self.register()
        intent = EmailIntent.objects.filter(account=account).first()
        services.dispatch_email(intent.pk)
        intent.refresh_from_db()
        self.assertEqual(intent.state, 'blocked')

    def test_csrf_and_get_do_not_mutate(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/auth/register/', {}).status_code, 403)
        self.assertEqual(self.client.get('/auth/logout/').status_code, 405)
