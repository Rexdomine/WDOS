"""Transactional authentication commands; no provider effect occurs before commit."""
import base64
import hashlib
import json
import secrets
import uuid
from datetime import timedelta
import pyotp
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from .email_templates import render_email
from .models import Account, ActionToken, AuditEvent, EmailIntent, Invitation, Person, RecoveryCode, Throttle


def digest(value):
    return salted_hmac('wdos-auth-proof-v1', str(value), algorithm='sha256').hexdigest()


def cipher():
    # Domain-separated encryption, tied to the deployment secret; rotation requires re-encryption.
    key = hashlib.sha256(('wdos-auth-encryption-v1:'+settings.SECRET_KEY).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(value):
    return cipher().encrypt(value.encode()).decode()


def decrypt(value):
    return cipher().decrypt(value.encode()).decode()


def audit(account, event):
    AuditEvent.objects.create(account=account, event=event)


def throttle(scope, identity, limit=10, seconds=900):
    """Shared DB-backed fixed window; identifiers persisted only as keyed hashes."""
    key = digest(scope+':'+identity)
    with transaction.atomic():
        row, _ = Throttle.objects.get_or_create(key=key, defaults={'expires_at': timezone.now()+timedelta(seconds=seconds)})
        row = Throttle.objects.select_for_update().get(pk=row.pk)
        now = timezone.now()
        if row.expires_at <= now:
            row.count = 0
            row.expires_at = now+timedelta(seconds=seconds)
        allowed = row.count < limit
        if allowed:
            row.count += 1
        row.save()
        return allowed


def _issue_locked(account, purpose):
    now = timezone.now()
    ActionToken.objects.filter(account=account, purpose=purpose, used_at=None).update(used_at=now)
    secret = f'{secrets.randbelow(1000000):06d}' if purpose == 'verify' else secrets.token_urlsafe(32)
    token = ActionToken.objects.create(account=account, purpose=purpose, digest=digest(secret), expires_at=now+timedelta(seconds=settings.WDOS_VERIFY_TTL if purpose=='verify' else settings.WDOS_RESET_TTL))
    return token, secret


def issue_token(account, purpose):
    if purpose not in ('verify','reset'):
        raise ValueError('Unsupported token purpose')
    with transaction.atomic():
        locked = Account.objects.select_for_update().get(pk=account.pk)
        return _issue_locked(locked, purpose)


def _email_locked(account, purpose):
    token, secret = _issue_locked(account, purpose)
    if purpose == 'verify':
        subject = 'Verify your WDOS account'
        expiry_minutes = settings.WDOS_VERIFY_TTL // 60
        text = f'Your WDOS verification code is {secret}. It expires in {expiry_minutes} minutes. If you did not request this, ignore this email.'
        html_content = render_email('verify', {'code': secret, 'expiry_minutes': expiry_minutes})
    else:
        subject = 'Reset your WDOS password'
        # Fragment is not sent to access logs. The browser posts it to a CSRF-protected form.
        url = settings.WDOS_PUBLIC_ORIGIN.rstrip('/')+'/auth/reset/#'+str(token.pk)+'.'+secret
        expiry_minutes = settings.WDOS_RESET_TTL // 60
        text = f'Reset your WDOS password: {url}\nThis link expires in {expiry_minutes} minutes. If you did not request this, ignore this email.'
        html_content = render_email('reset', {'url': url, 'expiry_minutes': expiry_minutes})
    payload = {'to':[{'email':account.email}], 'subject':subject, 'textContent':text, 'htmlContent':html_content}
    intent = EmailIntent.objects.create(account=account, token=token, encrypted_payload=encrypt(json.dumps(payload)), expires_at=token.expires_at)
    # A supervised outbox worker sends after commit; request timing never waits on Brevo.
    return intent


def register(name, email, password):
    email = email.strip().lower()
    user = get_user_model()(username=uuid.uuid4().hex, email=email, first_name=name)
    validate_password(password, user)
    user.set_password(password)
    try:
        with transaction.atomic():
            existing = Account.objects.select_for_update().select_related('user').filter(email__iexact=email).first()
            if existing:
                if existing.status != 'pending':
                    return None
                existing.user.first_name = name
                existing.user.set_password(password)
                existing.user.save(update_fields=['first_name', 'password'])
                existing.display_name = name
                existing.save(update_fields=['display_name'])
                _email_locked(existing, 'verify')
                audit(existing, 'registration_requested')
                return existing
            # Never attach a new account to an existing legacy user by email.
            if get_user_model().objects.filter(email__iexact=email).exists():
                return None
            user.save()
            account = Account.objects.create(user=user, email=email, display_name=name)
            _email_locked(account, 'verify')
            audit(account, 'registration_requested')
            return account
    except IntegrityError:
        return None


def request_email(email, purpose):
    with transaction.atomic():
        account = Account.objects.select_for_update().filter(email=email.strip().lower()).first()
        if not account or (purpose=='verify' and account.status!='pending') or (purpose=='reset' and account.status!='active'):
            return
        _email_locked(account, purpose)
        audit(account, purpose+'_requested')


def _consume_locked(account, purpose, secret, token_id=None):
    query = ActionToken.objects.select_for_update().filter(account=account, purpose=purpose, used_at=None)
    if token_id:
        query = query.filter(pk=token_id)
    token = query.order_by('-created_at').first()
    now = timezone.now()
    if not token or token.expires_at <= now or token.attempts >= 5:
        audit(account, purpose+'_expired_or_unavailable')
        return False
    token.attempts += 1
    good = constant_time_compare(token.digest, digest(secret))
    if good or token.attempts >= 5:
        token.used_at = now
    token.save()
    if not good:
        audit(account, purpose+'_rejected')
    return good


def verify_contact(account_id, secret):
    with transaction.atomic():
        account = Account.objects.select_for_update().filter(pk=account_id).first()
        if not account or account.status!='pending' or not _consume_locked(account, 'verify', secret):
            return False
        account.status = 'active'
        account.verified_at = timezone.now()
        account.save()
        audit(account, 'contact_verified')
        return True


def reset_password(token_id, secret, password):
    try:
        token_id = uuid.UUID(token_id)
    except (ValueError, TypeError, AttributeError):
        return False
    token = ActionToken.objects.filter(pk=token_id, purpose='reset').first()
    if not token:
        return False
    with transaction.atomic():
        account = Account.objects.select_for_update().select_related('user').get(pk=token.account_id)
        validate_password(password, account.user)
        if account.user.check_password(password):
            raise ValidationError('Choose a password you have not used here before.')
        if account.status!='active' or not _consume_locked(account, 'reset', secret, token_id):
            return False
        account.user.set_password(password)
        account.user.save(update_fields=['password'])
        account.security_version += 1
        account.save(update_fields=['security_version'])
        ActionToken.objects.filter(account=account, used_at=None).update(used_at=timezone.now())
        audit(account, 'password_reset_sessions_revoked')
        return True


def requires_mfa(account):
    return bool(account.user.is_staff or account.user.is_superuser or account.mfa_secret or account.accessgrant_set.filter(revoked_at=None, expires_at__gt=timezone.now()).exists())


def begin_mfa(account_id):
    with transaction.atomic():
        account = Account.objects.select_for_update().get(pk=account_id)
        if account.status!='active' or account.mfa_secret:
            return None
        if not account.mfa_pending_secret or not account.mfa_pending_until or account.mfa_pending_until <= timezone.now():
            account.mfa_pending_secret = encrypt(pyotp.random_base32())
            account.mfa_pending_until = timezone.now()+timedelta(seconds=settings.WDOS_MFA_TTL)
            account.save()
        return decrypt(account.mfa_pending_secret)


def confirm_mfa(account_id, code, setup=False):
    with transaction.atomic():
        account = Account.objects.select_for_update().get(pk=account_id)
        now = timezone.now()
        if account.status!='active' or not account.user.is_active:
            return None
        encrypted = account.mfa_pending_secret if setup else account.mfa_secret
        if not encrypted or (setup and (account.mfa_secret or not account.mfa_pending_until or account.mfa_pending_until <= now)):
            return None
        totp = pyotp.TOTP(decrypt(encrypted))
        counter = int(now.timestamp()) // 30
        matched = next((n for n in [counter-1,counter,counter+1] if n > account.mfa_last_counter and constant_time_compare(totp.at(n*30), str(code))), None)
        if matched is None:
            if setup:
                return None
            recovery = RecoveryCode.objects.select_for_update().filter(account=account, digest=digest(code), used_at=None).first()
            if not recovery:
                return None
            recovery.used_at = now
            recovery.save()
            audit(account, 'mfa_recovery_used')
            return []
        account.mfa_last_counter = matched
        codes = []
        if setup:
            account.mfa_secret = encrypted
            account.mfa_pending_secret = ''
            account.mfa_pending_until = None
            RecoveryCode.objects.filter(account=account).delete()
            codes = [secrets.token_hex(10) for _ in range(8)]
            RecoveryCode.objects.bulk_create([RecoveryCode(account=account, digest=digest(c)) for c in codes])
        account.save()
        audit(account, 'mfa_enrolled' if setup else 'mfa_verified')
        return codes


def claim_invitation(account_id, code, email):
    with transaction.atomic():
        account = Account.objects.select_for_update().get(pk=account_id)
        if account.status!='active' or not account.verified_at or account.email!=email.strip().lower():
            return False
        candidate = Invitation.objects.filter(digest=digest(code)).first()
        if not candidate:
            audit(account, 'invitation_rejected')
            return False
        # Issuance locks person before invitations; claims use the same order.
        person = Person.objects.select_for_update().get(pk=candidate.person_id)
        invite = Invitation.objects.select_for_update().get(pk=candidate.pk)
        if invite.person_id != person.pk or invite.email.lower()!=account.email or invite.claimed_at or invite.revoked_at or invite.expires_at <= timezone.now():
            audit(account,'invitation_rejected')
            return False
        if (account.person_id and account.person_id!=person.pk) or Account.objects.filter(person=person).exclude(pk=account.pk).exists():
            return False
        account.person = person
        account.save(update_fields=['person'])
        invite.claimed_by = account
        invite.claimed_at = timezone.now()
        invite.save()
        audit(account,'invitation_claimed')
        return True


def dispatch_email(intent_id):
    """One attempt only. Ambiguous outcomes are never blindly retried."""
    from .brevo import send, BrevoFailure
    with transaction.atomic():
        intent = EmailIntent.objects.select_for_update(of=('self',)).select_related('token').get(pk=intent_id)
        if intent.state not in ('pending','blocked'):
            return
        if (intent.expires_at and intent.expires_at <= timezone.now()) or (intent.token and (intent.token.used_at or intent.token.expires_at <= timezone.now())) or (intent.invitation and (intent.invitation.claimed_at or intent.invitation.revoked_at)) :
            intent.state = 'expired'
            intent.encrypted_payload = ''
            intent.save()
            return
        if not settings.BREVO_API_KEY or not settings.WDOS_EMAIL_FROM:
            intent.state = 'blocked'
            intent.error_code = 'not_configured'
            intent.save()
            return
        try:
            payload = json.loads(decrypt(intent.encrypted_payload))
            if not isinstance(payload, dict):
                raise ValueError('Email payload must be an object')
        except (InvalidToken, ValueError, TypeError, UnicodeError):
            intent.state = 'failed'
            intent.error_code = 'invalid_payload'
            intent.encrypted_payload = ''
            intent.finished_at = timezone.now()
            intent.save()
            return
        intent.state = 'sending'
        intent.started_at = timezone.now()
        intent.save()
    # Transaction has committed before contact with Brevo.
    try:
        message_id = send(payload)
        state, error = 'accepted', ''
    except BrevoFailure as exc:
        message_id, state, error = '', exc.state, exc.code
    with transaction.atomic():
        intent = EmailIntent.objects.select_for_update().get(pk=intent_id)
        intent.message_id, intent.state, intent.error_code = message_id, state, error
        intent.finished_at = timezone.now()
        intent.encrypted_payload = ''
        intent.save()
