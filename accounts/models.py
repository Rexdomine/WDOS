"""Additive account security records; Django's installed User remains unchanged."""
import uuid
from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class Person(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    display_name = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)


class Account(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=150)
    person = models.OneToOneField(Person, null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=16, default='pending', choices=[(s, s) for s in ('pending', 'active', 'suspended')])
    verified_at = models.DateTimeField(null=True)
    security_version = models.PositiveIntegerField(default=1)
    mfa_secret = models.TextField(blank=True)
    mfa_pending_secret = models.TextField(blank=True)
    mfa_pending_until = models.DateTimeField(null=True)
    mfa_last_counter = models.BigIntegerField(default=-1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(Lower('email'), name='account_email_ci_unique'), models.CheckConstraint(condition=models.Q(status__in=['pending','active','suspended']), name='account_valid_status')]


class ActionToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    purpose = models.CharField(max_length=12, choices=[('verify','verify'),('reset','reset')])
    digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class Invitation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(Person, on_delete=models.PROTECT)
    email = models.EmailField()
    digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    claimed_at = models.DateTimeField(null=True)
    revoked_at = models.DateTimeField(null=True)
    claimed_by = models.ForeignKey(Account, null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class RecoveryCode(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    digest = models.CharField(max_length=64, unique=True)
    used_at = models.DateTimeField(null=True)


class EmailIntent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, null=True, on_delete=models.PROTECT)
    token = models.ForeignKey(ActionToken, null=True, on_delete=models.PROTECT)
    encrypted_payload = models.TextField()
    expires_at = models.DateTimeField(null=True)
    invitation = models.ForeignKey(Invitation, null=True, on_delete=models.PROTECT)
    state = models.CharField(max_length=16, default='pending', choices=[(s,s) for s in ('pending','blocked','sending','accepted','failed','unknown','expired')])
    message_id = models.CharField(max_length=255, blank=True)
    error_code = models.CharField(max_length=32, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)


class Throttle(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField()


class AuditEvent(models.Model):
    account = models.ForeignKey(Account, null=True, on_delete=models.PROTECT)
    event = models.CharField(max_length=48)
    created_at = models.DateTimeField(auto_now_add=True)


class AccessGrant(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    role = models.CharField(max_length=64)
    network = models.CharField(max_length=32)
    geography = models.CharField(max_length=100)
    function = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True)
