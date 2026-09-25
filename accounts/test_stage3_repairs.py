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
        foundation = self.client.get('/')
        self.assertRedirects(foundation, '/foundation/')
        shell = self.client.get('/foundation/')
        self.assertContains(shell, 'action="/auth/logout/"')
        self.assertContains(shell, 'method="post"')
        self.assertContains(shell, 'name="csrfmiddlewaretoken"')
        self.assertContains(shell, 'Home')
        self.assertContains(shell, 'My activities')
        self.assertContains(shell, 'Records')
        self.assertContains(shell, 'Related information')
        self.assertContains(shell, 'Workspace actions')
        self.assertContains(shell, 'overflow-x: hidden')

    def test_foundation_response_is_private_and_uncacheable(self):
        account = self.create_active('foundation-cache@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Cached Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        response = self.client.get('/foundation/')
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        self.assertEqual(response['Referrer-Policy'], 'same-origin')

    def test_foundation_shell_has_styled_layout_and_bound_profile_menu(self):
        account = self.create_active('foundation-controls@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Foundation Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        html = self.client.get('/foundation/').content.decode()
        self.assertIn('data-profile-menu', html)
        self.assertIn('data-profile-trigger', html)
        self.assertIn('data-profile-panel', html)
        self.assertIn('aria-expanded="false"', html)
        self.assertIn('hidden', html)
        self.assertIn('/static/accounts/onboarding.', html)
        css = (Path(__file__).parent / 'static' / 'accounts' / 'design.css').read_text()
        self.assertIn('.foundation-shell', css)
        self.assertIn('.foundation-shell .content', css)

    def test_foundation_workspace_actions_have_real_targets(self):
        account = self.create_active('foundation-actions@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Action Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        html = self.client.get('/foundation/').content.decode()
        self.assertIn('id="activities"', html)
        self.assertIn('id="support"', html)
        self.assertIn('href="#activities"', html)
        self.assertIn('href="#support"', html)

    def test_foundation_logout_uses_persisted_locale_and_direction(self):
        account = self.create_active('accepted-locale@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Localized Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        expected = {'fr': ('fr', 'ltr', 'Se déconnecter'), 'pt': ('pt', 'ltr', 'Terminar sessão'),
                    'ar': ('ar', 'rtl', 'تسجيل الخروج'), 'sw': ('sw', 'ltr', 'Ondoka')}
        for lang, (html_lang, direction, label) in expected.items():
            self.client.cookies['wdos_language'] = lang
            shell = self.client.get('/foundation/')
            self.assertContains(shell, '<html lang="en" dir="ltr">')
            self.assertContains(shell, f'<span lang="{html_lang}" dir="{direction}">{label}</span>')

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

    def test_status_explainer_contains_distinct_context_from_status_sentence(self):
        account = self.create_active('status-explainer-context@example.org')
        self.login(account)
        response = self.client.get('/auth/status/')
        html = response.content.decode()
        popup = html.split('<div class="status-explainer-popup" role="note">', 1)[1].split('</div>', 1)[0]
        self.assertNotEqual(popup, response.context['status_text'])

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

    def test_mfa_setup_recovery_codes_continue_to_current_workspace(self):
        account = self.create_active('mfa-setup-destination@example.org')
        account.user.is_staff = True
        account.user.save(update_fields=['is_staff'])
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Accepted Setup Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.assertRedirects(self.login(account), '/auth/mfa/')
        setup = self.client.post('/auth/mfa/', {'begin': '1'})
        self.assertEqual(setup.status_code, 200)
        account.refresh_from_db()
        secret = services.decrypt(account.mfa_pending_secret)
        recovery = self.client.post('/auth/mfa/', {'code': pyotp.TOTP(secret).now()})
        self.assertEqual(recovery.status_code, 200)
        self.assertContains(recovery, 'href="/foundation/"')

    def test_profile_menu_preserves_avatar_fill_and_rtl_label_alignment(self):
        css = (Path(__file__).parent / 'static' / 'accounts' / 'onboarding.css').read_text()
        self.assertNotIn('.profile-trigger{border:0;background:transparent', css)
        self.assertIn('.profile-menu-panel{position:absolute;inset-inline-end:0;', css)
        self.assertNotIn('.profile-menu-panel{position:absolute;right:0;', css)
        self.assertIn('.profile-menu-panel button{width:100%;padding:9px;border:0;background:transparent;text-align:start;', css)
