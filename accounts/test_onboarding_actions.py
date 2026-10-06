"""Automated audit tests for all buttons, links, loading, disabled, and recovery actions in Stage 3."""
from pathlib import Path
from django.conf import settings
from django.test import TestCase, override_settings

from . import services
from .models import Account, Membership, OnboardingConsent, OnboardingDraft, OnboardingEvent, Person
from .test_onboarding_submission import TEST_POLICY


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    STORAGES={'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
    WDOS_ONBOARDING_POLICY=TEST_POLICY,
)
class OnboardingButtonAndActionAuditTests(TestCase):
    password = 'a genuinely long WDOS example passphrase!'

    def setUp(self):
        self.account = services.register('Audit Member', 'audit@example.org', self.password)
        _, code = services.issue_token(self.account, 'verify')
        self.assertTrue(services.verify_contact(self.account.pk, code))
        self.account.refresh_from_db()
        self.client.post('/auth/login/', {'email': self.account.email, 'password': self.password})

    def _complete_steps_up_to(self, target_step):
        """Helper to fill steps up to target_step with valid test data."""
        steps_data = {
            1: {'language': 'en', 'timezone': 'UTC', 'reading': 'standard'},
            2: {'full_name': 'Audit User', 'preferred_name': 'Audit'},
            3: {'eligibility': 'test-adult', 'network': 'WGMN', 'eligibility_confirmed': 'on'},
            4: {'country': 'Test Country', 'region': 'Test Region', 'district': 'Test District', 'timezone': 'UTC'},
            5: {'interests': 'Community', 'skills': 'Leadership', 'community_connection': 'Direct', 'availability': 'Weekly'},
            6: {'privacy_ack': 'on', 'channel': 'email'},
        }
        for step in range(1, target_step):
            draft = OnboardingDraft.objects.filter(account=self.account).first()
            rev = draft.revision if draft else 0
            payload = {'revision': rev, 'action': 'continue', **steps_data[step]}
            if step == 6:
                step6_page = self.client.get('/onboarding/6/')
                payload['notice_digest'] = step6_page.context['form'].initial.get('notice_digest', '')
            resp = self.client.post(f'/onboarding/{step}/', payload)
            self.assertEqual(resp.status_code, 302, f'Step {step} failed to advance: {resp.status_code}')

    def test_button_inventory_and_intended_controls_present_on_steps_1_to_7(self):
        """Every step form has Continue, Back, Loading, Interrupted, and Profile Menu controls."""
        for step_num in range(1, 7):
            response = self.client.get(f'/onboarding/{step_num}/')
            self.assertEqual(response.status_code, 200)
            html = response.content.decode('utf-8')

            # Primary submit button
            self.assertIn('name="action"', html)
            self.assertIn('value="continue"', html)
            self.assertIn('class="btn primary"', html)

            # Back button
            self.assertIn('value="back"', html)
            self.assertIn('formnovalidate', html)

            # Recovery and loading controls
            self.assertIn('id="onboarding-loading"', html)
            self.assertIn('data-loading-cancel', html)
            self.assertIn('id="onboarding-interrupted"', html)
            self.assertIn('data-recovery-retry', html)

            # Profile menu and sign out action
            self.assertIn('data-profile-trigger', html)
            self.assertIn('action="/auth/logout/"', html)

            # Tabs
            self.assertIn('class="tabs"', html)
            self.assertIn(f'/onboarding/{step_num}/?tab=records', html)
            self.assertIn(f'/onboarding/{step_num}/?tab=history', html)

    def test_step_1_back_button_redirects_to_account_status(self):
        """On Step 1, clicking Back exits to the account status overview."""
        response = self.client.post('/onboarding/1/', {'revision': 0, 'action': 'back'})
        self.assertRedirects(response, '/auth/status/')

    def test_back_action_preserves_valid_fields_and_decrements_step(self):
        """Clicking Back on Step 2 saves field edits to draft and returns to Step 1."""
        response = self.client.post('/onboarding/2/', {
            'revision': 0,
            'action': 'back',
            'full_name': 'Preserved Name',
            'preferred_name': 'Preserved',
        })
        self.assertRedirects(response, '/onboarding/1/')
        draft = OnboardingDraft.objects.get(account=self.account)
        self.assertEqual(draft.data.get('full_name'), 'Preserved Name')
        self.assertEqual(draft.data.get('preferred_name'), 'Preserved')

    def test_save_and_resume_preserves_geography_and_timezone(self):
        """Advancing through Step 4 saves Country, Region, District, and Timezone, preserved on resume."""
        self._complete_steps_up_to(5)
        draft = OnboardingDraft.objects.get(account=self.account)
        self.assertEqual(draft.data.get('country'), 'Test Country')
        self.assertEqual(draft.data.get('region'), 'Test Region')
        self.assertEqual(draft.data.get('district'), 'Test District')
        self.assertEqual(draft.data.get('timezone'), 'UTC')

        # Back to Step 4 from Step 5
        response = self.client.post('/onboarding/5/', {'revision': draft.revision, 'action': 'back'})
        self.assertRedirects(response, '/onboarding/4/')

        # Start URL resumes to next_step
        start_resp = self.client.get('/onboarding/')
        self.assertRedirects(start_resp, '/onboarding/5/')

    def test_step_7_review_and_submission_actions(self):
        """Step 7 review button submits with confirmation and advances to Step 8."""
        self._complete_steps_up_to(7)
        response = self.client.get('/onboarding/7/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')

        # Has review confirmation checkbox and complete registration button
        self.assertIn('name="review_confirmed"', html)
        self.assertIn('value="continue"', html)
        self.assertIn('value="back"', html)

        # Back from review returns to step 6
        draft = OnboardingDraft.objects.get(account=self.account)
        back_resp = self.client.post('/onboarding/7/', {'revision': draft.revision, 'action': 'back'})
        self.assertRedirects(back_resp, '/onboarding/6/')

        # Submitting without checkbox fails validation
        fail_resp = self.client.post('/onboarding/7/', {'revision': draft.revision, 'action': 'continue'})
        self.assertEqual(fail_resp.status_code, 422)

        # Submitting with confirmation succeeds and advances to step 8
        submit_resp = self.client.post('/onboarding/7/', {
            'revision': draft.revision,
            'action': 'continue',
            'review_confirmed': 'on',
        })
        self.assertRedirects(submit_resp, '/onboarding/8/')

        draft.refresh_from_db()
        self.assertIn(draft.state, ('submitted', 'review_needed', 'accepted'))
        self.assertTrue(draft.events.filter(event='submitted').exists())

    def test_first_use_step_8_pending_review_disables_dashboard_and_guards_app(self):
        """When draft is pending review, Step 8 dashboard button is disabled and /app is protected."""
        self._complete_steps_up_to(7)
        draft = OnboardingDraft.objects.get(account=self.account)
        self.client.post('/onboarding/7/', {
            'revision': draft.revision,
            'action': 'continue',
            'review_confirmed': 'on',
        })
        draft.refresh_from_db()

        # Step 8 page
        response = self.client.get('/onboarding/8/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')

        # Dashboard button is disabled with aria-disabled
        self.assertIn('disabled', html)
        self.assertIn('aria-disabled="true"', html)

        # Timeline links exist
        self.assertIn('/onboarding/4/', html)
        self.assertIn('/onboarding/2/', html)
        self.assertIn('/auth/invitation/', html)
        self.assertIn('/auth/help/', html)

        # Back button points to step 7
        self.assertIn('/onboarding/7/', html)

        # Direct access to /app and /foundation/ is rejected before acceptance
        app_resp = self.client.get('/app')
        self.assertRedirects(app_resp, '/auth/status/')
        foundation_resp = self.client.get('/foundation/')
        self.assertRedirects(foundation_resp, '/auth/status/')

    def test_first_use_step_8_accepted_activates_dashboard_link_and_permits_app(self):
        """When draft is accepted with membership, Step 8 dashboard button links to /app and /app is granted."""
        self._complete_steps_up_to(7)
        draft = OnboardingDraft.objects.get(account=self.account)
        self.client.post('/onboarding/7/', {
            'revision': draft.revision,
            'action': 'continue',
            'review_confirmed': 'on',
        })
        draft.refresh_from_db()

        # Accept the draft and create linked membership
        person = Person.objects.create(display_name='Audit User')
        consent = draft.consents.first()
        Membership.objects.create(
            draft=draft,
            person=person,
            network='WGMN',
            home={'label': 'Lagos Central'},
            consent=consent,
            policy_digest='p',
            approved_by=self.account,
        )
        draft.state = 'accepted'
        draft.save(update_fields=['state'])

        # Step 8 page now has active link to /app
        response = self.client.get('/onboarding/8/')
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('href="/app"', html)
        self.assertNotIn('disabled aria-disabled="true"', html)

        # Back button now targets records tab
        self.assertIn('href="/onboarding/8/?tab=records"', html)

        # /app loads the foundation workspace shell
        app_resp = self.client.get('/app')
        self.assertEqual(app_resp.status_code, 200)
        self.assertContains(app_resp, 'class="foundation-shell"')

    def test_duplicate_submission_blocked_by_revision_conflict(self):
        """Stale revision submissions return 409 conflict, preventing duplicate action."""
        response = self.client.post('/onboarding/1/', {
            'revision': 999,
            'action': 'continue',
            'language': 'en',
            'timezone': 'UTC',
            'reading': 'standard',
        })
        self.assertEqual(response.status_code, 409)

    def test_tab_actions_render_overview_records_and_history(self):
        """User can navigate between Overview, Records, and History tabs without losing state."""
        self._complete_steps_up_to(3)

        overview_resp = self.client.get('/onboarding/3/')
        self.assertEqual(overview_resp.status_code, 200)

        records_resp = self.client.get('/onboarding/3/?tab=records')
        self.assertEqual(records_resp.status_code, 200)
        self.assertContains(records_resp, 'Audit User')

        history_resp = self.client.get('/onboarding/3/?tab=history')
        self.assertEqual(history_resp.status_code, 200)
        self.assertContains(history_resp, 'data-history-event=')

    def test_button_disabled_and_loading_styles_present_in_css(self):
        """CSS provides clear disabled styling, loading spinner, and busy states."""
        css = (Path(settings.BASE_DIR) / 'accounts/static/accounts/onboarding.css').read_text(encoding='utf-8')
        self.assertIn('.btn:disabled', css)
        self.assertIn('aria-disabled="true"', css)
        self.assertIn('cursor: not-allowed', css)
        self.assertIn('.btn.is-loading', css)
        self.assertIn('aria-busy="true"', css)
        self.assertIn('btn-spin', css)

    def test_client_script_audit_guards_and_lifecycle_bindings(self):
        """JavaScript audit checks: re-binds on server response, closes selects on lock, guards recovery."""
        js = (Path(settings.BASE_DIR) / 'accounts/static/accounts/onboarding.js').read_text(encoding='utf-8')

        # replaceWithResponse re-binds all components
        self.assertIn('initializeSearchableDropdowns();', js)
        self.assertIn('initializeRecordTabs();', js)

        # lockControls closes open searchable selects
        self.assertIn('.searchable-select.is-open', js)
        self.assertIn('_searchableInstance.close()', js)

        # Active submitter tracking prevents duplicate clicks
        self.assertIn('activeSubmitter', js)
        self.assertIn('stopImmediatePropagation', js)

        # Recover pending guard prevents spamming try-again
        self.assertIn('pending = true', js)
        self.assertIn('finally {', js)

    def test_search_input_padding_prevents_text_overlapping_icon(self):
        """Search input has explicit 40px left padding to prevent typed text overlapping the search icon."""
        css = (Path(settings.BASE_DIR) / 'accounts/static/accounts/onboarding.css').read_text(encoding='utf-8')
        self.assertIn('.field .searchable-select-search-wrap input.searchable-select-search-input', css)
        self.assertIn('padding:6px 36px 6px 40px !important', css)
        self.assertIn('padding-inline-start:40px !important', css)
        self.assertIn('.searchable-select-search-icon{position:absolute;left:20px;top:50%', css)
        self.assertIn('z-index:3', css)

    def test_age_eligibility_shows_adult_and_youth_options_without_policy(self):
        """When policy is unconfigured, Step 3 provides Adult and Youth member tiers instead of only 'More information needed'."""
        with override_settings(WDOS_ONBOARDING_POLICY=None):
            from .onboarding_forms import NetworkForm
            form = NetworkForm()
            labels = [c[1] for c in form.fields['eligibility'].choices]
            self.assertIn('Select age eligibility', labels)
            self.assertIn('Adult Member (18+)', labels)
            self.assertIn('Youth Member (15–24)', labels)
            self.assertIn('More information needed', labels)

            # Step 3 GET response contains adult and youth choices in HTML and JSON script
            response = self.client.get('/onboarding/3/')
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Adult Member (18+)')
            self.assertContains(response, 'Youth Member (15–24)')
            self.assertContains(response, 'id="eligibility-data"')

            # Form submission succeeds with adult tier and WGMN network
            valid_form = NetworkForm(data={
                'eligibility': 'adult',
                'network': 'WGMN',
                'eligibility_confirmed': True,
            })
            self.assertTrue(valid_form.is_valid())

            # Mismatched network/eligibility triggers validation error
            mismatched_form = NetworkForm(data={
                'eligibility': 'adult',
                'network': 'WNNN',
                'eligibility_confirmed': True,
            })
            self.assertFalse(mismatched_form.is_valid())
            self.assertIn('More information needed', mismatched_form.errors.get('eligibility', []))

