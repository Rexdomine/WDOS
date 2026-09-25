import os
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import Role
from accounts.models import OnboardingDraft
from accounts.locale import LANGUAGES, catalog


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        migrations = _migration_count()
        roles = Role.objects.filter(is_system=True).count()
        db = "ok"
    except Exception:
        migrations = None
        roles = None
        db = "degraded"
    status = "ok" if db == "ok" else "degraded"
    return JsonResponse({
        "status": status,
        "service": "wdos",
        "environment": os.getenv("WDOS_ENVIRONMENT", "local"),
        "database": db,
        "migration_rows": migrations,
        "system_role_rows": roles,
        "checked_at": timezone.now().isoformat(),
    }, status=200 if status == "ok" else 503)


def _migration_count():
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM django_migrations")
        return cursor.fetchone()[0]


def app_shell(request):
    account = getattr(request, 'wdos_account', None)
    if not account:
        return redirect('/auth/login/')
    if (
        account.status != 'active'
        or not OnboardingDraft.objects.filter(
            account=account,
            state='accepted',
            membership__isnull=False,
        ).exists()
    ):
        return redirect('/auth/status/')
    lang = request.COOKIES.get('wdos_language') or request.session.get('wdos_language', 'en')
    if lang not in LANGUAGES:
        lang = 'en'
    return render(request, "foundation/app_shell.html", {
        "environment": os.getenv("WDOS_ENVIRONMENT", "local"),
        "lang": lang,
        "direction": LANGUAGES[lang]['dir'],
        "translations": catalog(lang),
    })
