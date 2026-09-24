import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from . import services
from .locale import catalog
from .models import Account, ActionToken, EmailIntent, Person


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AuthUIStateRegressionTests(TestCase):
    password = 'a genuinely long WDOS example passphrase!'

    def register_pending(self, email='pending@example.org'):
        response = self.client.post('/auth/register/', {
            'name': 'Pending Example', 'email': email, 'password': self.password,
        })
        self.assertRedirects(response, '/auth/verify/')
        return Account.objects.get(email=email)

    def create_active(self, email='active@example.org', privileged=False):
        account = services.register('Active Example', email, self.password)
        token, code = services.issue_token(account, 'verify')
        self.assertTrue(services.verify_contact(account.pk, code))
        account.refresh_from_db()
        if privileged:
            account.user.is_staff = True
            account.user.save(update_fields=['is_staff'])
        return account

    def login(self, account, client=None):
        return (client or self.client).post('/auth/login/', {
            'email': account.email, 'password': self.password,
        })

    def test_public_help_and_policy_routes_are_supplemental_not_canonical_ids(self):
        expected = {
            'help': ('HELP', 'Help with your WDOS account'),
            'privacy': ('PRIVACY', 'Privacy notice'),
            'terms': ('TERMS', 'Terms'),
        }
        for name, (screen, text) in expected.items():
            response = self.client.get(reverse('accounts:' + name))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['screen'], screen)
            self.assertContains(response, text)
            self.assertContains(response, 'https://thewoddi.org/contact.html')
            self.assertNotContains(response, 'AUTH-10')

    def test_help_is_actionable_and_explicitly_has_no_secret_or_bypass_path(self):
        response = self.client.get(reverse('accounts:help'))
        self.assertContains(response, '/auth/recover/')
        self.assertContains(response, 'https://thewoddi.org/contact.html')
        self.assertContains(response, 'Never share a password')
        self.assertContains(response, 'cannot bypass ownership checks or MFA')
        self.assertNotContains(response, 'submit a review')

    def test_all_public_screens_have_language_privacy_terms_help_and_cream_notice(self):
        paths = ('/', '/auth/login/', '/auth/register/', '/auth/verify/',
                 '/auth/recover/', '/auth/reset/', '/auth/status/')
        for path in paths:
            response = self.client.get(path)
            self.assertContains(response, 'class="language-picker"')
            self.assertContains(response, 'class="notice cream-notice"')
            self.assertContains(response, '/auth/privacy/')
            self.assertContains(response, '/auth/terms/')
            self.assertContains(response, '/auth/help/')
            self.assertContains(response, 'WODDI Digital Operating System')
            self.assertNotContains(response, '© 2026')

    def test_welcome_and_registration_navigation_are_present_without_duplicates(self):
        welcome = self.client.get('/')
        self.assertContains(welcome, 'Join as a member')
        self.assertContains(welcome, 'I already have an account')
        registration = self.client.get('/auth/register/')
        self.assertContains(registration, 'Already registered? Sign in')
        login = self.client.get('/auth/login/')
        self.assertContains(login, 'Create an account')
        self.assertNotContains(login, '>Back to sign in<')
        self.assertNotContains(login, 'Use another route')

    def test_direct_reset_get_shows_localized_missing_link_and_hides_form(self):
        for lang in ('en', 'fr', 'pt', 'ar', 'sw'):
            response = Client().get('/auth/reset/?lang=' + lang)
            self.assertContains(response, catalog(lang)['reset_missing_title'])
            self.assertContains(response, 'href="/auth/recover/"')
            self.assertContains(response, '<div hidden data-reset-form>')
            self.assertNotContains(response, 'Proof:')
            if lang != 'en':
                self.assertNotContains(response, catalog('en')['reset_missing_title'])

    def test_missing_malformed_invalid_and_used_reset_proofs_are_safe_states(self):
        new_password = self.password + ' changed'
        for proof in ('', 'not-a-proof', 'not-a-uuid.secret', 'x' * 250):
            response = self.client.post('/auth/reset/?lang=fr', {
                'proof': proof, 'password': new_password, 'confirm': new_password,
            })
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, catalog('fr')['link_expired'])
            self.assertContains(response, '/auth/recover/')
            self.assertNotContains(response, 'name="password"')
            self.assertNotContains(response, proof) if proof else None

        self.client.cookies['wdos_language'] = 'en'
        account = self.create_active('used-reset@example.org')
        token, secret = services.issue_token(account, 'reset')
        proof = f'{token.pk}.{secret}'
        first = self.client.post('/auth/reset/', {
            'proof': proof, 'password': new_password, 'confirm': new_password,
        })
        self.assertContains(first, 'Password updated')
        used = self.client.post('/auth/reset/', {
            'proof': proof, 'password': new_password + ' again', 'confirm': new_password + ' again',
        })
        self.assertContains(used, 'Link expired')
        self.assertNotContains(used, 'name="password"')
        self.assertNotContains(used, proof)

    def test_valid_reset_retry_does_not_echo_proof_in_response(self):
        account = self.create_active('retry-reset@example.org')
        token, secret = services.issue_token(account, 'reset')
        proof = f'{token.pk}.{secret}'
        response = self.client.post('/auth/reset/', {
            'proof': proof, 'password': self.password + ' one', 'confirm': self.password + ' two',
        })
        self.assertContains(response, 'Passwords must match')
        self.assertContains(response, 'name="password"')
        self.assertNotContains(response, proof)
        response = self.client.post('/auth/reset/', {
            'proof': '', 'reset_flow': str(token.pk),
            'password': self.password + ' changed', 'confirm': self.password + ' changed',
        })
        self.assertContains(response, 'Password updated')

    def test_invalid_reset_submission_drops_proof_that_expired_before_error_render(self):
        account = self.create_active('expired-reset-error@example.org')
        token, secret = services.issue_token(account, 'reset')
        proof = f'{token.pk}.{secret}'
        self.client.session['reset_retry_proof'] = services.encrypt(proof)
        self.client.session.save()
        ActionToken.objects.filter(pk=token.pk).update(expires_at=timezone.now() - timedelta(seconds=1))

        response = self.client.post('/auth/reset/', {
            'password': 'one', 'confirm': 'two',
        })

        self.assertContains(response, 'Link expired')
        self.assertNotContains(response, 'name="password"')
        self.assertNotIn('reset_retry_proof', self.client.session)

    def test_expired_bound_reset_proof_renders_unusable_link_state_on_get(self):
        account = self.create_active('expired-bound-reset@example.org')
        token, secret = services.issue_token(account, 'reset')
        proof = f'{token.pk}.{secret}'
        response = self.client.post('/auth/reset/', {
            'preserve_fragment': '1', 'proof': proof,
        })
        flow_id = response.headers['X-Reset-Flow']
        ActionToken.objects.filter(pk=token.pk).update(expires_at=timezone.now() - timedelta(seconds=1))

        response = self.client.get('/auth/reset/?reset_flow=' + flow_id)

        self.assertContains(response, 'Link expired')
        self.assertContains(response, 'This password reset link can no longer be used.')
        self.assertNotContains(response, 'Recovery link required')
        self.assertNotContains(response, 'name="password"')
        self.assertNotIn('reset_retry_proof', self.client.session)

    @patch('accounts.views.services.reset_password')
    @patch('accounts.views.services.is_live_reset_proof', side_effect=[True, False])
    def test_reset_error_drops_proof_that_expires_during_password_validation(
            self, live_proof, reset_password):
        account = self.create_active('expired-during-reset-error@example.org')
        token, secret = services.issue_token(account, 'reset')
        proof = f'{token.pk}.{secret}'
        reset_password.side_effect = services.ValidationError('password rejected')

        response = self.client.post('/auth/reset/', {
            'proof': proof,
            'password': self.password + ' changed',
            'confirm': self.password + ' changed',
        })

        self.assertContains(response, 'Link expired')
        self.assertNotContains(response, 'name="password"')
        self.assertNotIn('reset_retry_proof', self.client.session)
        self.assertEqual(live_proof.call_count, 2)

    def test_invalid_fragment_drops_any_stale_retry_proof(self):
        account = self.create_active('stale-fragment@example.org')
        token, secret = services.issue_token(account, 'reset')
        stale_proof = f'{token.pk}.{secret}'
        session = self.client.session
        session['reset_retry_proof'] = services.encrypt(stale_proof)
        session.save()

        response = self.client.post('/auth/reset/', {
            'preserve_fragment': '1', 'proof': 'not-a-valid-proof',
        })

        self.assertEqual(response.status_code, 400)
        self.assertTrue(self.client.session.get('reset_retry_proof'))

    def test_verification_is_bound_masked_and_has_real_resend_cooldown(self):
        account = self.register_pending('recognisable@example.org')
        response = self.client.get('/auth/verify/')
        self.assertContains(response, 'r***@e***.org')
        self.assertContains(response, 'name="code"')
        self.assertNotContains(response, 'name="email"')
        self.assertContains(response, 'data-resend-issued-at=')
        self.assertContains(response, 'data-resend-button disabled')
        before = EmailIntent.objects.filter(account=account, token__purpose='verify').count()
        early = self.client.post('/auth/resend/')
        self.assertEqual(EmailIntent.objects.filter(account=account, token__purpose='verify').count(), before)
        self.assertContains(early, 'countdown')

        latest = ActionToken.objects.filter(account=account, purpose='verify').latest('created_at')
        ActionToken.objects.filter(pk=latest.pk).update(created_at=timezone.now() - timedelta(seconds=61))
        allowed = self.client.post('/auth/resend/')
        self.assertEqual(EmailIntent.objects.filter(account=account, token__purpose='verify').count(), before + 1)
        self.assertContains(allowed, 'same verified destination')
        self.assertContains(allowed, 'data-resend-button disabled')

    def test_unbound_verification_has_no_identity_form_or_resend(self):
        account = services.register('Unknown', 'unknown-binding@example.org', self.password)
        intent = EmailIntent.objects.get(account=account)
        code = json.loads(services.decrypt(intent.encrypted_payload))['textContent'].split(' is ')[1].split('.')[0]
        response = self.client.post('/auth/verify/', {'email': account.email, 'code': code})
        self.assertContains(response, 'Verification link unavailable')
        self.assertNotContains(response, 'name="code"')
        self.assertNotContains(response, 'data-resend-button')
        account.refresh_from_db()
        self.assertEqual(account.status, 'pending')

    def test_pending_password_login_restores_verify_action_and_bound_destination(self):
        account = self.register_pending('pending-login@example.org')
        response = self.login(account)
        self.assertRedirects(response, '/auth/status/')
        status = self.client.get('/auth/status/')
        self.assertContains(status, 'Verification pending')
        self.assertContains(status, 'href="/auth/verify/"')
        verify = self.client.get('/auth/verify/')
        self.assertContains(verify, 'p***@e***.org')
        self.assertNotContains(verify, 'name="email"')

    def test_success_states_remove_stale_forms_and_offer_truthful_next_action(self):
        account = self.register_pending('success-verify@example.org')
        intent = EmailIntent.objects.filter(account=account, token__purpose='verify').latest('created_at')
        code = json.loads(services.decrypt(intent.encrypted_payload))['textContent'].split(' is ')[1].split('.')[0]
        verified = self.client.post('/auth/verify/', {'code': code})
        self.assertContains(verified, 'Go to sign in')
        self.assertNotContains(verified, 'name="code"')
        self.assertNotContains(verified, 'data-resend-button')

        recovered = Client().post('/auth/recover/', {'email': 'nobody@example.org'})
        self.assertContains(recovered, 'Check your inbox')
        self.assertContains(recovered, 'Back to sign in')
        self.assertNotContains(recovered, 'name="email"')

    def test_mfa_setup_then_enrollment_order_and_lost_factor_support(self):
        account = self.create_active('mfa-setup@example.org', privileged=True)
        self.assertRedirects(self.login(account), '/auth/mfa/')
        initial = self.client.get('/auth/mfa/')
        self.assertContains(initial, 'Begin MFA setup')
        self.assertNotContains(initial, 'name="code"')
        self.assertNotContains(initial, '>Verify code<')

        enrollment = self.client.post('/auth/mfa/', {'begin': '1'})
        content = enrollment.content.decode()
        self.assertContains(enrollment, 'name="code"')
        self.assertLess(content.index('Add WDOS to your authenticator'), content.index('id_code'))

        account.refresh_from_db()
        account.mfa_secret = account.mfa_pending_secret
        account.mfa_pending_secret = ''
        account.mfa_pending_until = None
        account.save(update_fields=['mfa_secret', 'mfa_pending_secret', 'mfa_pending_until'])
        self.client.post('/auth/logout/')
        self.assertRedirects(self.login(account), '/auth/mfa/')
        challenge = self.client.get('/auth/mfa/')
        self.assertContains(challenge, 'name="code"')
        self.assertContains(challenge, 'Verify code')
        self.assertContains(challenge, 'Cannot access your authenticator?')
        self.assertContains(challenge, 'href="/auth/help/"')
        self.assertContains(challenge, 'support cannot bypass MFA')

    def test_expired_mfa_restart_renders_the_replacement_setup_form(self):
        account = self.create_active('mfa-expired-restart@example.org', privileged=True)
        account.mfa_pending_secret = services.encrypt('stale-secret')
        account.mfa_pending_until = timezone.now() - timedelta(seconds=1)
        account.save(update_fields=['mfa_pending_secret', 'mfa_pending_until'])
        self.assertRedirects(self.login(account), '/auth/mfa/')

        response = self.client.post('/auth/mfa/', {'begin': '1'})

        self.assertContains(response, 'name="code"')
        self.assertContains(response, 'Add WDOS to your authenticator')

    def test_already_linked_invitation_has_no_claim_form(self):
        account = self.create_active('linked@example.org')
        account.person = Person.objects.create(display_name='Linked person')
        account.save(update_fields=['person'])
        self.login(account)
        response = self.client.get('/auth/invitation/')
        self.assertContains(response, 'Continue to your account')
        self.assertNotContains(response, 'name="code"')
        self.assertNotContains(response, '>Claim record<')

    def test_invalid_invitation_has_an_actionable_help_route(self):
        account = self.create_active('invalid-invitation@example.org')
        self.login(account)
        response = self.client.post('/auth/invitation/', {
            'code': 'invalid-invitation', 'email': account.email,
        })
        self.assertContains(response, 'Get invitation help')
        self.assertContains(response, 'href="/auth/help/"')

    def test_restricted_and_expired_statuses_are_prominent_and_private(self):
        suspended = services.register('Secret Suspended Name', 'private-suspended@example.org', self.password)
        suspended.status = 'suspended'
        suspended.save(update_fields=['status'])
        response = self.login(suspended)
        self.assertRedirects(response, '/auth/status/')
        status = self.client.get('/auth/status/')
        self.assertContains(status, 'status-card status-suspended')
        self.assertContains(status, 'Get support')
        self.assertNotContains(status, suspended.display_name)
        self.assertNotContains(status, suspended.email)

        client = Client()
        session = client.session
        session['access_notice'] = 'expired'
        session.save()
        expired = client.get('/auth/status/')
        self.assertContains(expired, 'status-card status-expired')
        self.assertContains(expired, 'Sign in again')

    def test_new_ui_messages_are_localized_in_every_catalog(self):
        keys = (
            'help_page_title', 'privacy_title', 'terms_title', 'reset_missing_title',
            'lost_factor_title', 'verification_pending_title', 'resend_wait',
            'footer_privacy', 'footer_terms', 'footer_help', 'invited_email', 'remember_short',
        )
        for lang in ('fr', 'pt', 'ar', 'sw'):
            for key in keys:
                self.assertNotEqual(catalog(lang)[key], catalog('en')[key])


@override_settings(STORAGES={
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class ResetFragmentBrowserSemanticsTests(StaticLiveServerTestCase):
    def create_active(self, email):
        account = services.register('Browser Reset', email, 'a genuinely long WDOS example passphrase!')
        token, code = services.issue_token(account, 'verify')
        self.assertTrue(services.verify_contact(account.pk, code))
        return account

    def test_fragment_reveals_form_before_history_is_cleared(self):
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self.skipTest('Playwright is not installed')

        with sync_playwright() as playwright:
            installed = [Path(playwright.chromium.executable_path)]
            installed += sorted(Path('/opt/hermes/.playwright').glob(
                'chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell'
            ))
            installed = [candidate for candidate in installed if candidate.exists()]
            if not installed:
                self.skipTest('No local Chromium executable is available for fragment semantics')
            browser = playwright.chromium.launch(
                headless=True, executable_path=str(installed[-1]),
            )
            try:
                page = browser.new_page()
                account = services.register('Browser Reset', 'browser-reset@example.org', 'a genuinely long WDOS example passphrase!')
                verification, code = services.issue_token(account, 'verify')
                self.assertTrue(services.verify_contact(account.pk, code))
                token, secret = services.issue_token(account, 'reset')
                browser_proof = f'{token.pk}.{secret}'
                page.goto(self.live_server_url + '/auth/reset/#' + browser_proof)
                page.wait_for_url(lambda url: '#' not in url and 'reset_flow=' in url)
                self.assertTrue(page.locator('[data-reset-form]').is_visible())
                self.assertFalse(page.locator('[data-reset-missing]').is_visible())
                self.assertEqual(page.locator('#id_proof').input_value(), browser_proof)
                self.assertTrue(page.url.startswith(self.live_server_url + '/auth/reset/?reset_flow='))

                page.reload()
                self.assertTrue(page.locator('[data-reset-form]').is_visible())
                self.assertFalse(page.locator('[data-reset-missing]').is_visible())
            finally:
                browser.close()

    def test_script_uses_the_real_static_path_and_never_browser_storage(self):
        js = (Path(__file__).parent / 'static' / 'accounts' / 'auth.js').read_text(encoding='utf-8')
        self.assertIn('const fragment', js)
        self.assertIn('resetPanel.hidden = true', js)
        self.assertIn('data-resend-remaining', js)
        self.assertNotIn('Date.now()', js)
        self.assertIn('location.pathname + location.search', js)
        self.assertIn('preserve_fragment', js)
        self.assertIn('credentials: "same-origin"', js)
        self.assertNotIn('localStorage', js)
        self.assertNotIn('sessionStorage', js)

    def test_reset_fragment_guard_is_scoped_to_reset_screen(self):
        reset = self.client.get('/auth/reset/')
        login = self.client.get('/auth/login/')
        self.assertContains(reset, 'data-reset-form')
        self.assertIn('if (fragment && fragment !== \'main\' && !/^id_[A-Za-z0-9_-]+$/.test(fragment))', reset.content.decode())
        self.assertNotContains(login, 'data-reset-form')
        self.assertNotContains(login, "document.querySelector('[data-reset-form]')")

    def test_reset_fragment_bootstrap_ignores_in_page_anchors_and_keeps_rejection_state_mounted(self):
        account = services.register(
            'Bound Reset', 'bound-reset@example.org',
            'a genuinely long WDOS example passphrase!',
        )
        token, code = services.issue_token(account, 'verify')
        self.assertTrue(services.verify_contact(account.pk, code))
        token, secret = services.issue_token(account, 'reset')
        session = self.client.session
        session['reset_retry_proof'] = services.encrypt(f'{token.pk}.{secret}')
        session.save()

        response = self.client.get('/auth/reset/')
        self.assertContains(response, '<section class="state-card reset-missing" data-reset-missing hidden')
        self.assertContains(response, '<section class="state-card reset-invalid" data-reset-invalid hidden')

    def test_reset_bindings_are_isolated_by_flow_id(self):
        first = self.create_active('first-flow@example.org')
        second = self.create_active('second-flow@example.org')
        first_token, first_secret = services.issue_token(first, 'reset')
        second_token, second_secret = services.issue_token(second, 'reset')

        first_response = self.client.post('/auth/reset/', {
            'preserve_fragment': '1', 'proof': f'{first_token.pk}.{first_secret}',
        })
        second_response = self.client.post('/auth/reset/', {
            'preserve_fragment': '1', 'proof': f'{second_token.pk}.{second_secret}',
        })

        self.assertEqual(first_response.headers['X-Reset-Flow'], str(first_token.pk))
        self.assertEqual(second_response.headers['X-Reset-Flow'], str(second_token.pk))
        first_page = self.client.get('/auth/reset/?reset_flow=' + str(first_token.pk))
        second_page = self.client.get('/auth/reset/?reset_flow=' + str(second_token.pk))
        first_language_page = self.client.get('/auth/reset/?lang=fr&reset_flow=' + str(first_token.pk))
        self.assertContains(first_page, 'data-proof-bound="true"')
        self.assertContains(second_page, 'data-proof-bound="true"')
        self.assertContains(first_language_page, 'name="reset_flow" value="' + str(first_token.pk) + '"')

        js = (Path(__file__).parent / 'static' / 'accounts' / 'auth.js').read_text(encoding='utf-8')
        self.assertNotIn('if (resetInvalid && replacementFragment) resetInvalid.hidden = false;', js)
        self.assertIn('if (resetInvalid) resetInvalid.hidden = false;', js)

    def test_reset_fragment_is_bound_to_the_session_before_url_cleanup(self):
        account = services.register('Reset Fragment', 'reset-fragment@example.org', 'a genuinely long WDOS example passphrase!')
        verification, code = services.issue_token(account, 'verify')
        self.assertTrue(services.verify_contact(account.pk, code))
        token, secret = services.issue_token(account, 'reset')
        proof = f'{token.pk}.{secret}'
        response = self.client.post('/auth/reset/', {
            'preserve_fragment': '1', 'proof': proof,
        })
        self.assertEqual(response.status_code, 204)
        flow_id = response.headers['X-Reset-Flow']
        self.assertEqual(flow_id, str(token.pk))
        self.assertContains(self.client.get('/auth/reset/?reset_flow=' + flow_id), 'data-proof-bound="true"')
        self.assertTrue(self.client.session.get('reset_retry_proof'))
