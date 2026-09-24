"""Auditable targeted revocation for scoped onboarding reviewer grants."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Account, AccessGrant
from accounts.services import audit


class Command(BaseCommand):
    help = 'Revoke one scoped onboarding reviewer grant.'

    def add_arguments(self, parser):
        parser.add_argument('--grant-id', required=True, type=int)
        parser.add_argument('--reason', required=True)

    def handle(self, *args, **options):
        reason = options['reason'].strip()
        if not reason:
            raise CommandError('--reason must not be blank.')
        with transaction.atomic():
            account_id = (
                AccessGrant.objects
                .filter(pk=options['grant_id'])
                .values_list('account_id', flat=True)
                .first()
            )
            if not account_id:
                raise CommandError('Reviewer grant does not exist.')
            # Match review/provisioning order: account before grant. This keeps
            # revocation and approval from taking the two rows in reverse order.
            account = Account.objects.select_for_update().get(pk=account_id)
            grant = (
                AccessGrant.objects.select_for_update()
                .filter(pk=options['grant_id'])
                .first()
            )
            if not grant:
                raise CommandError('Reviewer grant does not exist.')
            if grant.revoked_at is None:
                grant.revoked_at = timezone.now()
                grant.save(update_fields=['revoked_at'])
                audit(account, 'operator_revoke_reviewer_grant', {
                    'grant_id': grant.pk,
                    'reason': reason,
                })
                status = 'revoked'
            else:
                status = 'already revoked'
        self.stdout.write(
            f'Reviewer grant {grant.pk} {status}; revocation reason supplied: {reason}.'
        )
