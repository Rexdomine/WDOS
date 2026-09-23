"""The AUTH-01..09 server-rendered gateway. All mutations require POST + CSRF."""
from django.conf import settings
from django.contrib.auth import login as django_login, get_user_model
from django.contrib.auth.hashers import make_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.debug import sensitive_post_parameters
from . import forms, services
from .models import Account
from .locale import LANGUAGES, catalog, translate, localize_form, logout_preserving_language as django_logout

def _locale(request):
    lang = request.GET.get('lang') or request.session.get('wdos_language') or 'en'
    if lang not in LANGUAGES: lang = 'en'
    request.session['wdos_language'] = lang
    return lang

def _restore_locale(request, lang):
    request.session.flush()
    request.session['wdos_language'] = lang

def page(request, screen, title, lede, form=None, action=None, **extra):
    lang = _locale(request)
    t = catalog(lang)
    if form is not None: localize_form(form, lang)
    values = dict(screen=screen, title=translate(lang, title), lede=translate(lang, lede), form=form, action=translate(lang, action) if action else action, note=translate(lang, extra.pop('note', '')) if extra.get('note') else extra.pop('note', None), lang=lang, language=LANGUAGES[lang], languages=LANGUAGES, translations=t, **extra)
    return render(request, 'accounts/auth.html', values)


def rate(request, scope, identity=''):
    # REMOTE_ADDR is supplied by the server, never arbitrary X-Forwarded-For.
    ip_ok = services.throttle(scope+':ip', request.META.get('REMOTE_ADDR','unknown'), limit=60)
    if not ip_ok:
        return False
    subject_ok = services.throttle(scope+':subject', identity.lower(), limit=10) if identity else True
    return ip_ok and subject_ok


@require_http_methods(['GET'])
def welcome(request):
    return page(request, 'AUTH-01','Welcome to WDOS','Choose how you would like to connect with WODDI today.')


@sensitive_post_parameters('password')
@require_http_methods(['GET','POST'])
def register(request):
    form = forms.RegisterForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        request.session.pop('pending_registration_account', None)
        if not rate(request, 'register', form.cleaned_data['email']):
            form.add_error(None, 'Please wait before trying again.')
        else:
            try:
                account = services.register(form.cleaned_data['name'], form.cleaned_data['email'], form.cleaned_data['password'])
            except ValidationError as exc:
                form.add_error('password', exc)
            else:
                if account is not None:
                    request.session['pending_registration_account'] = {
                        'id': account.pk, 'version': account.security_version
                    }
                    return redirect('accounts:verify')
                form.add_error(None, 'This email is already registered. Sign in or request recovery instead.')
    return page(request,'AUTH-03','Create your WDOS account','Start with the contact details we use to verify your identity and keep one account.',form,'Create account', note='Creating an account does not grant a leadership or HQ role.')


def establish(request, account, mfa=False, remember=False):
    lang = _locale(request)
    django_login(request, account.user, backend='django.contrib.auth.backends.ModelBackend')
    request.session['wdos_language'] = lang
    now = timezone.now().timestamp()
    ttl = settings.WDOS_REMEMBER_TTL if remember else settings.WDOS_SESSION_TTL
    request.session['security_version'] = account.security_version
    request.session['mfa_verified'] = mfa
    request.session['last_activity'] = now
    request.session['absolute_expiry'] = now+ttl
    request.session.set_expiry(ttl if remember else 0)
    request.session.pop('pending_mfa', None)


@sensitive_post_parameters('password')
@require_http_methods(['GET','POST'])
def login(request):
    form = forms.LoginForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        email = form.cleaned_data['email'].strip().lower()
        if not rate(request,'login',email):
            form.add_error(None,'Please wait before trying again.')
        else:
            with transaction.atomic():
                account = Account.objects.select_for_update().select_related('user').filter(email=email).first()
                good = account.user.check_password(form.cleaned_data['password']) if account else False
                if not account:
                    make_password(form.cleaned_data['password'])
                if not good or not account.user.is_active:
                    services.audit(account, 'sign_in_rejected')
                    form.add_error(None,'Email or password was not recognised.')
                elif account.status!='active':
                    lang = _locale(request)
                    pending_registration_account = request.session.get('pending_registration_account')
                    _restore_locale(request, lang)
                    if (isinstance(pending_registration_account, dict)
                            and pending_registration_account.get('id') == account.pk
                            and pending_registration_account.get('version') == account.security_version):
                        request.session['pending_registration_account'] = pending_registration_account
                    request.session['access_notice'] = account.status
                    return redirect('accounts:status')
                elif services.requires_mfa(account):
                    lang = _locale(request)
                    _restore_locale(request, lang)
                    request.session['pending_mfa'] = {'id':account.pk, 'version':account.security_version, 'until':timezone.now().timestamp()+settings.WDOS_MFA_TTL, 'remember':form.cleaned_data['remember']}
                    return redirect('accounts:mfa')
                else:
                    establish(request,account,remember=form.cleaned_data['remember'])
                    services.audit(account,'signed_in')
                    return redirect('accounts:status')
    return page(request,'AUTH-02','Welcome back','Use your WDOS account email and password to continue securely.',form,'Sign in')


@sensitive_post_parameters('code')
@require_http_methods(['GET','POST'])
def verify(request):
    form = forms.VerifyForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        email = form.cleaned_data['email'].lower()
        account = Account.objects.filter(email=email).first()
        pending_registration = request.session.get('pending_registration_account', {})
        if not isinstance(pending_registration, dict):
            pending_registration = {}
        if (rate(request,'verify',email) and account
                and pending_registration.get('id') == account.pk
                and pending_registration.get('version') == account.security_version
                and services.verify_contact(account.pk,form.cleaned_data['code'])):
            request.session.pop('pending_registration_account', None)
            return page(request,'AUTH-04','Contact verified','Your account is ready. Sign in to continue.')
        form.add_error(None,'This code could not be verified. Check your details or request another code.')
    return page(request,'AUTH-04','Verify your contact details','Enter your email and its verification code. Email delivery may be unavailable until review configuration is complete.',form,'Verify contact')


@require_http_methods(['GET','POST'])
def recover(request):
    return email_request(request,'reset')


@require_http_methods(['GET','POST'])
def resend(request):
    return email_request(request,'verify')


def email_request(request,purpose):
    form = forms.EmailForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        email=form.cleaned_data['email'].lower()
        if rate(request,purpose,email) and services.throttle(purpose+':cooldown',email,limit=1,seconds=60):
            services.request_email(email,purpose)
        return page(request,'AUTH-06' if purpose=='reset' else 'AUTH-04','Request received','If the account is eligible, instructions will be attempted by email. This does not confirm delivery. Wait at least one minute before requesting again.')
    return page(request,'AUTH-06' if purpose=='reset' else 'AUTH-04','Request password recovery' if purpose=='reset' else 'Request a new verification code','We will send next steps if eligible, without revealing whether an account exists.',form,'Send recovery link' if purpose=='reset' else 'Request code')


@sensitive_post_parameters('password','confirm','proof')
@require_http_methods(['GET','POST'])
def reset(request):
    form = forms.ResetForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        proof = form.cleaned_data['proof'].split('.',1)
        try:
            ok = len(proof)==2 and rate(request,'reset-consume',proof[0]) and services.reset_password(proof[0],proof[1],form.cleaned_data['password'])
        except ValidationError as exc:
            form.add_error('password',exc)
        else:
            if ok:
                django_logout(request)
                return page(request,'AUTH-07','Password updated','Your previous sessions have been revoked. Sign in with your new password. MFA is still required where enabled.')
            form.add_error(None,'This recovery link is invalid, expired or already used. Request a new link.')
    return page(request,'AUTH-07','Set a new password','Choose a password you have not used here before, then return to sign in.',form,'Save new password')


@sensitive_post_parameters('code')
@require_http_methods(['GET','POST'])
def mfa(request):
    pending=request.session.get('pending_mfa',{})
    account=Account.objects.select_related('user').filter(pk=pending.get('id')).first()
    if not account or not account.user.is_active or account.status!='active' or pending.get('version')!=account.security_version or timezone.now().timestamp()>=pending.get('until',0):
        request.session.pop('pending_mfa',None)
        return redirect('accounts:login')
    setup=not account.mfa_secret
    secret=None
    form=forms.MFAForm(request.POST or None)
    if request.method=='POST' and request.POST.get('begin')=='1' and setup:
        if rate(request,'mfa-begin',str(account.pk)):
            secret=services.begin_mfa(account.pk)
        form=forms.MFAForm()
    elif request.method=='POST' and form.is_valid():
        if rate(request,'mfa',str(account.pk)):
            with transaction.atomic():
                account=Account.objects.select_for_update().select_related('user').get(pk=account.pk)
                # Password reset may have raced the first read.
                result=services.confirm_mfa(account.pk,form.cleaned_data['code'],setup) if account.security_version==pending['version'] else None
                if result is not None:
                    establish(request,account,mfa=True,remember=pending.get('remember',False))
                    if result:
                        return page(request,'AUTH-08','Save your recovery codes','Each code works once. These codes are shown only now. Store them privately.',codes=result)
                    return redirect('accounts:status')
        form.add_error(None,'This code could not be verified. Try a fresh authenticator code or an unused recovery code.')
    # Secret displayed only within the password-authenticated pending session.
    if setup and account.mfa_pending_secret and account.mfa_pending_until and account.mfa_pending_until>timezone.now():
        secret=services.decrypt(account.mfa_pending_secret)
    return page(request,'AUTH-08','Protect your administrator account' if setup else 'Verify your sign-in','Use your authenticator app. Password recovery does not bypass this check.',form,'Verify code',setup=setup,secret=secret)


@sensitive_post_parameters('code')
@require_http_methods(['GET','POST'])
def invitation(request):
    account=getattr(request,'wdos_account',None)
    if not account:
        return redirect('accounts:login')
    form=forms.InvitationForm(request.POST or None)
    if request.method=='POST' and form.is_valid():
        if rate(request,'invite',str(account.pk)) and services.claim_invitation(account.pk,form.cleaned_data['code'],form.cleaned_data['email']):
            account.refresh_from_db()
            return page(request,'AUTH-05','Record linked','Your account is linked to the intended WDOS person. No leadership or HQ role has been granted.',account=account)
        services.audit(account, 'invitation_claim_rejected')
        form.add_error(None,'This invitation cannot be claimed. Check your details or contact your invitation issuer.')
    return page(request,'AUTH-05','Claim your invited record','Confirm the invitation before linking this account to an existing WDOS record.',form,'Claim record')


@require_POST
def logout(request):
    lang = _locale(request)
    django_logout(request)
    request.session['wdos_language'] = lang
    return redirect('accounts:login')


@require_POST
def revoke_sessions(request):
    if not request.wdos_account:
        return redirect('accounts:login')
    with transaction.atomic():
        account=Account.objects.select_for_update().get(pk=request.wdos_account.pk)
        account.security_version+=1
        account.save(update_fields=['security_version'])
        services.audit(account,'all_sessions_revoked')
    django_logout(request)
    return redirect('accounts:login')


@require_http_methods(['GET'])
def status(request):
    account=getattr(request,'wdos_account',None)
    notice=request.session.get('access_notice','signed_out')
    explanations={'pending':'Your email is not verified yet. Verify your contact details to continue.', 'suspended':'Your account is suspended. Contact your WDOS administrator for the permitted next step.', 'expired':'Your session expired or was revoked. Sign in again.', 'mfa':'A second factor is required. Sign in again to verify it.', 'unavailable':'Access is unavailable. Sign in or contact your WDOS administrator.', 'signed_out':'Sign in to check your account. Restricted records are never shown here.'}
    return page(request,'AUTH-09','Check your access status','Your account is active. Further workspace access depends on approved permissions.' if account else explanations.get(notice,explanations['signed_out']),account=account)


@require_http_methods(['GET'])
def session_info(request):
    if not request.wdos_account:
        return JsonResponse({'authenticated':False},status=401)
    return JsonResponse({'authenticated':True,'status':request.wdos_account.status,'mfa_verified':bool(request.session.get('mfa_verified'))})
