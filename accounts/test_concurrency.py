"""Real multi-connection contracts. SQLite results are deliberately insufficient."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from django.db import connection, close_old_connections
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
import pyotp
from .models import Account, Person, Invitation, EmailIntent, RecoveryCode
from . import services


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor!='postgresql':
            self.skipTest('PostgreSQL concurrency gate; required in CI')
        self.account=services.register('Ada','concurrency@example.org','a very long concurrency passphrase!')
        token,code=services.issue_token(self.account,'verify')
        services.verify_contact(self.account.pk,code)

    def race(self, operation):
        barrier=Barrier(2)
        def run(_):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return operation()
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(run,range(2)))

    def test_invitation_has_one_claim(self):
        person=Person.objects.create(display_name='Existing person')
        Invitation.objects.create(person=person,email=self.account.email,digest=services.digest('invitation-proof'),expires_at=timezone.now()+timedelta(hours=1))
        results=self.race(lambda:services.claim_invitation(self.account.pk,'invitation-proof',self.account.email))
        self.assertEqual(sorted(results),[False,True])

    def test_mfa_recovery_has_one_consumer(self):
        secret=pyotp.random_base32()
        Account.objects.filter(pk=self.account.pk).update(mfa_secret=services.encrypt(secret))
        RecoveryCode.objects.create(account=self.account,digest=services.digest('recovery-proof'))
        results=self.race(lambda:services.confirm_mfa(self.account.pk,'recovery-proof'))
        self.assertEqual(sum(r is not None for r in results),1)

    @override_settings(BREVO_API_KEY='unit-test-only',WDOS_EMAIL_FROM='sender@example.org')
    def test_provider_call_after_durable_claim_and_at_most_once(self):
        services.request_email(self.account.email,'reset')
        intent=EmailIntent.objects.filter(account=self.account,token__purpose='reset').get()
        observations=[]
        def provider(payload):
            # Independent connection can see the committed claim while provider runs.
            with ThreadPoolExecutor(max_workers=1) as pool:
                def observe():
                    close_old_connections()
                    try:
                        row=EmailIntent.objects.get(pk=intent.pk)
                        return row.state, bool(row.started_at), row.finished_at
                    finally: connection.close()
                observations.append(pool.submit(observe).result(timeout=10))
            return 'unit-message-id'
        with patch('accounts.brevo.send',side_effect=provider) as send:
            self.race(lambda:services.dispatch_email(intent.pk))
        self.assertEqual(send.call_count,1)
        self.assertEqual(observations,[('sending',True,None)])

    @override_settings(BREVO_API_KEY='unit-test-only',WDOS_EMAIL_FROM='sender@example.org')
    def test_crash_after_provider_acceptance_does_not_resend(self):
        services.request_email(self.account.email,'reset')
        intent=EmailIntent.objects.filter(token__purpose='reset').get()
        save=EmailIntent.save
        def crash(row,*args,**kwargs):
            if row.state=='accepted': raise RuntimeError('simulated terminal commit loss')
            return save(row,*args,**kwargs)
        with patch('accounts.brevo.send',return_value='unit-message-id') as send:
            with patch.object(EmailIntent,'save',crash):
                with self.assertRaises(RuntimeError): services.dispatch_email(intent.pk)
            services.dispatch_email(intent.pk)
        self.assertEqual(send.call_count,1)
        intent.refresh_from_db(); self.assertEqual(intent.state,'sending')
