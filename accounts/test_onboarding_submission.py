"""Submission and consent invariants; configuration below is test-only, never seeded."""
from copy import deepcopy
from django.test import TestCase, override_settings
from django.urls import reverse
from . import test_flows as helpers
from .models import OnboardingDraft, Person

TEST_POLICY = {
    'version': 'test-only-v1', 'approval_reference': 'TEST FIXTURE - NOT WODDI POLICY',
    'privacy_notice': 'Test-only privacy notice. No production consent policy is implied.',
    'eligibility': [{'code': 'test-adult', 'label': 'Test eligibility group', 'network': 'WGMN', 'basis': 'Test attestation'}],
    'homes': [{'code': 'test-home', 'label': 'Test Chapter', 'network': 'WGMN', 'country': 'Test Country', 'region': 'Test Region', 'district': 'Test District', 'kind': 'chapter'}],
    'review_role': 'test-reviewer', 'review_function': 'test-onboarding',
}

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class SubmissionTests(TestCase):
    password = helpers.AuthFlows.password
    create = helpers.AuthFlows.create
    login = helpers.AuthFlows.login

    def setUp(self):
        self.account = self.create()
        self.login(self.account)

    def fill(self, policy=False):
        values = [
            {'language': 'en', 'timezone': 'UTC', 'reading': 'standard'},
            {'full_name': 'Amara Ézè', 'preferred_name': 'Amara'},
            {'network': 'WGMN', 'eligibility': 'test-adult' if policy else 'pending', 'eligibility_confirmed': 'on'},
            {'country': 'Test Country', 'region': 'Test Region', 'district': 'Test District'},
            {'interests': 'Mentoring', 'skills': 'Facilitation', 'community_connection': 'Programme participant', 'availability': 'Occasional'},
            {'privacy_ack': 'on' if policy else '', 'optional_updates': '', 'channel': 'email'},
        ]
        for number, value in enumerate(values, 1):
            if number == 6 and policy:
                value['notice_digest'] = self.client.get('/onboarding/6/').context['form'].initial['notice_digest']
            current_revision = OnboardingDraft.objects.filter(account=self.account).values_list('revision', flat=True).first() or 0
            response = self.client.post(f'/onboarding/{number}/', {'revision': current_revision, 'action': 'continue', **value})
            self.assertEqual(response.status_code, 302, (number, response.status_code))

    def submit(self, revision=6):
        return self.client.post('/onboarding/7/', {'revision': revision, 'review_confirmed': 'on', 'action': 'continue'})

    def test_no_policy_goes_to_review_not_automatic_membership(self):
        self.fill()
        response = self.submit()
        self.assertRedirects(response, '/onboarding/8/')
        draft = OnboardingDraft.objects.get(account=self.account)
        self.assertEqual(draft.state, 'review_needed')
        self.assertEqual(self.account.accessgrant_set.count(), 0)
        self.assertEqual(Person.objects.count(), 0)
        self.assertContains(self.client.get('/onboarding/8/'), 'More information needed')

    def test_lost_submit_response_replay_returns_same_submission(self):
        self.fill()
        first = self.submit()
        self.assertEqual(first.status_code, 302)
        draft = OnboardingDraft.objects.get(account=self.account)
        self.assertEqual(draft.state, 'review_needed')
        events = draft.events.count()
        replay = self.submit()
        self.assertRedirects(replay, '/onboarding/8/')
        draft.refresh_from_db()
        self.assertEqual(draft.events.count(), events)
        self.assertEqual(draft.revision, 7)

    def test_reload_does_not_resubmit(self):
        self.fill()
        self.submit()
        draft = OnboardingDraft.objects.get(account=self.account)
        self.assertEqual(draft.state, 'review_needed')
        events = draft.events.count()
        self.client.get('/onboarding/8/')
        self.client.get('/onboarding/8/')
        self.assertEqual(draft.events.count(), events)

    @override_settings(WDOS_ONBOARDING_POLICY=TEST_POLICY)
    def test_consent_stores_exact_version_and_unselected_optional_choice(self):
        self.fill(policy=True)
        response = self.submit()
        self.assertRedirects(response, '/onboarding/8/')
        draft = OnboardingDraft.objects.get(account=self.account)
        record = draft.consents.get()
        self.assertEqual(record.version, 'test-only-v1')
        self.assertEqual(record.notice, TEST_POLICY['privacy_notice'])
        self.assertTrue(record.privacy_ack)
        self.assertFalse(record.optional_updates)

    @override_settings(WDOS_ONBOARDING_POLICY=TEST_POLICY)
    def test_consent_after_edit_and_resubmission_uses_new_revision(self):
        self.fill(policy=True)
        self.submit()
        draft = OnboardingDraft.objects.get(account=self.account)
        first = draft.consents.get()
        self.login(self.account)
        response = self.client.post('/onboarding/2/', {'revision': 7, 'full_name': 'Edited Name', 'preferred_name': 'Edited'})
        self.assertEqual(response.status_code, 302)
        draft.refresh_from_db()
        self.assertEqual(draft.state, 'draft')
        self.fill(policy=True)
        draft.refresh_from_db()
        self.submit(revision=draft.revision)
        draft.refresh_from_db()
        self.assertEqual(draft.consents.count(), 2)
        self.assertGreater(draft.consents.order_by('-id').first().revision, first.revision)

    @override_settings(WDOS_ONBOARDING_POLICY=TEST_POLICY)
    def test_policy_change_requires_fresh_acknowledgement(self):
        self.fill(policy=True)
        updated = deepcopy(TEST_POLICY)
        updated['version'] = 'test-only-v2'
        with override_settings(WDOS_ONBOARDING_POLICY=updated):
            response = self.submit()
        self.assertEqual(response.status_code, 422)
        self.assertEqual(OnboardingDraft.objects.get(account=self.account).state, 'draft')

    def test_review_needed_edit_invalidates_prior_submission(self):
        self.fill()
        self.submit()
        draft = OnboardingDraft.objects.get(account=self.account)
        self.assertEqual(draft.state, 'review_needed')
        response = self.client.post('/onboarding/2/', {'revision': 7, 'full_name': 'Corrected Name', 'preferred_name': 'Corrected'})
        self.assertEqual(response.status_code, 302)
        draft.refresh_from_db()
        self.assertEqual(draft.state, 'draft')
        self.assertEqual(draft.data['full_name'], 'Corrected Name')

    def test_anonymous_reviewer_is_denied(self):
        self.client.logout()
        response = self.client.post(f'/onboarding/review/{self.account.pk}/', {'decision': 'accept'})
        self.assertEqual(response.status_code, 403)

    def test_ordinary_member_cannot_self_approve(self):
        self.fill()
        self.submit()
        response = self.client.post(f'/onboarding/review/{self.account.pk}/', {'decision': 'accept', 'revision': 7})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(OnboardingDraft.objects.get(account=self.account).state, 'review_needed')
