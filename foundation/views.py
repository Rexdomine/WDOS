import os
from django.http import JsonResponse
from django.db import connection


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        db = "ok"
    except Exception:
        db = "degraded"
    status = "ok" if db == "ok" else "degraded"
    return JsonResponse({
        "status": status,
        "service": "wdos",
        "environment": os.getenv("WDOS_ENVIRONMENT", "local"),
        "database": db,
    }, status=200 if status == "ok" else 503)


def app_shell(request):
    return JsonResponse({
        "service": "wdos",
        "stage": "foundation",
        "framework": "django",
        "environment": os.getenv("WDOS_ENVIRONMENT", "local"),
        "message": "WDOS Stage 1 Django foundation shell",
    })
