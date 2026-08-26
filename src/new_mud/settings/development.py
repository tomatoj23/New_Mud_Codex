from .base import *  # noqa: F403

AUTH_ALLOWED_ORIGINS = ["http://localhost:5173"]

DEBUG = True
SECRET_KEY = SECRET_KEY or "unsafe-development-only-key"  # noqa: F405
AUTH_TOKEN_SIGNING_KEY = (  # noqa: F405
    AUTH_TOKEN_SIGNING_KEY or "unsafe-development-only-token-signing-key"  # noqa: F405
)
