"""Real PostgreSQL races between onboarding approval and invitations."""
from datetime import timedelta
from io import StringIO
from threading import Event, Thread
from time import monotonic

from django.core import management
from django.core.management.base import CommandError
from django.db import close_old_connections, connection, connections, transaction
from django.test import Client, TransactionTestCase, override_settings
from django.utils import timezone

from . import services
from .models import AccessGrant, Account, EmailIntent, Invitation, OnboardingDraft, Person
from .test_onboarding_submission import TEST_POLICY



@override_settings(WDOS_ONBOARDING_POLICY=TEST_POLICY, PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class OnboardingIdentityConcurrencyTests(TransactionTestCase):
    """Both tests prove an actual database wait and assert both operation results."""

    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL concurrency gate; required in CI')
        self.password = 'a genuinely long WDOS example passphrase!'
        self.account = self._create('applicant@example.org')
        self.reviewer = self._create('reviewer@example.org')
        reviewer_client = Client()
        self.assertEqual(reviewer_client.post('/auth/login/', {'email': self.reviewer.email, 'password': self.password}).status_code, 302)
        AccessGrant.objects.create(account=self.reviewer, role='test-reviewer', function='test-onboarding', network='WGMN', geography='Test Country', expires_at=timezone.now() + timedelta(hours=1))
        session = reviewer_client.session
        session['mfa_verified'] = True
        session.save()
        self.reviewer_session_key = session.session_key
        self._submit_draft()
        self.person = Person.objects.create(display_name='Existing invited person')
        self.email_intent_baseline = EmailIntent.objects.count()
        self.errors = []
        self.winner_ready = Event()
        self.contender_started = Event()
        self.release = Event()
        self.winner_pid = None
        self.contender_pid = None

    def _create(self, email):
        account = services.register(email.split('@')[0], email, self.password)
        token, code = services.issue_token(account, 'verify')
        self.assertTrue(services.verify_contact(account.pk, code))
        account.refresh_from_db()
        return account

    def _submit_draft(self):
        client = Client()
        self.assertEqual(client.post('/auth/login/', {'email': self.account.email, 'password': self.password}).status_code, 302)
        values = [
            {'language': 'en', 'timezone': 'UTC', 'reading': 'standard'},
            {'full_name': 'Applicant Person', 'preferred_name': 'Applicant'},
            {'network': 'WGMN', 'eligibility': 'test-adult', 'eligibility_confirmed': 'on'},
            {'country': 'Test Country', 'region': 'Test Region', 'district': 'Test District'},
            {'interests': 'Mentoring', 'skills': 'Facilitation', 'community_connection': 'Programme participant', 'availability': 'Occasional'},
            {'privacy_ack': 'on', 'optional_updates': '', 'channel': 'email'},
        ]
        for number, value in enumerate(values, 1):
            revision = OnboardingDraft.objects.get(account=self.account).revision if OnboardingDraft.objects.filter(account=self.account).exists() else 0
            if number == 6:
                value['notice_digest'] = client.get('/onboarding/6/').context['form'].initial['notice_digest']
            self.assertEqual(client.post(f'/onboarding/{number}/', {'revision': revision, 'action': 'continue', **value}).status_code, 302)
        self.assertEqual(client.post('/onboarding/7/', {'revision': 6, 'review_confirmed': 'on', 'action': 'continue'}).status_code, 302)

    def _pid(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT pg_backend_pid()')
            return cursor.fetchone()[0]


    def _observe_wait(self, winner_pid, contender_pid):
        deadline = monotonic() + 12
        seen = None
        while monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT a.pid, pg_blocking_pids(a.pid), a.wait_event_type, a.wait_event
                    FROM pg_stat_activity a WHERE a.pid = %s AND a.state <> 'idle'
                """, [contender_pid])
                row = cursor.fetchone()
            if row and winner_pid in (row[1] or []) and row[2] == 'Lock':
                seen = row
                break
        self.assertIsNotNone(seen, f'no observed PostgreSQL lock wait: winner={winner_pid}, contender={contender_pid}, row={seen}')
        return seen

    def _join(self, *threads):
        for thread in threads:
            thread.join(timeout=15)
            self.assertFalse(thread.is_alive(), 'race thread did not terminate')
        self.assertFalse(self.errors, self.errors)

    def _approval(self):
        close_old_connections()
        try:
            with transaction.atomic():
                self.winner_pid = self._pid()
                Account.objects.select_for_update().get(pk=self.account.pk)
                self.winner_ready.set()
                client = Client()
                client.cookies['sessionid'] = self.reviewer_session_key
                response = client.post(f'/onboarding/review/{self.account.pk}/', {'decision': 'accept', 'revision': 7, 'home': 'test-home', 'identity_evidence': 'Concurrency identity check'})
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(response.json()['state'], 'accepted')
                self.contender_started.set()
                self.assertTrue(self.release.wait(15))
        except BaseException as exc:
            self.errors.append(exc)
        finally:
            connection.close()

    def _invite(self):
        close_old_connections()
        try:
            with transaction.atomic():
                self.winner_pid = self._pid()
                Account.objects.select_for_update().get(pk=self.account.pk)
                self.winner_ready.set()
                management.call_command('invite_person', person=str(self.person.pk), email=self.account.email, stdout=StringIO())
                self.assertTrue(self.release.wait(15))
        except BaseException as exc:
            self.errors.append(exc)
        finally:
            connection.close()

    def _losing_invite(self):
        close_old_connections()
        try:
            self.contender_pid = self._pid()
            self.contender_started.set()
            out = StringIO()
            with self.assertRaises(CommandError) as raised:
                management.call_command('invite_person', person=str(self.person.pk), email=self.account.email, stdout=out)
            self.assertIn('already linked to a different person', str(raised.exception))
        except BaseException as exc:
            self.errors.append(exc)
        finally:
            connection.close()

    def _losing_approval(self):
        close_old_connections()
        try:
            self.contender_pid = self._pid()
            self.contender_started.set()
            client = Client()
            client.cookies['sessionid'] = self.reviewer_session_key
            response = client.post(f'/onboarding/review/{self.account.pk}/', {'decision': 'accept', 'revision': 7, 'home': 'test-home', 'identity_evidence': 'Concurrency identity check'})
            self.assertEqual(response.status_code, 409, response.content)
        except BaseException as exc:
            self.errors.append(exc)
        finally:
            connection.close()

    def test_approval_wins_real_review_blocks_invite_and_rejects_it(self):
        approval = Thread(target=self._approval)
        contender = Thread(target=self._losing_invite)
        try:
            approval.start()
            self.assertTrue(self.winner_ready.wait(15))
            contender.start()
            self.assertTrue(self.contender_started.wait(15))
            observed = self._observe_wait(self.winner_pid, self.contender_pid)
        finally:
            self.release.set()
            self._join(approval, contender)
        self.account.refresh_from_db()
        draft = OnboardingDraft.objects.get(account=self.account)
        self.assertIsNotNone(self.account.person_id)
        self.assertEqual(Person.objects.count(), 2)
        self.assertEqual(draft.state, 'accepted')
        self.assertEqual(Invitation.objects.count(), 0)
        self.assertEqual(EmailIntent.objects.count(), self.email_intent_baseline)
        self.assertEqual(observed[2], 'Lock')

    def test_invite_wins_real_command_blocks_review_and_returns_conflict(self):
        approval = Thread(target=self._losing_approval)
        winner = Thread(target=self._invite)
        try:
            winner.start()
            self.assertTrue(self.winner_ready.wait(15))
            approval.start()
            self.assertTrue(self.contender_started.wait(15))
            observed = self._observe_wait(self.winner_pid, self.contender_pid)
        finally:
            self.release.set()
            self._join(winner, approval)
        draft = OnboardingDraft.objects.get(account=self.account)
        invitation = Invitation.objects.get()
        self.account.refresh_from_db()
        self.assertIsNone(self.account.person_id)
        self.assertEqual(draft.state, 'review_needed')
        self.assertEqual(Person.objects.count(), 1)
        self.assertEqual(Invitation.objects.count(), 1)
        self.assertEqual(EmailIntent.objects.count(), self.email_intent_baseline + 1)
        self.assertIsNone(invitation.claimed_at)
        self.assertIsNone(invitation.revoked_at)
        self.assertEqual(observed[2], 'Lock')
