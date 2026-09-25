"""The AUTH-01..09 server-rendered gateway. All mutations require POST + CSRF."""
import math
import uuid

from cryptography.fernet import InvalidToken
from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.db import transaction
from django.contrib.auth import login as django_login
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from . import forms, services
from .locale import LANGUAGES, catalog, localize_form, logout_preserving_language as django_logout, translate
from .models import Account, ActionToken


LOCALE_COOKIE = 'wdos_language'
LOCALE_COOKIE_AGE = 31536000
VERIFY_RESEND_SECONDS = 60
SUPPORT_URL = 'https://thewoddi.org/contact.html'
RESET_RETRY_SESSION_KEY = 'reset_retry_proof'
RESET_FLOW_QUERY_KEY = 'reset_flow'


def _locale(request):
    lang = (request.GET.get('lang') or request.COOKIES.get(LOCALE_COOKIE)
            or request.session.get(LOCALE_COOKIE)
            or getattr(request, 'wdos_locale_after_logout', None) or 'en')
    return lang if lang in LANGUAGES else 'en'


def _restore_locale(request, lang):
    request.session.flush()
    request.session[LOCALE_COOKIE] = lang


def _set_locale_cookie(response, lang):
    response.set_cookie(
        LOCALE_COOKIE, lang, max_age=LOCALE_COOKIE_AGE,
        httponly=False, secure=settings.SESSION_COOKIE_SECURE, samesite='Lax',
    )
    return response


def _masked_email(email):
    """Retain enough context to recognise a destination without disclosing it."""
    if not email or '@' not in email:
        return ''
    local, domain = email.rsplit('@', 1)
    domain_name, dot, suffix = domain.rpartition('.')
    masked_domain = (domain_name[:1] + '***') if domain_name else '***'
    if dot:
        masked_domain += dot + suffix
    return (local[:1] + '***' if local else '***') + '@' + masked_domain


def _workspace_destination(account):
    """Route authenticated users without trusting a client-side destination."""
    from .models import OnboardingDraft
    draft = OnboardingDraft.objects.filter(account=account).first()
    if draft and draft.state == 'accepted' and hasattr(draft, 'membership'):
        return reverse('app-shell')
    return reverse('onboarding:step', args=[draft.next_step if draft else 1])


def page(request, screen, title, lede, form=None, action=None, **extra):
    lang = _locale(request)
    translations = catalog(lang)
    if form is not None:
        form.label_suffix = ''
        localize_form(form, lang)
    note = extra.pop('note', None)
    values = {
        'screen': screen,
        'title': translate(lang, title),
        'lede': translate(lang, lede),
        'form': form,
        'action': translate(lang, action) if action else None,
        'note': translate(lang, note) if note else None,
        'lang': lang,
        'language': LANGUAGES[lang],
        'languages': LANGUAGES,
        'translations': translations,
        **extra,
    }
    return _set_locale_cookie(render(request, 'accounts/auth.html', values), lang)


def rate(request, scope, identity=''):
    # REMOTE_ADDR is supplied by the server, never arbitrary X-Forwarded-For.
    if not services.throttle(scope + ':ip', request.META.get('REMOTE_ADDR', 'unknown'), limit=60):
        return False
    return services.throttle(scope + ':subject', identity.lower(), limit=10) if identity else True


def _pending_registration_account(request):
    pending = request.session.get('pending_registration_account')
    if not isinstance(pending, dict) or set(pending) != {'id', 'version'}:
        return None
    try:
        account_id = int(pending['id'])
        version = int(pending['version'])
    except (TypeError, ValueError, AttributeError):
        return None
    if account_id < 1 or version < 1:
        return None
    return Account.objects.filter(
        pk=account_id, security_version=version, status='pending', user__is_active=True,
    ).first()


def _verify_resend_context(account):
    latest = ActionToken.objects.filter(account=account, purpose='verify').order_by('-created_at').first()
    if not latest:
        return {'resend_remaining': 0, 'resend_issued_at': 0}
    elapsed = (timezone.now() - latest.created_at).total_seconds()
    return {
        'resend_remaining': max(0, math.ceil(VERIFY_RESEND_SECONDS - elapsed)),
        'resend_issued_at': int(latest.created_at.timestamp()),
    }


def _verification_page(request, account, form=None, feedback=None):
    if account is None:
        return page(
            request, 'AUTH-04', 'Verification link unavailable',
            'Start from registration or sign in again so we can safely identify the account to verify.',
            verification_unbound=True,
        )
    return page(
        request, 'AUTH-04', 'Verify your contact details',
        'Enter the code sent to your email. Request another after the timer ends.',
        form or forms.VerifyForm(), 'Verify contact',
        masked_destination=_masked_email(account.email),
        verification_bound=True,
        resend_feedback=translate(_locale(request), feedback) if feedback else None,
        **_verify_resend_context(account),
    )


@require_http_methods(['GET'])
def welcome(request):
    account = getattr(request, 'wdos_account', None)
    if account:
        return redirect(_workspace_destination(account))
    return page(request, 'AUTH-01', 'Welcome to WDOS',
                'Choose how you would like to connect with WODDI today.')


@sensitive_post_parameters('password')
@require_http_methods(['GET', 'POST'])
def register(request):
    form = forms.RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        request.session.pop('pending_registration_account', None)
        if not rate(request, 'register', form.cleaned_data['email']):
            form.add_error(None, 'Please wait before trying again.')
        else:
            try:
                account = services.register(
                    form.cleaned_data['name'], form.cleaned_data['email'], form.cleaned_data['password'],
                )
            except ValidationError as exc:
                form.add_error('password', exc)
            else:
                if account is not None:
                    request.session['pending_registration_account'] = {
                        'id': account.pk, 'version': account.security_version,
                    }
                    return redirect('accounts:verify')
                form.add_error(None, 'This email is already registered. Sign in or request recovery instead.')
    return page(
        request, 'AUTH-03', 'Create your WDOS account',
        'Start with the contact details we use to verify your identity and keep one account.',
        form, 'Create account',
        note='Creating an account does not grant a leadership or HQ role.',
    )


def establish(request, account, mfa=False, remember=False):
    lang = _locale(request)
    django_login(request, account.user, backend='django.contrib.auth.backends.ModelBackend')
    request.session[LOCALE_COOKIE] = lang
    now = timezone.now().timestamp()
    ttl = settings.WDOS_REMEMBER_TTL if remember else settings.WDOS_SESSION_TTL
    request.session['security_version'] = account.security_version
    request.session['mfa_verified'] = mfa
    request.session['last_activity'] = now
    request.session['absolute_expiry'] = now + ttl
    request.session.set_expiry(ttl if remember else 0)
    request.session.pop('pending_mfa', None)


@sensitive_post_parameters('password')
@require_http_methods(['GET', 'POST'])
def login(request):
    form = forms.LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].strip().lower()
        if not rate(request, 'login', email):
            form.add_error(None, 'Please wait before trying again.')
        else:
            with transaction.atomic():
                account = Account.objects.select_for_update().select_related('user').filter(email=email).first()
                good = account.user.check_password(form.cleaned_data['password']) if account else False
                if not account:
                    make_password(form.cleaned_data['password'])
                if not good or not account.user.is_active:
                    services.audit(account, 'sign_in_rejected')
                    form.add_error(None, 'Email or password was not recognised.')
                elif account.status != 'active':
                    lang = _locale(request)
                    _restore_locale(request, lang)
                    if account.status == 'pending':
                        request.session['pending_registration_account'] = {
                            'id': account.pk, 'version': account.security_version,
                        }
                    request.session['access_notice'] = account.status
                    return redirect('accounts:status')
                elif services.requires_mfa(account):
                    lang = _locale(request)
                    _restore_locale(request, lang)
                    request.session['pending_mfa'] = {
                        'id': account.pk,
                        'version': account.security_version,
                        'until': timezone.now().timestamp() + settings.WDOS_MFA_TTL,
                        'remember': form.cleaned_data['remember'],
                    }
                    return redirect('accounts:mfa')
                else:
                    establish(request, account, remember=form.cleaned_data['remember'])
                    services.audit(account, 'signed_in')
                    return redirect(_workspace_destination(account))
    return page(
        request, 'AUTH-02', 'Welcome back',
        'Use your WDOS account email and password to continue securely.',
        form, 'Sign in',
    )


@sensitive_post_parameters('code')
@require_http_methods(['GET', 'POST'])
def verify(request):
    account = _pending_registration_account(request)
    if account is None:
        return _verification_page(request, None)
    form = forms.VerifyForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        if (rate(request, 'verify', str(account.pk))
                and services.verify_contact(account.pk, form.cleaned_data['code'])):
            request.session.pop('pending_registration_account', None)
            request.session.pop('access_notice', None)
            return page(
                request, 'AUTH-04', 'Contact verified',
                'Your account is ready. Sign in to continue.',
                success_action='login',
            )
        form.add_error(None, 'This code could not be verified. Check your details or request another code.')
    return _verification_page(request, account, form)


@require_http_methods(['GET', 'POST'])
def recover(request):
    form = forms.EmailForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].lower()
        if rate(request, 'reset', email) and services.throttle(
                'reset:cooldown', email, limit=1, seconds=60):
            services.request_email(email, 'reset')
        return page(
            request, 'AUTH-06', 'Check your inbox',
            'If an eligible account exists, recovery instructions will be sent to that address.',
            recovery_requested=True,
        )
    return page(
        request, 'AUTH-06', 'Request password recovery',
        'We will send next steps if eligible, without revealing whether an account exists.',
        form, 'Send recovery link',
    )


@sensitive_post_parameters()
@require_POST
def resend(request):
    account = _pending_registration_account(request)
    if account is None:
        return _verification_page(request, None)
    context = _verify_resend_context(account)
    feedback = 'Please wait for the countdown before requesting another code.'
    if context['resend_remaining'] == 0:
        if (rate(request, 'verify-resend', str(account.pk))
                and services.throttle('verify:cooldown', account.email, limit=1, seconds=60)):
            services.request_email(account.email, 'verify')
            feedback = 'A new code was requested for the same verified destination.'
        else:
            feedback = 'Please wait before trying again.'
    return _verification_page(request, account, feedback=feedback)


def _valid_reset_proof(value):
    if not value or len(value) > 200:
        return None
    token_id, separator, secret = value.partition('.')
    if not separator or not secret:
        return None
    try:
        uuid.UUID(token_id)
    except (ValueError, TypeError, AttributeError):
        return None
    return value


def _reset_flow_id(proof):
    token_id, separator, _ = (proof or '').partition('.')
    if not separator:
        return None
    try:
        return str(uuid.UUID(token_id))
    except (ValueError, TypeError, AttributeError):
        return None


def _reset_retry_proof(request):
    raw_posted = request.POST.get('proof', '')
    if raw_posted:
        return _valid_reset_proof(raw_posted)
    flow_id = request.GET.get(RESET_FLOW_QUERY_KEY) or request.POST.get(RESET_FLOW_QUERY_KEY)
    proofs = request.session.get(RESET_RETRY_SESSION_KEY, {})
    if isinstance(proofs, str):
        # Legacy scalar proofs have no flow binding.  Discard them rather than
        # allowing a stale proof to survive a replacement-flow rejection.
        request.session.pop(RESET_RETRY_SESSION_KEY, None)
        request.session.modified = True
        return None
    if not isinstance(proofs, dict) or not flow_id:
        return None
    encrypted = proofs.get(flow_id)
    if not encrypted:
        return None
    try:
        return _valid_reset_proof(services.decrypt(encrypted))
    except (InvalidToken, ValueError, TypeError, UnicodeError):
        proofs.pop(flow_id, None)
        request.session[RESET_RETRY_SESSION_KEY] = proofs
        request.session.modified = True
        return None


def _store_reset_retry_proof(request, proof):
    flow_id = _reset_flow_id(proof)
    if not flow_id:
        return None
    new_session = not request.session.session_key
    if new_session:
        request.session.save()
    session_key = request.session.session_key
    with transaction.atomic():
        Session.objects.select_for_update().get(session_key=session_key)
        store = SessionStore(session_key=session_key)
        session_data = store.load()
        proofs = session_data.get(RESET_RETRY_SESSION_KEY, {})
        if not isinstance(proofs, dict):
            proofs = {}
        proofs[flow_id] = services.encrypt(proof)
        session_data[RESET_RETRY_SESSION_KEY] = dict(list(proofs.items())[-4:])
        store._session_cache = session_data
        store.save(must_create=False)
    request.session._session_cache = session_data
    request.session.modified = new_session
    return flow_id


def _clear_reset_retry_proof(request, proof=None):
    flow_id = _reset_flow_id(proof) or request.GET.get(RESET_FLOW_QUERY_KEY) or request.POST.get(RESET_FLOW_QUERY_KEY)
    if not flow_id:
        return
    new_session = not request.session.session_key
    if new_session:
        request.session.save()
    session_key = request.session.session_key
    with transaction.atomic():
        Session.objects.select_for_update().get(session_key=session_key)
        store = SessionStore(session_key=session_key)
        session_data = store.load()
        proofs = session_data.get(RESET_RETRY_SESSION_KEY, {})
        if not isinstance(proofs, dict):
            proofs = {}
        proofs.pop(flow_id, None)
        if proofs:
            session_data[RESET_RETRY_SESSION_KEY] = proofs
        else:
            session_data.pop(RESET_RETRY_SESSION_KEY, None)
        store._session_cache = session_data
        store.save(must_create=False)
    request.session._session_cache = session_data
    request.session.modified = new_session


def _invalid_reset_page(request, proof=None):
    _clear_reset_retry_proof(request, proof)
    return page(
        request, 'AUTH-07', 'Link expired',
        'This password reset link can no longer be used.',
        reset_invalid=True,
    )


@sensitive_post_parameters('password', 'confirm', 'proof')
@require_http_methods(['GET', 'POST'])
def reset(request):
    if request.method == 'GET':
        proof_bound = _reset_retry_proof(request)
        if proof_bound and not services.is_live_reset_proof(*proof_bound.split('.', 1)):
            return _invalid_reset_page(request, proof_bound)
        return page(
            request, 'AUTH-07', 'Set a new password',
            'Choose a password you have not used here before, then return to sign in.',
            forms.ResetForm(), 'Save new password', reset_requires_fragment=proof_bound is None,
            reset_proof_bound=proof_bound is not None,
            reset_flow=_reset_flow_id(proof_bound) if proof_bound else None,
        )

    if request.POST.get('preserve_fragment') == '1':
        proof = _valid_reset_proof(request.POST.get('proof', ''))
        if proof is None or not services.is_live_reset_proof(*proof.split('.', 1)):
            if isinstance(request.session.get(RESET_RETRY_SESSION_KEY), str):
                request.session.pop(RESET_RETRY_SESSION_KEY, None)
                request.session.modified = True
            return JsonResponse({'error': 'invalid proof'}, status=400)
        flow_id = _store_reset_retry_proof(request, proof)
        response = HttpResponse(status=204)
        if flow_id:
            response['X-Reset-Flow'] = flow_id
        return response

    proof = _reset_retry_proof(request)
    if proof is None:
        return _invalid_reset_page(request)
    proof_is_live = services.is_live_reset_proof(*proof.split('.', 1))
    if not proof_is_live:
        return _invalid_reset_page(request, proof)
    form = forms.ResetForm(request.POST)
    if not form.is_valid():
        _store_reset_retry_proof(request, proof)
        return page(
            request, 'AUTH-07', 'Set a new password',
            'Choose a password you have not used here before, then return to sign in.',
            form, 'Save new password', reset_proof_bound=True,
            reset_flow=_reset_flow_id(proof),
        )

    token_id, secret = proof.split('.', 1)
    try:
        ok = (rate(request, 'reset-consume', token_id)
              and services.reset_password(token_id, secret, form.cleaned_data['password']))
    except ValidationError as exc:
        if not services.is_live_reset_proof(token_id, secret):
            return _invalid_reset_page(request, proof)
        _store_reset_retry_proof(request, proof)
        form.add_error('password', exc)
        return page(
            request, 'AUTH-07', 'Set a new password',
            'Choose a password you have not used here before, then return to sign in.',
            form, 'Save new password', reset_proof_bound=True,
            reset_flow=_reset_flow_id(proof),
        )
    if not ok:
        return _invalid_reset_page(request, proof)

    _clear_reset_retry_proof(request, proof)
    lang = _locale(request)
    django_logout(request)
    request.wdos_locale_after_logout = lang
    return page(
        request, 'AUTH-07', 'Password updated',
        'Your previous sessions have been revoked. Sign in with your new password. MFA is still required where enabled.',
        success_action='login',
    )


@sensitive_post_parameters('code')
@require_http_methods(['GET', 'POST'])
def mfa(request):
    pending = request.session.get('pending_mfa', {})
    account = Account.objects.select_related('user').filter(pk=pending.get('id')).first()
    if (not account or not account.user.is_active or account.status != 'active'
            or pending.get('version') != account.security_version
            or timezone.now().timestamp() >= pending.get('until', 0)):
        request.session.pop('pending_mfa', None)
        return redirect('accounts:login')

    setup = not account.mfa_secret
    secret = None
    form = None
    if request.method == 'POST' and request.POST.get('begin') == '1' and setup:
        if rate(request, 'mfa-begin', str(account.pk)):
            secret = services.begin_mfa(account.pk)
        if secret:
            # begin_mfa() writes a replacement pending secret; do not let the
            # pre-POST ORM snapshot suppress the freshly-created form.
            account.refresh_from_db()
            form = forms.MFAForm()
    elif request.method == 'POST':
        form = forms.MFAForm(request.POST)
        if form.is_valid() and rate(request, 'mfa', str(account.pk)):
            with transaction.atomic():
                account = Account.objects.select_for_update().select_related('user').get(pk=account.pk)
                result = (services.confirm_mfa(account.pk, form.cleaned_data['code'], setup)
                          if account.security_version == pending['version'] else None)
                if result is not None:
                    establish(request, account, mfa=True, remember=pending.get('remember', False))
                    if setup:
                        return page(
                            request, 'AUTH-08', 'Save your recovery codes',
                            'Each code works once. These codes are shown only now. Store them privately.',
                            codes=result, workspace_url=_workspace_destination(account),
                        )
                    return redirect(_workspace_destination(account))
        if form.is_bound:
            form.add_error(None, 'This code could not be verified. Try a fresh authenticator code or an unused recovery code.')

    if setup and not secret and account.mfa_pending_secret and account.mfa_pending_until:
        if account.mfa_pending_until > timezone.now():
            secret = services.decrypt(account.mfa_pending_secret)
            form = form or forms.MFAForm()
        elif request.method == 'POST':
            form = None
    elif not setup and request.method == 'GET':
        form = forms.MFAForm()
    title = 'Protect your administrator account' if setup else 'Verify your sign-in'
    lede = ('Enrol an approved second factor and save recovery codes somewhere private.' if setup
            else 'Use your authenticator app. Password recovery does not bypass this check.')
    return page(
        request, 'AUTH-08', title, lede, form, 'Verify code' if form else None,
        setup=setup, secret=secret, mfa_initial=setup and not secret,
        mfa_challenge=not setup,
    )


@sensitive_post_parameters('code')
@require_http_methods(['GET', 'POST'])
def invitation(request):
    account = getattr(request, 'wdos_account', None)
    if not account:
        return redirect('accounts:login')
    if account.person_id:
        return page(
            request, 'AUTH-05', 'Record linked',
            'Your account is linked to the intended WDOS person. No leadership or HQ role has been granted.',
            account=account, invitation_linked=True,
        )
    form = forms.InvitationForm(request.POST or None, initial={'email': account.email})
    if request.method == 'POST' and form.is_valid():
        if (rate(request, 'invite', str(account.pk))
                and services.claim_invitation(account.pk, form.cleaned_data['code'], form.cleaned_data['email'])):
            account.refresh_from_db()
            return page(
                request, 'AUTH-05', 'Record linked',
                'Your account is linked to the intended WDOS person. No leadership or HQ role has been granted.',
                account=account, invitation_linked=True,
            )
        services.audit(account, 'invitation_claim_rejected')
        form.add_error(None, 'This invitation cannot be claimed. Check your details or contact your invitation issuer.')
    return page(
        request, 'AUTH-05', 'Claim your invited record',
        'Confirm the invitation before linking this account to an existing WDOS record.',
        form, 'Claim record', invitation_form=True,
    )


@require_POST
def logout(request):
    lang = _locale(request)
    was_authenticated = request.user.is_authenticated
    django_logout(request)
    if was_authenticated:
        request.session[LOCALE_COOKIE] = lang
    return _set_locale_cookie(redirect('accounts:login'), lang)


@require_POST
def revoke_sessions(request):
    if not request.wdos_account:
        return redirect('accounts:login')
    with transaction.atomic():
        account = Account.objects.select_for_update().get(pk=request.wdos_account.pk)
        account.security_version += 1
        account.save(update_fields=['security_version'])
        services.audit(account, 'all_sessions_revoked')
    lang = django_logout(request)
    return _set_locale_cookie(redirect('accounts:login'), lang)


@require_http_methods(['GET'])
def status(request):
    account = getattr(request, 'wdos_account', None)
    notice = 'active' if account else request.session.get('access_notice', 'signed_out')
    variants = {
        'active': ('Account active', 'Your account is active. Further workspace access depends on approved permissions.',
                   'invitation' if account and not account.person_id else None),
        'pending': ('Verification pending', 'Your email is not verified yet. Verify your contact details to continue.', 'verify'),
        'suspended': ('Access restricted', 'This workspace is not available to your current account. Contact the authorized support team.', 'help'),
        'expired': ('Session expired', 'Sign in again to continue. Sensitive actions have not been submitted.', 'login'),
        'mfa': ('Additional verification required', 'A second factor is required. Sign in again to verify it.', 'login'),
        'unavailable': ('Access restricted', 'Access is unavailable. Sign in or contact the authorized support team.', 'help'),
        'signed_out': ('Sign in required', 'Sign in to check your account. Restricted records are never shown here.', 'login'),
    }
    status_title, status_text, status_action = variants.get(notice, variants['signed_out'])
    return page(
        request, 'AUTH-09', 'Check your access status',
        'Your account status and safest next step are shown without exposing restricted records.',
        account=account, status_kind=notice,
        status_title=translate(_locale(request), status_title),
        status_text=translate(_locale(request), status_text),
        status_action=status_action, onboarding_available=bool(account),
    )


@require_http_methods(['GET'])
def session_info(request):
    if not request.wdos_account:
        return JsonResponse({'authenticated': False}, status=401)
    return JsonResponse({
        'authenticated': True,
        'status': request.wdos_account.status,
        'mfa_verified': bool(request.session.get('mfa_verified')),
    })


@require_http_methods(['GET'])
def help_page(request):
    return page(
        request, 'HELP', 'Help with your WDOS account',
        'Use the safe recovery routes below. Support cannot bypass account ownership, verification, or MFA.',
        help_page=True, contact_url=SUPPORT_URL,
    )


@require_http_methods(['GET'])
def privacy(request):
    return page(
        request, 'PRIVACY', 'Privacy notice',
        'WODDI provides the applicable privacy information. Use the official contact page for policy details.',
        policy_page=True, contact_url=SUPPORT_URL,
    )


@require_http_methods(['GET'])
def terms(request):
    return page(
        request, 'TERMS', 'Terms',
        'WODDI provides the applicable terms. Use the official contact page for policy details.',
        policy_page=True, contact_url=SUPPORT_URL,
    )
