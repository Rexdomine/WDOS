from django.utils import timezone


def allowed(request, *, role, network, geography, function):
    """Exact-scope grants only; no implicit HQ, assistant or superuser inheritance."""
    account = getattr(request, 'wdos_account', None)
    if not account or not request.session.get('mfa_verified'):
        return False
    return account.accessgrant_set.filter(role=role, network=network, geography=geography, function=function, revoked_at=None, expires_at__gt=timezone.now()).exists()
