"""Restricted operator command; all changes revoke existing and pending sessions."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from accounts.models import Account
from accounts.services import audit


class Command(BaseCommand):
    help = 'Operator-only account suspension/restoration or staff grant/revocation.'

    def add_arguments(self, parser):
        parser.add_argument('--email',required=True)
        parser.add_argument('--action',required=True,choices=['suspend','restore','grant-staff','revoke-staff'])

    def handle(self,*args,**options):
        with transaction.atomic():
            account=Account.objects.select_for_update().select_related('user').filter(email=options['email'].lower()).first()
            if not account:
                raise CommandError('Account does not exist; register through the normal flow first.')
            action=options['action']
            if action in ['restore','grant-staff'] and not account.verified_at:
                raise CommandError('Email verification is required first.')
            if action=='suspend': account.status='suspended'
            if action=='restore': account.status='active'
            if action in ['grant-staff','revoke-staff']:
                account.user.is_staff=action=='grant-staff'
                if action=='revoke-staff': account.user.is_superuser=False
                account.user.save()
            account.security_version+=1
            account.save()
            audit(account,'operator_'+action.replace('-','_'))
        self.stdout.write('Access updated; previous sessions revoked. Privileged sign-in requires MFA.')
