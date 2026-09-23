from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "wdos-local-development-only")
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [h for h in os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "foundation",
    "accounts",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.AccountSecurityMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]
ROOT_URLCONF = "wdos_project.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "wdos_project.wsgi.application"

DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL:
    import urllib.parse
    parsed = urllib.parse.urlparse(DATABASE_URL)
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": parsed.path.lstrip("/"),
        "USER": parsed.username,
        "PASSWORD": parsed.password,
        "HOST": parsed.hostname,
        "PORT": parsed.port or 5432,
        "OPTIONS": {"sslmode": os.getenv("DB_SSLMODE", "require")},
    }}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
# Provisional Stage 2 policy; final values require IT approval.
WDOS_VERIFY_TTL = 600
WDOS_RESET_TTL = 1800
WDOS_MFA_TTL = 600
WDOS_IDLE_TTL = 1800
WDOS_SESSION_TTL = 43200
WDOS_REMEMBER_TTL = 604800
WDOS_PUBLIC_ORIGIN = os.getenv("WDOS_PUBLIC_ORIGIN", "https://wdos-staging.onrender.com")
if os.getenv("WDOS_ENVIRONMENT") == "production":
    from urllib.parse import urlsplit
    from django.core.exceptions import ImproperlyConfigured
    explicit_origin = os.getenv("WDOS_PUBLIC_ORIGIN", "")
    try:
        origin = urlsplit(explicit_origin)
        valid_origin = (
            origin.scheme == "https" and bool(origin.hostname)
            and not origin.hostname.endswith(".")
            and origin.hostname != "wdos-staging.onrender.com"
            and not origin.username and not origin.password
            and origin.path in ("", "/") and not origin.query and not origin.fragment
            and origin.port in (None, 443)
        )
    except ValueError:
        valid_origin = False
    if not valid_origin:
        raise ImproperlyConfigured("Production requires an explicit, production-specific HTTPS WDOS_PUBLIC_ORIGIN.")
    WDOS_PUBLIC_ORIGIN = explicit_origin.rstrip("/")
BREVO_API_KEY = os.getenv("WDOS_BREVO_API_KEY", "")
WDOS_EMAIL_FROM = os.getenv("WDOS_EMAIL_FROM", "")
SESSION_COOKIE_SECURE = os.getenv("WDOS_SECURE_COOKIES", "1") == "1"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_AGE = WDOS_SESSION_TTL
LOGIN_URL = "/auth/login/"

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
