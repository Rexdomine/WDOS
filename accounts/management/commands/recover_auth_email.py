"""Recover queued intents conservatively; never retry unknown provider acceptance."""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from accounts.models import EmailIntent
from accounts.services import dispatch_email


class Command(BaseCommand):
    help = 'Expire old payloads, classify stale sends unknown, and retry only unsent intents.'

    def handle(self, *args, **options):
        now = timezone.now()
        with transaction.atomic():
            for row in EmailIntent.objects.select_for_update().filter(state='sending', started_at__lte=now-timedelta(minutes=5)):
                row.state='unknown'; row.error_code='interrupted_send'; row.encrypted_payload=''; row.finished_at=now; row.save()
            EmailIntent.objects.filter(state__in=['pending','blocked'], expires_at__lte=now).update(state='expired',encrypted_payload='',finished_at=now)
        ids=list(EmailIntent.objects.filter(state__in=['pending','blocked']).order_by('created_at').values_list('pk',flat=True)[:100])
        for pk in ids:
            dispatch_email(pk)
        self.stdout.write(f'Processed {len(ids)} unsent intents. Unknown/failed sends were not retried.')
