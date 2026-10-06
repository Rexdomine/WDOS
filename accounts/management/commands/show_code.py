"""Management command to view or reissue verification codes and reset links in local development."""
import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import Account, EmailIntent
from accounts.services import decrypt, request_email


class Command(BaseCommand):
    help = 'Show the latest verification code or password reset link for local testing.'

    def add_arguments(self, parser):
        parser.add_argument('email', nargs='?', default=None, help='Email address to filter by')
        parser.add_argument('--resend', action='store_true', help='Generate and send a fresh verification code for the email')

    def handle(self, *args, **options):
        email = options.get('email')
        resend = options.get('resend')

        if resend:
            if not email:
                self.stderr.write(self.style.ERROR('Please provide an email address when using --resend.'))
                return
            account = Account.objects.filter(email__iexact=email.strip().lower()).first()
            if not account:
                self.stderr.write(self.style.ERROR(f'No account found with email: {email}'))
                return
            purpose = 'verify' if account.status == 'pending' else 'reset'
            request_email(account.email, purpose)
            self.stdout.write(self.style.SUCCESS(f'Issued fresh {purpose} code for {account.email}.'))

        now = timezone.now()
        qs = EmailIntent.objects.filter(encrypted_payload__gt='').order_by('-created_at')
        if email:
            qs = qs.filter(account__email__iexact=email.strip().lower())

        intent = qs.first()
        if not intent:
            self.stdout.write(self.style.WARNING('No recent active email intents found in the database.'))
            return

        try:
            payload = json.loads(decrypt(intent.encrypted_payload))
            text = payload.get('textContent', '')
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'Failed to decrypt payload: {exc}'))
            return

        is_expired = intent.expires_at and intent.expires_at <= now
        status_str = self.style.ERROR('EXPIRED') if is_expired else self.style.SUCCESS('ACTIVE')

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(f'Account:    {intent.account.email}')
        self.stdout.write(f'Status:     {status_str}')
        self.stdout.write(f'Created:    {intent.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")}')
        if intent.expires_at:
            self.stdout.write(f'Expires:    {intent.expires_at.strftime("%Y-%m-%d %H:%M:%S UTC")}')
        self.stdout.write('-' * 60)
        self.stdout.write(text)
        self.stdout.write('=' * 60 + '\n')
