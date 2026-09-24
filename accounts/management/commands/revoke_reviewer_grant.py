"""Auditable targeted revocation for scoped onboarding reviewer grants."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import AccessGrant
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
            grant = (
                AccessGrant.objects.select_for_update()
                .select_related('account')
                .filter(pk=options['grant_id'])
                .first()
            )
            if not grant:
                raise CommandError('Reviewer grant does not exist.')
            if grant.revoked_at is None:
                grant.revoked_at = timezone.now()
                grant.save(update_fields=['revoked_at'])
                audit(grant.account, 'operator_revoke_reviewer_grant')
                status = 'revoked'
            else:
                status = 'already revoked'
        self.stdout.write(
            f'Reviewer grant {grant.pk} {status}; revocation reason supplied: {reason}.'
        )
