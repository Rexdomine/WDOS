from datetime import timedelta
from io import StringIO
from unittest.mock import patch
import json
import subprocess
import sys
import threading
from django.core.management import call_command
from django.test import TestCase, SimpleTestCase, override_settings
from django.utils import timezone
from .models import EmailIntent, Invitation, Person, Account
from . import services
from wdos_project.runtime import supervise


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class OperatorTests(TestCase):
    def test_http_request_never_calls_provider_even_when_configured(self):
        with override_settings(BREVO_API_KEY='unit-test-only', WDOS_EMAIL_FROM='sender@example.org'):
            with patch('accounts.brevo.send') as send, self.captureOnCommitCallbacks(execute=True):
                self.client.post('/auth/register/',{'name':'Ada','email':'ada@example.org','password':'very long operator test password!'})
            send.assert_not_called()
        self.assertEqual(EmailIntent.objects.get().state,'pending')

    def test_worker_marks_missing_configuration_blocked_on_natural_tick(self):
        services.register('Ada','ada@example.org','very long operator test password!')
        call_command('run_auth_mailer',once=True,stdout=StringIO())
        self.assertEqual(EmailIntent.objects.get().state,'blocked')

    def test_stale_send_unknown_never_replayed(self):
        services.register('Ada','ada@example.org','very long operator test password!')
        intent=EmailIntent.objects.get()
        intent.state='sending'; intent.started_at=timezone.now()-timedelta(minutes=6); intent.save()
        with patch('accounts.brevo.send') as send:
            call_command('recover_auth_email',stdout=StringIO())
        send.assert_not_called()
        intent.refresh_from_db()
        self.assertEqual(intent.state,'unknown')
        self.assertEqual(intent.encrypted_payload,'')

    def test_invitation_operator_command_and_consumption(self):
        person=Person.objects.create(display_name='Existing person')
        with patch('accounts.brevo.send') as send:
            output=StringIO()
            call_command('invite_person',person=str(person.pk),email='ada@example.org',stdout=output)
        send.assert_not_called()
        intent=EmailIntent.objects.get()
        payload=json.loads(services.decrypt(intent.encrypted_payload))
        code=payload['textContent'].split('enter: ')[1].split('.')[0]
        self.assertNotIn(code,output.getvalue())
        account=services.register('Ada','ada@example.org','very long operator test password!')
        token,secret=services.issue_token(account,'verify')
        services.verify_contact(account.pk,secret)
        self.assertTrue(services.claim_invitation(account.pk,code,account.email))
        with patch('accounts.brevo.send') as send:
            services.dispatch_email(intent.pk)
        send.assert_not_called()
        intent.refresh_from_db(); self.assertEqual(intent.state,'expired')

    def test_operator_access_always_revokes_sessions(self):
        account=services.register('Ada','ada@example.org','very long operator test password!')
        token,secret=services.issue_token(account,'verify')
        services.verify_contact(account.pk,secret)
        for action in ['grant-staff','revoke-staff','suspend','restore']:
            old=Account.objects.get(pk=account.pk).security_version
            call_command('set_account_access',email=account.email,action=action,stdout=StringIO())
            account.refresh_from_db()
            self.assertEqual(account.security_version,old+1)


class SupervisorTests(SimpleTestCase):
    def test_child_exit_stops_sibling_and_reports_failure(self):
        children=[]
        real=subprocess.Popen
        def track(*args,**kwargs):
            child=real(*args,**kwargs); children.append(child); return child
        with patch('wdos_project.runtime.subprocess.Popen',side_effect=track):
            result=supervise([[sys.executable,'-c','import time; time.sleep(30)'],[sys.executable,'-c','raise SystemExit(2)']])
        self.assertEqual(result,1)
        self.assertTrue(all(p.poll() is not None for p in children))

    def test_shutdown_stops_all_children(self):
        stop=threading.Event(); stop.set()
        self.assertEqual(supervise([[sys.executable,'-c','import time; time.sleep(30)']],stop),0)
