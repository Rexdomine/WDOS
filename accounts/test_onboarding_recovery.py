"""Real-browser recovery regressions; route controls delay/abort real requests."""
from concurrent.futures import ThreadPoolExecutor

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import close_old_connections
from django.test import override_settings
from playwright.sync_api import sync_playwright, expect

from . import services
from .models import OnboardingDraft, OnboardingEvent
from .test_onboarding_submission import TEST_POLICY


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    STORAGES={'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
    SESSION_COOKIE_SECURE=False, CSRF_COOKIE_SECURE=False,
)
class OnboardingRecoveryBrowserTests(StaticLiveServerTestCase):
    password = 'a genuinely long WDOS example passphrase!'

    def setUp(self):
        self.account = services.register('Browser Member', 'recovery@example.org', self.password)
        _, code = services.issue_token(self.account, 'verify')
        self.assertTrue(services.verify_contact(self.account.pk, code))
        self.pw = sync_playwright().start()
        self.addCleanup(self.pw.stop)
        from pathlib import Path
        local_browser = Path('/opt/data/.cache/ms-playwright/chromium-1187/chrome-linux/chrome')
        options = {'executable_path': str(local_browser)} if local_browser.exists() else {}
        self.browser = self.pw.chromium.launch(headless=True, args=['--no-sandbox'], **options)
        self.addCleanup(self.browser.close)
        self.page = self.browser.new_page()
        self.page.set_default_timeout(7000)
        self.page.goto(self.live_server_url + '/auth/login/')
        self.page.fill('[name=email]', self.account.email)
        self.page.fill('[name=password]', self.password)
        self.page.click('button[type=submit]')
        self.page.wait_for_load_state('networkidle')
        self.page.goto(self.live_server_url + '/onboarding/1/')
        expect(self.page.locator('#onboarding-form')).to_be_visible()

    def next(self):
        self.page.click('button[name=action][value=continue]')

    def read_draft(self):
        def query():
            close_old_connections()
            try:
                draft = OnboardingDraft.objects.get(account_id=self.account.pk)
                return draft.revision, draft.next_step, draft.state, list(
                    OnboardingEvent.objects.filter(draft=draft).values_list('event', flat=True)
                )
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(query).result()

    def test_payload_and_valid_save(self):
        p = self.page
        p.select_option('[name=reading]', 'standard')
        with p.expect_request(lambda r: r.method == 'POST') as info:
            self.next()
        request = info.value
        self.assertEqual(request.url, self.live_server_url + '/onboarding/1/')
        body = request.post_data or ''
        for name in ('revision', 'csrfmiddlewaretoken', 'action', 'language', 'reading'):
            self.assertIn('name="' + name + '"', body)
        self.assertIn('continue', body)
        p.wait_for_url('**/onboarding/2/')
        expect(p.locator('[name=email]')).to_be_disabled()

    def test_delayed_post_cancel_waits_then_reads_back(self):
        p = self.page
        held = []
        def hold(route):
            if route.request.method == 'POST':
                held.append(route)
            else:
                route.continue_()
        p.route('**/onboarding/1/', hold)
        self.next()
        expect(p.locator('#onboarding-loading')).to_be_visible()
        expect(p.locator('[name=language]')).to_be_disabled()
        p.click('[data-loading-cancel]')
        expect(p.locator('[name=language]')).to_be_disabled()
        self.assertEqual(len(held), 1)
        held[0].continue_()
        expect(p.locator('[name=full_name]')).to_be_enabled()
        expect(p.locator('#onboarding-loading')).to_be_hidden()
        self.assertEqual(p.url, self.live_server_url + '/onboarding/2/')
        self.assertEqual(p.locator('[name=revision]').input_value(), '1')

    def test_lost_response_after_step1_commit_retries_canonical_get_without_post(self):
        p = self.page
        post_count = []
        def lose(route):
            if route.request.method == 'POST':
                post_count.append(route.request)
                route.fetch(max_redirects=0)
                route.abort(error_code='connectionreset')
            else:
                route.continue_()
        p.route('**/onboarding/1/', lose)
        self.next()
        expect(p.locator('#onboarding-interrupted')).to_be_visible()
        revision, next_step, state, events = self.read_draft()
        self.assertEqual((revision, next_step, state), (1, 2, 'draft'))
        self.assertEqual(events, ['draft_saved'])
        p.unroute('**/onboarding/1/')
        with p.expect_request(lambda r: r.method == 'GET' and r.url.endswith('/onboarding/')):
            p.click('[data-recovery-retry]')
        p.wait_for_url('**/onboarding/2/')
        self.assertEqual(p.locator('[name=revision]').input_value(), '1')
        self.assertEqual(len(post_count), 1)
        self.assertEqual(self.read_draft(), (1, 2, 'draft', ['draft_saved']))

    @override_settings(WDOS_ONBOARDING_POLICY=TEST_POLICY)
    def test_lost_response_after_step7_commit_recovers_to_step8_once(self):
        p = self.page
        steps = [
            {'[name=language]': 'en', '[name=timezone]': 'UTC', '[name=reading]': 'standard'},
            {'[name=full_name]': 'Amara Ézè', '[name=preferred_name]': 'Amara'},
            {'[name=eligibility]': 'test-adult', '[name=network]': 'WGMN', '[name=eligibility_confirmed]': True},
            {'[name=country]': 'Test Country', '[name=region]': 'Test Region', '[name=district]': 'Test District'},
            {'[name=interests]': 'Mentoring', '[name=skills]': 'Facilitation', '[name=community_connection]': 'Programme participant', '[name=availability]': 'Occasional'},
            {'[name=privacy_ack]': True, '[name=optional_updates]': False, '[name=channel]': 'email'},
        ]
        for fields in steps:
            for selector, value in fields.items():
                if isinstance(value, bool):
                    if value: p.check(selector)
                elif p.locator(selector).evaluate("e => e.tagName") == 'SELECT':
                    p.select_option(selector, value)
                else:
                    p.fill(selector, value)
            if '[name=privacy_ack]' in fields:
                p.locator('[name=notice_digest]').input_value()
            self.next()
            p.wait_for_load_state('networkidle')
        p.check('[name=review_confirmed]')
        p.route('**/onboarding/7/', lambda route: (route.fetch(max_redirects=0), route.abort(error_code='connectionreset')) if route.request.method == 'POST' else route.continue_())
        self.next()
        expect(p.locator('#onboarding-interrupted')).to_be_visible()
        revision, next_step, state, events = self.read_draft()
        self.assertEqual((revision, next_step, state), (7, 8, 'review_needed'))
        self.assertEqual(events.count('submitted'), 1)
        p.unroute('**/onboarding/7/')
        with p.expect_request(lambda r: r.method == 'GET' and r.url.endswith('/onboarding/')):
            p.click('[data-recovery-retry]')
        p.wait_for_url('**/onboarding/8/')
        self.assertEqual(self.read_draft()[3].count('submitted'), 1)

    def test_aborted_post_retry_is_get_and_handlers_rebind(self):
        p = self.page
        p.route('**/onboarding/1/', lambda route: route.abort() if route.request.method == 'POST' else route.continue_())
        self.next()
        expect(p.locator('#onboarding-interrupted')).to_be_visible()
        expect(p.locator('[name=language]')).to_be_disabled()
        p.unroute('**/onboarding/1/')
        with p.expect_request('**/onboarding/1/') as info:
            p.click('[data-recovery-retry]')
        self.assertEqual(info.value.method, 'GET')
        expect(p.locator('[name=language]')).to_be_enabled()
        # A second abort proves listeners are rebound on the returned server HTML.
        p.route('**/onboarding/1/', lambda route: route.abort())
        self.next()
        expect(p.locator('#onboarding-interrupted')).to_be_visible()
        expect(p.locator('[name=language]')).to_be_disabled()

    def test_conflict_html_is_retained_and_second_submit_enhanced(self):
        p = self.page
        p.locator('[name=revision]').evaluate('e => e.value = "999"')
        with p.expect_response(lambda r: r.request.method == 'POST') as response:
            self.next()
        self.assertEqual(response.value.status, 409)
        expect(p.get_by_text('Another change needs review', exact=True)).to_be_visible()
        expect(p.locator('[name=language]')).to_be_enabled()
        p.route('**/onboarding/1/', lambda route: route.abort())
        self.next()
        expect(p.locator('#onboarding-interrupted')).to_be_visible()

    def test_invalid_back_and_disabled_identity(self):
        p = self.page
        p.goto(self.live_server_url + '/onboarding/2/')
        expect(p.locator('[name=email]')).to_be_disabled()
        p.fill('[name=full_name]', '')
        with p.expect_response(lambda r: r.request.method == 'POST') as response:
            p.click('button[name=action][value=back]')
        # formnovalidate bypasses browser validation, not authoritative server validation.
        self.assertEqual(response.value.status, 422)
        expect(p.get_by_text('This field is required.', exact=True)).to_be_visible()
        expect(p.locator('[name=email]')).to_be_disabled()
        expect(p.locator('[name=full_name]')).to_have_value('')
