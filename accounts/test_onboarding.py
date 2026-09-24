"""Stage 3 contract regressions: real authenticated requests and durable state."""
from django.test import TestCase, override_settings
from . import test_flows as _flow_helpers
from .models import Person


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class OnboardingEntryTests(TestCase):
    password = _flow_helpers.AuthFlows.password
    create = _flow_helpers.AuthFlows.create
    login = _flow_helpers.AuthFlows.login

    def test_anonymous_onboarding_requires_sign_in(self):
        response = self.client.get('/onboarding/')
        self.assertRedirects(response, '/auth/login/')

    def test_onboarding_renders_approved_first_screen(self):
        account = self.create()
        self.login(account)
        response = self.client.get('/onboarding/1/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Make WDOS feel like home')
        self.assertContains(response, 'Interface language')
        self.assertContains(response, 'Your timezone')
        self.assertContains(response, 'Reading preference')
        self.assertContains(response, 'Motion preference')
        self.assertNotContains(response, 'Ada Okafor')
        self.assertNotContains(response, 'UI REVIEW V1')
        self.assertEqual(response['Cache-Control'], 'no-store, private')

    def test_unlinked_account_does_not_create_a_second_person_on_get(self):
        account = self.create()
        self.login(account)
        before = Person.objects.count()
        self.client.get('/onboarding/1/')
        self.client.get('/onboarding/1/')
        self.assertEqual(Person.objects.count(), before)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class OnboardingDraftTests(TestCase):
    password = _flow_helpers.AuthFlows.password
    create = _flow_helpers.AuthFlows.create
    login = _flow_helpers.AuthFlows.login

    def setUp(self):
        self.account = self.create()
        self.login(self.account)

    def save(self, step, data, revision=0):
        return self.client.post(f'/onboarding/{step}/', {'revision': revision, 'action': 'continue', **data})

    def test_preferences_saved_and_resume_returns_next_step(self):
        response = self.save(1, {'language': 'en', 'timezone': 'Africa/Lagos', 'reading': 'standard'})
        self.assertRedirects(response, '/onboarding/2/')
        self.assertRedirects(self.client.get('/onboarding/'), '/onboarding/2/')
        page = self.client.get('/onboarding/1/')
        self.assertEqual(page.context['form'].initial['timezone'], 'Africa/Lagos')
        self.assertEqual(page.context['revision'], 1)

    def test_stale_tab_cannot_overwrite_saved_draft(self):
        self.save(1, {'language': 'en', 'timezone': 'Africa/Lagos', 'reading': 'standard'})
        response = self.save(1, {'language': 'en', 'timezone': 'UTC', 'reading': 'standard'})
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, 'Another change needs review', status_code=409)
        page = self.client.get('/onboarding/1/')
        self.assertEqual(page.context['form'].initial['timezone'], 'Africa/Lagos')

    def test_profile_email_cannot_be_changed_through_onboarding(self):
        response = self.save(2, {'full_name': 'Amara Ézè', 'preferred_name': 'Amara', 'email': 'attacker@example.org'})
        self.assertEqual(response.status_code, 302)
        self.account.refresh_from_db()
        self.assertEqual(self.account.email, 'ada@example.org')
        self.assertEqual(self.client.get('/onboarding/2/').context['form'].initial['full_name'], 'Amara Ézè')

    def test_invalid_draft_keeps_valid_fields_without_advancing(self):
        response = self.save(2, {'full_name': '', 'preferred_name': 'Amara'})
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, 'Check the highlighted information', status_code=422)
        page = self.client.get('/onboarding/2/')
        self.assertEqual(page.context['form'].initial['preferred_name'], 'Amara')

    def test_post_needs_expected_revision(self):
        response = self.client.post('/onboarding/1/', {'timezone': 'UTC'})
        self.assertEqual(response.status_code, 409)

    def test_unapproved_age_values_are_not_production_defaults(self):
        response = self.client.get('/onboarding/3/')
        self.assertContains(response, 'Find your network')
        self.assertNotContains(response, '30 years or older')
        self.assertNotContains(response, 'Approved age re-attestation')
        self.assertContains(response, 'WNNN')

    def test_network_never_grants_privileged_access(self):
        response = self.save(3, {'network': 'WNNN', 'eligibility': 'pending', 'eligibility_confirmed': 'on', 'role': 'HQ'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.account.accessgrant_set.count(), 0)
        self.assertEqual(self.client.get('/onboarding/3/').context['form'].initial['network'], 'WNNN')

    def test_country_home_is_not_inferred_from_sample(self):
        response = self.client.get('/onboarding/4/')
        self.assertContains(response, 'Connect with your local community')
        self.assertNotContains(response, 'Ikeja')
        self.assertNotContains(response, 'Lagos')

    def test_optional_consent_not_preselected(self):
        response = self.client.get('/onboarding/6/')
        self.assertContains(response, 'Your preferences, your choice')
        self.assertFalse(response.context['form'].initial.get('optional_updates', False))
        self.assertTrue(response.context['form'].fields['privacy_ack'].disabled)

    def test_cannot_submit_incomplete_registration(self):
        response = self.save(7, {'review_confirmed': 'on'})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.account.accessgrant_set.count(), 0)

    def test_unknown_step_not_relabelled_as_first_screen(self):
        self.assertEqual(self.client.get('/onboarding/99/').status_code, 404)

    def test_other_account_cannot_read_draft(self):
        self.save(2, {'full_name': 'Private First Member', 'preferred_name': 'Private'})
        other = self.create('other@example.org')
        self.login(other)
        response = self.client.get('/onboarding/2/?account=' + str(self.account.pk))
        self.assertNotContains(response, 'Private First Member')

    def test_suspended_account_cannot_write_draft(self):
        self.account.status = 'suspended'
        self.account.save(update_fields=['status'])
        self.assertRedirects(self.save(1, {'timezone': 'UTC'}), '/auth/login/')
