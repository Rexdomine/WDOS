"""Behavioral regressions through live forms/services; no provider calls."""
from datetime import timedelta
import json
import uuid
from unittest.mock import patch, MagicMock
import urllib.error
import pyotp
from django.conf import settings
from django.db import transaction, connection, close_old_connections
from django.test import TestCase, TransactionTestCase, Client, RequestFactory, override_settings
from django.utils import timezone
from . import services, brevo
from .models import Account, ActionToken, AuditEvent, EmailIntent, Invitation, Person, RecoveryCode, AccessGrant
from .permissions import allowed


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AuthFlows(TestCase):
    password='a genuinely long WDOS example passphrase!'

    def create(self, email='ada@example.org', privileged=False):
        account=services.register('Ada Example',email,self.password)
        token,code=services.issue_token(account,'verify')
        self.assertTrue(services.verify_contact(account.pk,code))
        account.refresh_from_db()
        if privileged:
            account.user.is_staff=True
            account.user.save()
        return account

    def login(self, account, client=None):
        return (client or self.client).post('/auth/login/',{'email':account.email,'password':self.password})

    def test_invitation_success_keeps_authenticated_controls(self):
        from django.core.management import call_command
        from io import StringIO
        account = self.create()
        person = Person.objects.create(display_name='Invited person')
        call_command('invite_person', person=str(person.pk), email=account.email, stdout=StringIO())
        intent = EmailIntent.objects.get(invitation__person=person)
        payload = json.loads(services.decrypt(intent.encrypted_payload))
        code = payload['textContent'].split('enter: ')[1].split('.')[0]
        self.login(account)
        response = self.client.post('/auth/invitation/', {'email': account.email, 'code': code})
        self.assertContains(response, 'Record linked')
        self.assertContains(response, 'Your invited person record is linked.')
        self.assertContains(response, 'Sign out all sessions')
        self.assertNotContains(response, 'Back to sign in')
        self.assertEqual(self.client.get('/auth/session/').status_code, 200)
        self.assertRedirects(self.client.post('/auth/logout/'), '/auth/login/')

    def test_real_registration_verification_login_logout(self):
        with self.captureOnCommitCallbacks(execute=True):
            response=self.client.post('/auth/register/',{'name':'Ada','email':'ADA@example.org','password':self.password,'is_staff':'true','role':'HQ'})
        self.assertRedirects(response,'/auth/verify/')
        account=Account.objects.get()
        self.assertFalse(account.user.is_staff)
        intent=EmailIntent.objects.get()
        self.assertEqual(intent.state,'pending')
        payload=json.loads(services.decrypt(intent.encrypted_payload))
        code=payload['textContent'].split(' is ')[1].split('.')[0]
        self.assertNotIn(code,intent.encrypted_payload)
        response=self.client.post('/auth/verify/',{'email':account.email,'code':code})
        self.assertContains(response,'Contact verified')
        self.login(account)
        self.assertEqual(self.client.get('/auth/session/').status_code,200)
        self.assertRedirects(self.client.post('/auth/logout/'),'/auth/login/')
        self.assertEqual(self.client.get('/auth/session/').status_code,401)

    def test_verification_is_bound_to_the_registration_session(self):
        account = services.register('Ada', 'bound@example.org', self.password)
        intent = EmailIntent.objects.get(account=account)
        code = json.loads(services.decrypt(intent.encrypted_payload))['textContent'].split(' is ')[1].split('.')[0]
        response = self.client.post('/auth/verify/', {'email': account.email, 'code': code})
        self.assertContains(response, 'could not be verified')
        account.refresh_from_db()
        self.assertEqual(account.status, 'pending')

    def test_pending_sign_in_preserves_registration_verification_binding(self):
        response = self.client.post('/auth/register/', {
            'name': 'Ada', 'email': 'pending-signin@example.org', 'password': self.password
        })
        self.assertRedirects(response, '/auth/verify/')
        account = Account.objects.get(email='pending-signin@example.org')
        intent = EmailIntent.objects.get(account=account)
        code = json.loads(services.decrypt(intent.encrypted_payload))['textContent'].split(' is ')[1].split('.')[0]
        self.assertRedirects(self.client.post('/auth/login/', {'email': account.email, 'password': self.password}), '/auth/status/')
        response = self.client.post('/auth/verify/', {'email': account.email, 'code': code})
        self.assertContains(response, 'Contact verified')

    def test_email_owner_can_reclaim_pending_registration(self):
        services.register('Attacker', 'reclaim@example.org', 'attacker passphrase long enough!')
        victim_password = 'victim passphrase long enough!'
        response = self.client.post('/auth/register/', {
            'name': 'Victim Owner', 'email': 'reclaim@example.org', 'password': victim_password
        })
        self.assertRedirects(response, '/auth/verify/')
        account = Account.objects.get(email='reclaim@example.org')
        intent = EmailIntent.objects.filter(account=account).order_by('-created_at').first()
        code = json.loads(services.decrypt(intent.encrypted_payload))['textContent'].split(' is ')[1].split('.')[0]
        other = Client()
        self.assertContains(other.post('/auth/login/', {
            'email': account.email, 'password': 'attacker passphrase long enough!'
        }), 'not recognised')
        self.assertContains(self.client.post('/auth/verify/', {'email': account.email, 'code': code}), 'Contact verified')
        account.refresh_from_db()
        self.assertEqual(account.display_name, 'Victim Owner')
        self.assertTrue(account.user.check_password(victim_password))

    def test_verification_attempt_limit_and_purpose(self):
        account=services.register('Ada','ada@example.org',self.password)
        token,code=services.issue_token(account,'verify')
        for _ in range(5):
            self.assertFalse(services.verify_contact(account.pk,'wrong'))
        self.assertFalse(services.verify_contact(account.pk,code))
        reset,secret=services.issue_token(account,'reset')
        self.assertFalse(services.verify_contact(account.pk,secret))

    def test_expiry_matrix_and_resend_revocation(self):
        for delta, expected in [(-1,True),(0,False),(1,False)]:
            account=services.register('Ada',f'ada{delta}@example.org',self.password)
            token,code=services.issue_token(account,'verify')
            with patch('accounts.services.timezone.now',return_value=token.expires_at+timedelta(seconds=delta)):
                self.assertEqual(services.verify_contact(account.pk,code),expected)
        account=services.register('Ada','resend@example.org',self.password)
        old,oldcode=services.issue_token(account,'verify')
        fresh,freshcode=services.issue_token(account,'verify')
        self.assertFalse(services.verify_contact(account.pk,oldcode))
        self.assertTrue(services.verify_contact(account.pk,freshcode))

    def test_reset_real_form_revokes_all_sessions_and_preserves_mfa(self):
        account=self.create()
        other=Client()
        self.login(account); self.login(account,other)
        token,secret=services.issue_token(account,'reset')
        proof=str(token.pk)+'.'+secret
        self.client.get('/auth/reset/')
        token.refresh_from_db(); self.assertIsNone(token.used_at)
        response=self.client.post('/auth/reset/',{'proof':proof,'password':self.password+'new','confirm':self.password+'new'})
        self.assertContains(response,'Password updated')
        self.assertEqual(other.get('/auth/session/').status_code,401)
        self.assertFalse(services.reset_password(str(token.pk),secret,self.password+'other'))

    def test_suspension_and_idle_expiry_rechecked(self):
        account=self.create(); self.login(account)
        Account.objects.filter(pk=account.pk).update(status='suspended')
        self.assertEqual(self.client.get('/auth/session/').status_code,401)
        Account.objects.filter(pk=account.pk).update(status='active')
        self.login(account)
        session=self.client.session
        session['last_activity']=timezone.now().timestamp()-settings.WDOS_IDLE_TTL
        session.save()
        self.assertEqual(self.client.get('/auth/session/').status_code,401)

    def test_privileged_mfa_and_admin_cannot_be_bypassed(self):
        account=self.create(privileged=True)
        response=self.login(account)
        self.assertRedirects(response,'/auth/mfa/')
        self.assertEqual(self.client.get('/auth/session/').status_code,401)
        self.assertRedirects(self.client.get('/admin/login/'),'/auth/login/')
        response=self.client.post('/auth/mfa/',{'begin':'1'})
        account.refresh_from_db()
        secret=services.decrypt(account.mfa_pending_secret)
        self.assertContains(response,secret)
        response=self.client.post('/auth/mfa/',{'code':pyotp.TOTP(secret).now()})
        self.assertContains(response,'Save your recovery codes')
        codes=response.context['codes']
        self.assertEqual(len(codes),8)
        self.assertEqual(self.client.get('/auth/session/').status_code,200)
        self.client.post('/auth/logout/')
        self.login(account)
        response=self.client.post('/auth/mfa/',{'code':pyotp.TOTP(secret).now()})
        self.assertContains(response,'This code could not be verified')
        self.assertEqual(self.client.get('/auth/session/').status_code,401)
        self.client.post('/auth/mfa/',{'code':codes[0]})
        self.assertEqual(self.client.get('/auth/session/').status_code,200)
        self.client.post('/auth/logout/'); self.login(account)
        response=self.client.post('/auth/mfa/',{'code':codes[0]})
        self.assertContains(response,'This code could not be verified')
        account.refresh_from_db(); original=account.mfa_secret
        token,proof=services.issue_token(account,'reset')
        self.assertTrue(services.reset_password(str(token.pk),proof,self.password+'new'))
        account.refresh_from_db(); self.assertEqual(account.mfa_secret,original)
        self.assertRedirects(self.client.get('/auth/mfa/'),'/auth/login/')

    def test_invitation_identity_no_privilege_no_replay(self):
        account=self.create()
        person=Person.objects.create(display_name='Existing person')
        code='unguessable-invite-secret'
        invite=Invitation.objects.create(person=person,email=account.email,digest=services.digest(code),expires_at=timezone.now()+timedelta(hours=1))
        self.assertFalse(services.claim_invitation(account.pk,code,'other@example.org'))
        self.assertTrue(services.claim_invitation(account.pk,code,account.email))
        self.assertFalse(services.claim_invitation(account.pk,code,account.email))
        account.refresh_from_db(); self.assertEqual(account.person,person)
        self.assertFalse(account.user.is_staff)
        other=self.create('other@example.org')
        Invitation.objects.create(person=person,email=other.email,digest=services.digest('second-secret'),expires_at=timezone.now()+timedelta(hours=1))
        self.assertFalse(services.claim_invitation(other.pk,'second-secret',other.email))

    def test_invitation_expired_or_suspended_denied(self):
        account=self.create()
        person=Person.objects.create(display_name='Existing person')
        invite=Invitation.objects.create(person=person,email=account.email,digest=services.digest('expired'),expires_at=timezone.now())
        self.assertFalse(services.claim_invitation(account.pk,'expired',account.email))
        Account.objects.filter(pk=account.pk).update(status='suspended')
        invite.expires_at=timezone.now()+timedelta(days=1); invite.save()
        self.assertFalse(services.claim_invitation(account.pk,'expired',account.email))

    def test_scope_exact_match_and_live_revocation(self):
        account=self.create()
        grant=AccessGrant.objects.create(account=account,role='member',network='WGMN',geography='NG',function='read',expires_at=timezone.now()+timedelta(days=1))
        request=MagicMock(wdos_account=account,session={'mfa_verified':True})
        args=dict(role='member',network='WGMN',geography='NG',function='read')
        self.assertTrue(allowed(request,**args))
        self.assertFalse(allowed(request,**dict(args,network='WNNN')))
        self.assertFalse(allowed(request,**dict(args,geography='GH')))
        self.assertFalse(allowed(request,**dict(args,function='write')))
        grant.revoked_at=timezone.now(); grant.save()
        self.assertFalse(allowed(request,**args))

    def test_recovery_unknown_has_same_response_and_no_redirect_injection(self):
        account=self.create()
        a=self.client.post('/auth/recover/',{'email':account.email})
        b=self.client.post('/auth/recover/',{'email':'unknown@example.org'})
        self.assertEqual(a.context['lede'],b.context['lede'])
        r=self.client.post('/auth/login/?next=https://evil.invalid',{'email':account.email,'password':self.password})
        self.assertEqual(r.url,'/auth/status/')

    def test_rate_limit_shared_and_resets_at_boundary(self):
        for _ in range(2): self.assertTrue(services.throttle('test','person',limit=2))
        self.assertFalse(services.throttle('test','person',limit=2))
        with patch('accounts.services.timezone.now',return_value=timezone.now()+timedelta(seconds=901)):
            self.assertTrue(services.throttle('test','person',limit=2))

    def test_screens_security_headers_and_no_get_mutations(self):
        for path in ['/','/auth/login/','/auth/register/','/auth/verify/','/auth/recover/','/auth/reset/','/auth/status/']:
            response=self.client.get(path)
            self.assertEqual(response.status_code,200)
            self.assertIn('no-store',response['Cache-Control'])
            self.assertEqual(response['Referrer-Policy'],'same-origin')
            self.assertContains(response,'WODDI DIGITAL OPERATING SYSTEM')
        self.assertEqual(self.client.get('/auth/revoke/').status_code,405)
        client=Client(enforce_csrf_checks=True)
        for path in ['/auth/login/','/auth/verify/','/auth/recover/','/auth/reset/','/auth/mfa/','/auth/logout/']:
            self.assertEqual(client.post(path,{}).status_code,403)

    def test_ip_rate_limit_does_not_create_subject_rows(self):
        request = RequestFactory().post('/', REMOTE_ADDR='198.51.100.7')
        with patch('accounts.views.services.throttle', return_value=False) as throttle:
            from . import views
            self.assertFalse(views.rate(request, 'verify', 'victim@example.org'))
        throttle.assert_called_once_with('verify:ip', '198.51.100.7', limit=60)

    def test_registration_password_rejects_submitted_name(self):
        response = self.client.post('/auth/register/', {
            'name': 'Ada Example', 'email': 'name@example.org', 'password': 'Ada Example Ada'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'too similar')


@override_settings(BREVO_API_KEY='unit-test-only',WDOS_EMAIL_FROM='sender@example.org', PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class DeliveryTests(TestCase):
    def test_malformed_outbox_payload_is_failed_and_quarantined_without_provider_call(self):
        services.register('Ada','malformed@example.org','very long delivery test passphrase!')
        intent=EmailIntent.objects.get()
        intent.encrypted_payload='not-fernet'
        intent.save(update_fields=['encrypted_payload'])
        with patch('accounts.brevo.send') as mocked:
            services.dispatch_email(intent.pk)
        mocked.assert_not_called()
        intent.refresh_from_db()
        self.assertEqual(intent.state,'failed')
        self.assertEqual(intent.error_code,'invalid_payload')
        self.assertEqual(intent.encrypted_payload,'')

    def test_invalid_json_outbox_payload_is_failed_and_next_intent_can_send(self):
        services.register('Ada','json@example.org','very long delivery test passphrase!')
        first=EmailIntent.objects.get()
        first.encrypted_payload=services.encrypt('{not-json')
        first.save(update_fields=['encrypted_payload'])
        services.register('Bea','valid@example.org','another very long delivery passphrase!')
        second=EmailIntent.objects.exclude(pk=first.pk).get()
        with patch('accounts.brevo.send', return_value='message-id') as mocked:
            services.dispatch_email(first.pk)
            services.dispatch_email(second.pk)
        first.refresh_from_db(); second.refresh_from_db()
        self.assertEqual(first.state,'failed')
        self.assertEqual(second.state,'accepted')
        self.assertEqual(mocked.call_count,1)

    def test_invalid_utf8_outbox_payload_is_failed_and_quarantined(self):
        services.register('Ada','encoding@example.org','very long delivery test passphrase!')
        intent=EmailIntent.objects.get()
        intent.encrypted_payload=services.cipher().encrypt(b'\xff').decode('ascii')
        intent.save(update_fields=['encrypted_payload'])
        with patch('accounts.brevo.send') as mocked:
            services.dispatch_email(intent.pk)
        mocked.assert_not_called()
        intent.refresh_from_db()
        self.assertEqual(intent.state,'failed')
        self.assertEqual(intent.error_code,'invalid_payload')
    def test_intent_claimed_before_call_and_no_duplicate_send(self):
        account=services.register('Ada','ada@example.org','very long delivery test passphrase!')
        intent=EmailIntent.objects.get(account=account)
        def send(payload):
            intent.refresh_from_db()
            self.assertEqual(intent.state,'sending')
            self.assertIsNotNone(intent.started_at)
            return 'unit-message-id'
        with patch('accounts.brevo.send',side_effect=send) as mocked:
            services.dispatch_email(intent.pk)
            services.dispatch_email(intent.pk)
        self.assertEqual(mocked.call_count,1)
        intent.refresh_from_db()
        self.assertEqual(intent.state,'accepted')
        self.assertEqual(intent.encrypted_payload,'')

    def test_timeout_unknown_no_retry(self):
        services.register('Ada','ada@example.org','very long delivery test passphrase!')
        intent=EmailIntent.objects.get()
        with patch('accounts.brevo.send',side_effect=brevo.BrevoFailure('unknown','transport_unknown')) as mocked:
            services.dispatch_email(intent.pk); services.dispatch_email(intent.pk)
        self.assertEqual(mocked.call_count,1)
        intent.refresh_from_db(); self.assertEqual(intent.state,'unknown')

    def test_transport_status_matrix(self):
        for code,expected in [(401,'failed'),(403,'failed'),(429,'failed'),(500,'unknown')]:
            opener=MagicMock()
            opener.open.side_effect=urllib.error.HTTPError('https://api.brevo.com',code,'test',{},None)
            with patch('accounts.brevo.urllib.request.build_opener',return_value=opener):
                with self.assertRaises(brevo.BrevoFailure) as err: brevo.send({'to':[]})
                self.assertEqual(err.exception.state,expected)
        for body in [b'invalid',b'{}']:
            opener=MagicMock(); response=opener.open.return_value.__enter__.return_value
            response.status=201; response.read.return_value=body
            with patch('accounts.brevo.urllib.request.build_opener',return_value=opener):
                with self.assertRaises(brevo.BrevoFailure) as err: brevo.send({'to':[]})
                self.assertEqual(err.exception.state,'unknown')

    def test_expired_token_never_sent(self):
        services.register('Ada','ada@example.org','very long delivery test passphrase!')
        intent=EmailIntent.objects.get()
        ActionToken.objects.filter(pk=intent.token_id).update(expires_at=timezone.now())
        with patch('accounts.brevo.send') as mocked: services.dispatch_email(intent.pk)
        mocked.assert_not_called()
        intent.refresh_from_db(); self.assertEqual(intent.state,'expired')


class PostgreSQLRaces(TransactionTestCase):
    def setUp(self):
        if connection.vendor != 'postgresql':
            self.skipTest('Requires real PostgreSQL; mandatory in hosted CI')

    @override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
    def test_concurrent_token_consumption_has_one_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        account=services.register('Ada','race@example.org','a very long race test passphrase!')
        token,code=services.issue_token(account,'verify')
        barrier=Barrier(2)
        def consume():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return services.verify_contact(account.pk,code)
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:consume(),range(2)))
        self.assertEqual(sorted(results),[False,True])
