"""Recheck durable eligibility, revocation and second-factor authority every request."""
from django.conf import settings
from .locale import logout_preserving_language as logout
from django.shortcuts import redirect
from django.utils import timezone
from .models import Account
from .services import requires_mfa


class AccountSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request._wdos_upload_rejected = bool(request.META.get('wdos.raw_body_rejected'))
        request.wdos_account = None
        if request.user.is_authenticated:
            account = Account.objects.select_related('user').filter(user=request.user).first()
            now = timezone.now().timestamp()
            reason = None
            if not account or not request.user.is_active or account.status != 'active':
                reason = 'unavailable'
            elif request.session.get('security_version') != account.security_version:
                reason = 'expired'
            elif now >= request.session.get('absolute_expiry', 0) or now >= request.session.get('last_activity', 0) + settings.WDOS_IDLE_TTL:
                reason = 'expired'
            elif requires_mfa(account) and not request.session.get('mfa_verified'):
                reason = 'mfa'
            if reason:
                lang = logout(request)
                request.wdos_locale_after_logout = lang
                request.session['access_notice'] = reason
            else:
                request.wdos_account = account
                request.session['last_activity'] = now
        if request.path.startswith('/admin/'):
            # One sign-in gateway: Django admin cannot bypass MFA or account status.
            if not request.wdos_account or not request.user.is_staff or not request.session.get('mfa_verified'):
                response = redirect('accounts:login')
                lang = getattr(request, 'wdos_locale_after_logout', None)
                if lang:
                    response.set_cookie(
                        'wdos_language', lang, max_age=31536000,
                        httponly=False, secure=settings.SESSION_COOKIE_SECURE, samesite='Lax',
                    )
                return response
        response = self.get_response(request)
        lang = getattr(request, 'wdos_locale_after_logout', None)
        if lang:
            response.set_cookie(
                'wdos_language', lang, max_age=31536000,
                httponly=False, secure=settings.SESSION_COOKIE_SECURE, samesite='Lax',
            )
        if request.path.startswith(('/auth/', '/app', '/admin/', '/onboarding/', '/foundation/')) or request.path == '/':
            response['Cache-Control'] = 'no-store, private'
            response['Referrer-Policy'] = 'same-origin'
            response['X-Robots-Tag'] = 'noindex, nofollow'
        return response
