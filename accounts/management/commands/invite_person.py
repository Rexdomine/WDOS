"""Trusted operator invitation issuance. No new person or authority is created."""
from datetime import timedelta
import html
import json
import secrets
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from accounts.models import Person, Invitation, EmailIntent
from accounts.services import digest, encrypt, dispatch_email


class Command(BaseCommand):
    help = 'Queue a WDOS invitation for an existing person; never print the claim secret.'

    def add_arguments(self, parser):
        parser.add_argument('--person', required=True)
        parser.add_argument('--email', required=True)

    def handle(self, *args, **options):
        email=options['email'].strip().lower()
        try:
            validate_email(email)
            person=Person.objects.get(pk=options['person'])
        except (ValidationError,ValueError,Person.DoesNotExist):
            raise CommandError('Valid recipient and existing person ID are required.') from None
        secret=secrets.token_urlsafe(32)
        with transaction.atomic():
            person=Person.objects.select_for_update().get(pk=person.pk)
            if hasattr(person,'account'):
                raise CommandError('Person already has a linked account.')
            Invitation.objects.filter(person=person, claimed_at=None, revoked_at=None).update(revoked_at=timezone.now())
            invitation=Invitation.objects.create(person=person,email=email,digest=digest(secret),expires_at=timezone.now()+timedelta(days=7))
            text=f'You have been invited to link your WDOS account to an existing person record. Sign in with this email, open Claim an invited record and enter: {secret}. This invitation expires in seven days. No leadership role is granted.'
            payload={'to':[{'email':email}], 'subject':'Your WDOS invitation', 'textContent':text, 'htmlContent':'<h1>Your WDOS invitation</h1><p>'+html.escape(text)+'</p>'}
            intent=EmailIntent.objects.create(invitation=invitation,expires_at=invitation.expires_at,encrypted_payload=encrypt(json.dumps(payload)))
            # The supervised outbox worker sends this committed intent.
        self.stdout.write('Invitation queued. Provider acceptance and delivery must be checked separately.')
