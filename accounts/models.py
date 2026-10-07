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
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class AccessGrant(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    role = models.CharField(max_length=64)
    network = models.CharField(max_length=32)
    geography = models.CharField(max_length=100)
    function = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True)


class OnboardingDraft(models.Model):
    """One durable draft per account, never an alternative person identity."""
    account = models.OneToOneField(Account, on_delete=models.PROTECT)
    revision = models.PositiveIntegerField(default=0)
    data = models.JSONField(default=dict)
    next_step = models.PositiveSmallIntegerField(default=1)
    state = models.CharField(max_length=24, default='draft')
    updated_at = models.DateTimeField(auto_now=True)
    submission_revision = models.PositiveIntegerField(null=True)
    submitted_at = models.DateTimeField(null=True)
    photo = models.BinaryField(default=bytes, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(next_step__gte=1, next_step__lte=8), name='onboarding_valid_step'),
            models.CheckConstraint(condition=models.Q(state__in=['draft', 'review_needed', 'accepted']), name='onboarding_valid_state'),
        ]


class OnboardingEvent(models.Model):
    draft = models.ForeignKey(OnboardingDraft, related_name='events', on_delete=models.PROTECT)
    actor = models.ForeignKey(Account, on_delete=models.PROTECT)
    event = models.CharField(max_length=32)
    revision = models.PositiveIntegerField()
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['draft', 'revision', 'event'], name='onboarding_event_once')]
        ordering = ['id']


class OnboardingConsent(models.Model):
    draft = models.ForeignKey(OnboardingDraft, related_name='consents', on_delete=models.PROTECT)
    revision = models.PositiveIntegerField()
    version = models.CharField(max_length=100)
    notice = models.TextField()
    digest = models.CharField(max_length=64)
    approval_reference = models.CharField(max_length=500)
    privacy_ack = models.BooleanField()
    optional_updates = models.BooleanField(default=False)
    channel = models.CharField(max_length=32)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['draft', 'revision'], name='onboarding_consent_once')]
        ordering = ['id']


class Membership(models.Model):
    """Ordinary membership only; this record never grants leadership authority."""
    draft = models.OneToOneField(OnboardingDraft, related_name='membership', on_delete=models.PROTECT)
    person = models.OneToOneField(Person, on_delete=models.PROTECT)
    network = models.CharField(max_length=8)
    home = models.JSONField()
    consent = models.ForeignKey(OnboardingConsent, on_delete=models.PROTECT)
    policy_digest = models.CharField(max_length=64)
    approved_by = models.ForeignKey(Account, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(network__in=['WGMN', 'WNNN']), name='membership_explicit_network')]


class CountryCatalogue(models.Model):
    """Normalized country catalogue for all 55 African nations."""
    iso3 = models.CharField(max_length=3, primary_key=True)
    iso2 = models.CharField(max_length=2, unique=True, db_index=True)
    name = models.CharField(max_length=100, unique=True, db_index=True)
    admin1_label = models.CharField(max_length=100)
    admin2_label = models.CharField(max_length=100)
    level2_reliable = models.BooleanField(default=False)
    source = models.CharField(max_length=100, default='geoBoundaries gbOpen')
    source_version = models.CharField(max_length=50, default='gbOpen-v4.0')
    last_verified_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Country Catalogue'

    def __str__(self):
        return f"{self.name} ({self.iso3})"


class AdministrativeDivision(models.Model):
    """Normalized Level 1 and reliable Level 2 administrative divisions."""
    id = models.CharField(max_length=64, primary_key=True)
    level = models.PositiveSmallIntegerField(choices=[(1, 'Level 1'), (2, 'Level 2')], db_index=True)
    country = models.ForeignKey(CountryCatalogue, on_delete=models.CASCADE, related_name='divisions')
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')
    display_name = models.CharField(max_length=150, db_index=True)
    local_unit_type = models.CharField(max_length=100)
    source = models.CharField(max_length=100)
    source_version = models.CharField(max_length=50)
    last_verified_date = models.DateField()

    class Meta:
        ordering = ['display_name']
        constraints = [
            models.UniqueConstraint(fields=['country', 'parent', 'display_name'], name='unique_division_per_parent'),
        ]

    def __str__(self):
        return f"{self.display_name} ({self.local_unit_type}, {self.id})"


class DataImprovementFlag(models.Model):
    """Flags unlisted subdivisions typed by users for subsequent catalogue enhancement."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    draft = models.ForeignKey(OnboardingDraft, null=True, blank=True, on_delete=models.SET_NULL, related_name='data_improvement_flags')
    account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.SET_NULL, related_name='geography_flags')
    country_iso3 = models.CharField(max_length=3)
    region_id = models.CharField(max_length=64, blank=True)
    region_name = models.CharField(max_length=150, blank=True)
    unlisted_subdivision = models.CharField(max_length=150)
    unit_type = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, default='pending', choices=[('pending', 'Pending Review'), ('reviewed', 'Reviewed'), ('catalogued', 'Added to Catalogue')])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Flag: {self.unlisted_subdivision} ({self.country_iso3} / {self.region_name})"

