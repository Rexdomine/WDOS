import json
from unittest.mock import patch
from django.core.management import call_command
from django.test import TestCase, override_settings
from .email_templates import render_email
from .models import EmailIntent, Person
from .services import decrypt, register, request_email


class TransactionalEmailTemplateTests(TestCase):
    @override_settings(WDOS_PUBLIC_ORIGIN='https://wdos.example.test')
    def test_verify_and_reset_payloads_are_branded_plaintext_and_expiring(self):
        account = register('Ada <Admin>', 'ada@example.test', 'A long unique phrase for WDOS 2026!')
        verify = json.loads(decrypt(EmailIntent.objects.get(account=account).encrypted_payload))
        self.assertIn('WODDI', verify['htmlContent'])
        self.assertIn('D4006A', verify['htmlContent'])
        self.assertIn('10 minutes', verify['htmlContent'])
        self.assertIn('verification code', verify['textContent'])
        # Complete the real verification transition before requesting recovery.
        import re
        from .services import verify_contact
        code = re.search(r'\b\d{6}\b', verify['textContent']).group()
        self.assertTrue(verify_contact(account.pk, code))
        request_email(account.email, 'reset')
        reset = json.loads(decrypt(EmailIntent.objects.filter(account=account, token__purpose='reset').latest('created_at').encrypted_payload))
        self.assertIn('/auth/reset/#', reset['textContent'])
        self.assertIn('/auth/reset/#', reset['htmlContent'])
        self.assertIn('30 minutes', reset['htmlContent'])
        self.assertIn('30 minutes', reset['textContent'])

    def test_template_autoescapes_code_and_url_without_external_assets(self):
        html = render_email('reset', {'url': 'https://wdos.example.test/auth/reset/#x.<script>', 'expiry_minutes': 30})
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertNotIn('http://', html)
        self.assertIn('<img', html.lower())
        self.assertIn('alt="WODDI"', html)
        self.assertIn('https://', html)
        self.assertIn('/static/accounts/assets/woddi-logo', html)

    @patch('accounts.management.commands.invite_person.secrets.token_urlsafe', return_value='invite<&')
    def test_invitation_payload_has_plaintext_and_escaped_html(self, token):
        person = Person.objects.create(display_name='Example Person')
        call_command('invite_person', person=str(person.pk), email='invite@example.test')
        intent = EmailIntent.objects.get(invitation__person=person)
        payload = json.loads(decrypt(intent.encrypted_payload))
        self.assertIn('invite<&', payload['textContent'])
        self.assertIn('invite&lt;&amp;', payload['htmlContent'])
        self.assertIn('seven days', payload['textContent'])
        self.assertIn('seven days', payload['htmlContent'])
        self.assertNotIn('http://', payload['htmlContent'])
