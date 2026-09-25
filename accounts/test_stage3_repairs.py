from django.test import TestCase, override_settings
from pathlib import Path

import pyotp

from . import services
from .locale import catalog
from .models import Membership, OnboardingConsent, OnboardingDraft, Person


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class Stage3RepairTests(TestCase):
    password = 'a genuinely long WDOS example passphrase!'

    def create_active(self, email):
        account = services.register('Stage Three', email, self.password)
        token, code = services.issue_token(account, 'verify')
        self.assertTrue(services.verify_contact(account.pk, code))
        account.refresh_from_db()
        return account

    def login(self, account):
        return self.client.post('/auth/login/', {'email': account.email, 'password': self.password})

    def test_accepted_membership_login_and_root_open_foundation_shell(self):
        account = self.create_active('accepted-nav@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Accepted Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        response = self.login(account)
        self.assertRedirects(response, '/foundation/')
        self.assertRedirects(self.client.get('/'), '/foundation/')

    def test_status_explainer_is_localized_and_does_not_leak_restricted_identity(self):
        account = self.create_active('private-status@example.org')
        self.login(account)
        for lang in ('en', 'fr', 'pt', 'ar', 'sw'):
            response = self.client.get('/auth/status/?lang=' + lang)
            self.assertContains(response, 'data-status-explainer')
            self.assertContains(response, response.context['status_text'])
            self.assertNotContains(response, account.email)

    def test_status_explainer_accessible_label_uses_each_catalog(self):
        account = self.create_active('localized-status-label@example.org')
        self.login(account)
        for lang in ('en', 'fr', 'pt', 'ar', 'sw'):
            response = self.client.get('/auth/status/?lang=' + lang)
            expected = {
                'en': 'Why am I seeing this status?',
                'fr': 'Pourquoi est-ce que je vois ce statut ?',
                'pt': 'Por que estou vendo este status?',
                'ar': 'لماذا أرى هذه الحالة؟',
                'sw': 'Kwa nini ninaona hali hii?',
            }
            self.assertContains(response, f'aria-label="{expected[lang]}"')

    def test_enrolled_mfa_success_uses_current_workspace_destination(self):
        account = self.create_active('mfa-destination@example.org')
        secret = pyotp.random_base32()
        account.mfa_secret = services.encrypt(secret)
        account.save(update_fields=['mfa_secret'])
        self.login(account)
        response = self.client.post('/auth/mfa/', {'code': pyotp.TOTP(secret).now()})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/onboarding/1/')

    def test_onboarding_profile_menu_has_csrf_post_logout_for_desktop_and_mobile(self):
        account = self.create_active('menu@example.org')
        self.login(account)
        response = self.client.get('/onboarding/1/')
        self.assertContains(response, 'data-profile-menu')
        self.assertContains(response, 'action="/auth/logout/"')
        self.assertContains(response, 'method="post"')
        self.assertGreaterEqual(response.content.decode().count('name="csrfmiddlewaretoken"'), 2)
        self.assertContains(response, 'aria-haspopup="menu"')
        html = response.content.decode()
        mobile_head = html.split('<div class="mobile-head">', 1)[1].split('</div><div class="mobile-scope">', 1)[0]
        self.assertIn('data-profile-menu', mobile_head)

    def test_onboarding_script_rebinds_profile_menus_after_document_replacement(self):
        script = (Path(__file__).parent / 'static' / 'accounts' / 'onboarding.js').read_text()
        self.assertIn('function initializeProfileMenus()', script)
        self.assertIn('initializeProfileMenus();', script)
