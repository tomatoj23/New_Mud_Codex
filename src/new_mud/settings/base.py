import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]


def _json_string_map(name: str) -> dict[str, str]:
    try:
        value = json.loads(os.getenv(name, "{}"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(value, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    ):
        return {}
    return value


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS = [
    value.strip()
    for value in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if value.strip()
]

INSTALLED_APPS = [
    "daphne",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "channels",
    "new_mud.apps.health",
    "new_mud.apps.content",
    "new_mud.apps.identity",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "new_mud.apps.identity.middleware.AuthNoStoreMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "new_mud.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

ASGI_APPLICATION = "new_mud.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "new_mud"),
        "USER": os.getenv("POSTGRES_USER", "new_mud"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "new_mud"),
        "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
        "PORT": int(os.getenv("POSTGRES_PORT", "5432")),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"connect_timeout": int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "5"))},
    }
}

CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CONTENT_INSTANCE_ID = os.getenv("NEW_MUD_INSTANCE_ID", "default")
CONTENT_STARTUP_ENABLED = True

AUTH_ALLOWED_ORIGINS = [
    value.strip()
    for value in os.getenv(
        "NEW_MUD_AUTH_ALLOWED_ORIGINS",
        "https://localhost,https://127.0.0.1",
    ).split(",")
    if value.strip()
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
AUTH_ACCESS_TOKEN_TTL_SECONDS = int(os.getenv("NEW_MUD_ACCESS_TOKEN_TTL_SECONDS", "900"))
AUTH_REFRESH_TOKEN_TTL_SECONDS = int(
    os.getenv("NEW_MUD_REFRESH_TOKEN_TTL_SECONDS", str(30 * 24 * 60 * 60))
)
AUTH_TOKEN_SIGNING_KEY = os.getenv("NEW_MUD_AUTH_TOKEN_SIGNING_KEY", "")
AUTH_TERMINAL_SECRET_CLEANUP_GRACE_SECONDS = int(
    os.getenv("NEW_MUD_TERMINAL_SECRET_CLEANUP_GRACE_SECONDS", str(24 * 60 * 60))
)
AUTH_REFRESH_REQUEST_RETRY_WINDOW_SECONDS = int(
    os.getenv("NEW_MUD_REFRESH_REQUEST_RETRY_WINDOW_SECONDS", str(24 * 60 * 60))
)
AUTH_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("NEW_MUD_AUTH_RATE_LIMIT_WINDOW_SECONDS", "900"))
AUTH_REGISTRATION_RATE_LIMIT_ACCOUNT = int(
    os.getenv("NEW_MUD_REGISTRATION_RATE_LIMIT_ACCOUNT", "5")
)
AUTH_REGISTRATION_RATE_LIMIT_IP = int(os.getenv("NEW_MUD_REGISTRATION_RATE_LIMIT_IP", "50"))
AUTH_LOGIN_RATE_LIMIT_ACCOUNT = int(os.getenv("NEW_MUD_LOGIN_RATE_LIMIT_ACCOUNT", "10"))
AUTH_LOGIN_RATE_LIMIT_IP = int(os.getenv("NEW_MUD_LOGIN_RATE_LIMIT_IP", "100"))
AUTH_RECOVERY_RATE_LIMIT_ACCOUNT = int(os.getenv("NEW_MUD_RECOVERY_RATE_LIMIT_ACCOUNT", "5"))
AUTH_RECOVERY_RATE_LIMIT_IP = int(os.getenv("NEW_MUD_RECOVERY_RATE_LIMIT_IP", "100"))
AUTH_RECOVERY_RATE_LIMIT_DEVICE = int(os.getenv("NEW_MUD_RECOVERY_RATE_LIMIT_DEVICE", "20"))
AUTH_RECOVERY_DEVICE_MAX_AGE_SECONDS = int(
    os.getenv("NEW_MUD_RECOVERY_DEVICE_MAX_AGE_SECONDS", str(365 * 24 * 60 * 60))
)
AUTH_VERIFICATION_ENABLED = os.getenv("NEW_MUD_VERIFICATION_ENABLED", "0") == "1"
AUTH_VERIFICATION_WORKER_READY = os.getenv("NEW_MUD_VERIFICATION_WORKER_READY", "0") == "1"
AUTH_VERIFICATION_PROVIDER_READY = os.getenv("NEW_MUD_VERIFICATION_PROVIDER_READY", "0") == "1"
AUTH_VERIFICATION_ALLOW_TEST_EMAIL_BACKEND = False
AUTH_CONTACT_ENCRYPTION_KEYS = _json_string_map("NEW_MUD_CONTACT_ENCRYPTION_KEYS_JSON")
AUTH_CONTACT_ENCRYPTION_CURRENT_KEY_ID = os.getenv("NEW_MUD_CONTACT_ENCRYPTION_CURRENT_KEY_ID", "")
AUTH_CONTACT_LOOKUP_KEYS = _json_string_map("NEW_MUD_CONTACT_LOOKUP_KEYS_JSON")
AUTH_CONTACT_LOOKUP_CURRENT_KEY_ID = os.getenv("NEW_MUD_CONTACT_LOOKUP_CURRENT_KEY_ID", "")
AUTH_VERIFICATION_CODE_PEPPER_KEYS = _json_string_map("NEW_MUD_VERIFICATION_CODE_PEPPER_KEYS_JSON")
AUTH_VERIFICATION_CODE_PEPPER_CURRENT_KEY_ID = os.getenv(
    "NEW_MUD_VERIFICATION_CODE_PEPPER_CURRENT_KEY_ID", ""
)
AUTH_DELIVERY_PAYLOAD_ENCRYPTION_KEYS = _json_string_map(
    "NEW_MUD_DELIVERY_PAYLOAD_ENCRYPTION_KEYS_JSON"
)
AUTH_DELIVERY_PAYLOAD_ENCRYPTION_CURRENT_KEY_ID = os.getenv(
    "NEW_MUD_DELIVERY_PAYLOAD_ENCRYPTION_CURRENT_KEY_ID", ""
)
AUTH_VERIFICATION_IDEMPOTENCY_RETENTION_SECONDS = int(
    os.getenv("NEW_MUD_VERIFICATION_IDEMPOTENCY_RETENTION_SECONDS", str(24 * 60 * 60))
)
AUTH_VERIFICATION_DEVICE_MAX_AGE_SECONDS = int(
    os.getenv("NEW_MUD_VERIFICATION_DEVICE_MAX_AGE_SECONDS", str(24 * 60 * 60))
)
AUTH_VERIFICATION_CHALLENGE_TTL_SECONDS = int(
    os.getenv("NEW_MUD_VERIFICATION_CHALLENGE_TTL_SECONDS", "600")
)
AUTH_VERIFICATION_LEASE_SECONDS = int(os.getenv("NEW_MUD_VERIFICATION_LEASE_SECONDS", "30"))
AUTH_VERIFICATION_MAX_DELIVERY_ATTEMPTS = int(
    os.getenv("NEW_MUD_VERIFICATION_MAX_DELIVERY_ATTEMPTS", "5")
)
AUTH_TRUSTED_PROXY_NETWORKS = [
    value.strip()
    for value in os.getenv("NEW_MUD_AUTH_TRUSTED_PROXY_NETWORKS", "").split(",")
    if value.strip()
]

EMAIL_BACKEND = os.getenv(
    "NEW_MUD_EMAIL_BACKEND",
    "django.core.mail.backends.locmem.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "465"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "1") == "1"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "")

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "new_mud.apps.identity.exceptions.api_exception_handler",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "new_mud.observability.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}
