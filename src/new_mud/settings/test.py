from .base import *  # noqa: F403

SECRET_KEY = "test-only-key"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
DATABASES["default"]["NAME"] = "new_mud_test"  # noqa: F405
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405
