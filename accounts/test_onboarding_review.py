from datetime import timedelta
from django.test import TestCase, override_settings
from django.utils import timezone
from . import test_onboarding_submission as fixtures
from .models import AccessGrant, OnboardingDraft, Person, Invitation

@override_settings(WDOS_ONBOARDING_POLICY=fixtures.TEST_POLICY, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ReviewTests(TestCase):
    password = fixtures.SubmissionTests.password
    create = fixtures.SubmissionTests.create
    login = fixtures.SubmissionTests.login
    fill = fixtures.SubmissionTests.fill
    submit = fixtures.SubmissionTests.submit

    def setUp(self):
        self.account = self.create()
        self.login(self.account)
        self.fill(policy=True)
        self.submit()
        self.reviewer = self.create('reviewer@example.org')
        self.login(self.reviewer)
        self.grant = AccessGrant.objects.create(account=self.reviewer, role='test-reviewer', function='test-onboarding', network='WGMN', geography='Test Country', expires_at=timezone.now()+timedelta(hours=1))
        session = self.client.session
        session['mfa_verified'] = True
        session.save()

    def approve(self, **changes):
        return self.client.post(f'/onboarding/review/{self.account.pk}/', {'decision': 'accept', 'revision': 7, 'home': 'test-home', 'identity_evidence': 'Test duplicate review completed', **changes})

    def test_scoped_reviewer_can_accept_once_without_privileged_grant(self):
        response = self.approve()
        self.assertEqual(response.status_code, 200)
        draft = OnboardingDraft.objects.get(account=self.account)
        self.assertEqual(draft.state, 'accepted')
        self.account.refresh_from_db()
        self.assertIsNotNone(self.account.person_id)
        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(self.account.accessgrant_set.count(), 0)
        self.assertEqual(draft.membership.network, 'WGMN')
        self.assertEqual(draft.membership.home['code'], 'test-home')
        replay = self.approve()
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(draft.events.filter(event='accepted').count(), 1)

    def test_wrong_network_reviewer_denied(self):
        self.grant.network = 'WNNN'; self.grant.save()
        self.assertEqual(self.approve().status_code, 403)

    def test_wrong_country_reviewer_denied(self):
        self.grant.geography = 'Another Country'; self.grant.save()
        self.assertEqual(self.approve().status_code, 403)

    def test_expired_grant_denied(self):
        self.grant.expires_at = timezone.now(); self.grant.save()
        self.assertEqual(self.approve().status_code, 403)

    def test_unknown_home_cannot_be_assigned(self):
        self.assertEqual(self.approve(home='guessed-home').status_code, 422)
        self.assertEqual(Person.objects.count(), 0)

    def test_identity_check_evidence_required(self):
        self.assertEqual(self.approve(identity_evidence='').status_code, 422)
        self.assertEqual(Person.objects.count(), 0)

    def test_invited_identity_requires_claim_not_new_person(self):
        person = Person.objects.create(display_name='Existing Person')
        Invitation.objects.create(person=person, email=self.account.email, digest='0'*64, expires_at=timezone.now()+timedelta(days=1))
        self.assertEqual(self.approve().status_code, 409)
        self.assertEqual(Person.objects.count(), 1)
        self.account.refresh_from_db()
        self.assertIsNone(self.account.person_id)

    def test_stale_submission_cannot_be_approved(self):
        self.assertEqual(self.approve(revision=6).status_code, 409)
        self.assertEqual(Person.objects.count(), 0)

    def test_approval_rejects_consent_choices_changed_after_submission(self):
        draft = OnboardingDraft.objects.get(account=self.account)
        consent = draft.consents.get()
        draft.data['optional_updates'] = True
        draft.save(update_fields=['data'])
        consent.optional_updates = False
        consent.save(update_fields=['optional_updates'])
        self.assertEqual(self.approve().status_code, 422)
        self.assertEqual(Person.objects.count(), 0)

    def test_mfa_required_for_review(self):
        session=self.client.session; session['mfa_verified']=False; session.save()
        self.assertEqual(self.approve().status_code, 403)

    def test_reviewer_cannot_read_unsubmitted_draft(self):
        draft = OnboardingDraft.objects.get(account=self.account)
        draft.state = 'draft'
        draft.save(update_fields=['state'])
        response = self.client.get(f'/onboarding/review/{self.account.pk}/')
        self.assertEqual(response.status_code, 409)

    def test_accepted_first_use_opens_dashboard(self):
        self.assertEqual(self.approve().status_code, 200)
        self.login(self.account)
        response = self.client.get('/onboarding/8/')
        self.assertContains(response, 'href="/app"')
        self.assertNotContains(response, 'disabled aria-disabled="true"')
        dashboard = self.client.get('/app')
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, 'A shared platform foundation.')

    def test_accepted_network_cannot_be_silently_changed(self):
        self.assertEqual(self.approve().status_code, 200)
        self.login(self.account)
        response = self.client.post('/onboarding/3/', {'revision': 8, 'network': 'WNNN', 'eligibility': 'test-adult', 'eligibility_confirmed': 'on'})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(OnboardingDraft.objects.get(account=self.account).membership.network, 'WGMN')
