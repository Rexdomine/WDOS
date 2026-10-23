from pathlib import Path
import os
import json
import sys

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local .env file values if present (without overriding existing environment variables)
_env_path = BASE_DIR / ".env"
_is_test_run = any(arg == "test" or arg.endswith("test") for arg in sys.argv)
if _env_path.exists():
    for _raw_line in _env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        _line = _raw_line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        _k = _k.strip()
        _v = _v.strip()
        if _is_test_run and _k in ("WDOS_ONBOARDING_POLICY_JSON", "WDOS_SECURE_COOKIES"):
            continue
        if _k and (_k not in os.environ or not os.environ[_k]):
            os.environ[_k] = _v

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
    "wdos_project.request_limits.RawBodyRejectedCsrfBypassMiddleware",
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
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3", "OPTIONS": {"timeout": 30}}}

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
WDOS_IDLE_TTL = int(os.getenv("WDOS_IDLE_TTL", "86400"))
WDOS_SESSION_TTL = int(os.getenv("WDOS_SESSION_TTL", "86400"))
WDOS_REMEMBER_TTL = int(os.getenv("WDOS_REMEMBER_TTL", "604800"))
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
            and not explicit_origin.endswith(("?", "#"))
            and origin.port in (None, 443)
        )
    except ValueError:
        valid_origin = False
    if not valid_origin:
        raise ImproperlyConfigured("Production requires an explicit, production-specific HTTPS WDOS_PUBLIC_ORIGIN.")
    WDOS_PUBLIC_ORIGIN = explicit_origin.rstrip("/")
BREVO_API_KEY = os.getenv("WDOS_BREVO_API_KEY", "")
WDOS_EMAIL_FROM = os.getenv("WDOS_EMAIL_FROM", "")
DEFAULT_ONBOARDING_POLICY = {
    'version': 'wdos-policy-2026.1',
    'approval_reference': 'WDOS Operational Governance & Privacy Policy 2026',
    'privacy_notice': 'WDOS collects and processes your personal details, chapter affiliation, and communication preferences solely for membership administration, leadership services, and community coordination under authorized WODDI community privacy standards.',
    'eligibility': [
        {'code': 'adult', 'label': 'Adult Member (18+)', 'network': 'WGMN', 'basis': 'Adult membership criteria verified'},
        {'code': 'youth', 'label': 'Youth Member (15–24)', 'network': 'WNNN', 'basis': 'Youth membership criteria verified'},
    ],
    'homes': [
        {'code': 'lagos-hq', 'label': 'Lagos Central Chapter', 'network': 'WGMN', 'country': 'Nigeria', 'region': 'Lagos', 'district': 'Ikeja', 'kind': 'chapter'},
        {'code': 'nairobi-hq', 'label': 'Nairobi Kilimani Chapter', 'network': 'WGMN', 'country': 'Kenya', 'region': 'Nairobi', 'district': 'Kilimani', 'kind': 'chapter'},
        {'code': 'lagos-youth', 'label': 'Lagos Next-Gen Youth Hub', 'network': 'WNNN', 'country': 'Nigeria', 'region': 'Lagos', 'district': 'Ikeja', 'kind': 'chapter'},
        {'code': 'nairobi-youth', 'label': 'Nairobi Youth Tech Chapter', 'network': 'WNNN', 'country': 'Kenya', 'region': 'Nairobi', 'district': 'Kilimani', 'kind': 'chapter'},
    ],
    'review_role': 'onboarding-reviewer',
    'review_function': 'onboarding-approval',
}

_raw_policy_env = os.getenv("WDOS_ONBOARDING_POLICY_JSON")
if _raw_policy_env is not None and _raw_policy_env != "null":
    try:
        WDOS_ONBOARDING_POLICY = json.loads(_raw_policy_env)
    except (TypeError, ValueError, json.JSONDecodeError):
        WDOS_ONBOARDING_POLICY = None
elif any(arg == "test" or arg.endswith("test") for arg in sys.argv):
    WDOS_ONBOARDING_POLICY = None
else:
    WDOS_ONBOARDING_POLICY = DEFAULT_ONBOARDING_POLICY
SESSION_COOKIE_SECURE = os.getenv("WDOS_SECURE_COOKIES", "1") == "1"
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
# Reject oversized multipart bodies before Django upload handlers spool files.
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
FILE_UPLOAD_HANDLERS = [
    "wdos_project.upload_handlers.UploadSizeLimitHandler",
    "django.core.files.uploadhandler.MemoryFileUploadHandler",
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
]
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

# Stage 10 Multilingua & Event Provider Configuration
MEETING_VIDEO_PROVIDER = os.getenv("MEETING_VIDEO_PROVIDER", "zoom")
MEETING_TRANSLATION_PROVIDER = os.getenv("MEETING_TRANSLATION_PROVIDER", "azure")
ZOOM_SDK_KEY = os.getenv("ZOOM_SDK_KEY", "wdos-dev-zoom-sdk-key")
ZOOM_SDK_SECRET = os.getenv("ZOOM_SDK_SECRET", "wdos-dev-zoom-sdk-secret-hs256-min-32-bytes")
AZURE_SPEECH_KEY = os.getenv("AZURE_SPEECH_KEY", "wdos-dev-azure-speech-key")
AZURE_SPEECH_KEY_2 = os.getenv("AZURE_SPEECH_KEY_2", "")
AZURE_SPEECH_REGION = os.getenv("AZURE_SPEECH_REGION", "eastus")


