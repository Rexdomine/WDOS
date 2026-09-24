"""Auditable operator provisioning for scoped onboarding reviewers."""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import AccessGrant, Account
from accounts.services import audit


class Command(BaseCommand):
    help = 'Provision a scoped, expiring onboarding reviewer grant.'

    def add_arguments(self, parser):
        parser.add_argument('--email', required=True)
        parser.add_argument('--role', required=True)
        parser.add_argument('--function', required=True)
        parser.add_argument('--network', required=True, choices=['WGMN', 'WNNN'])
        parser.add_argument('--geography', required=True)
        parser.add_argument('--expires-hours', required=True, type=int)

    def handle(self, *args, **options):
        if options['expires_hours'] <= 0:
            raise CommandError('--expires-hours must be positive.')
        with transaction.atomic():
            account = (
                Account.objects.select_for_update().select_related('user')
                .filter(email__iexact=options['email'].strip()).first()
            )
            if not account:
                raise CommandError('Account does not exist; register through the normal flow first.')
            if account.status != 'active' or not account.verified_at or not account.user.is_active:
                raise CommandError('An active, verified account is required.')
            grant = AccessGrant.objects.create(
                account=account,
                role=options['role'].strip(),
                function=options['function'].strip(),
                network=options['network'],
                geography=options['geography'].strip(),
                expires_at=timezone.now() + timedelta(hours=options['expires_hours']),
            )
            audit(account, 'operator_provision_reviewer_grant')
        self.stdout.write(f'Reviewer grant {grant.pk} provisioned; expiry is {grant.expires_at.isoformat()}.')