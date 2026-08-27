import base64

from .base import *  # noqa: F403

SECRET_KEY = "test-only-key"
AUTH_TOKEN_SIGNING_KEY = "test-only-token-signing-key"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
DATABASES["default"]["NAME"] = "new_mud_test"  # noqa: F405
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405
CONTENT_STARTUP_ENABLED = False
AUTH_ALLOWED_ORIGINS = ["https://testserver"]
AUTH_BASELINE_CUTOVER_ENABLED = True
AUTH_VERIFICATION_WORKER_READY = True
AUTH_VERIFICATION_PROVIDER_READY = True
AUTH_VERIFICATION_ALLOW_TEST_EMAIL_BACKEND = True
AUTH_CONTACT_ENCRYPTION_KEYS = {
    "contact-encryption-v1": base64.urlsafe_b64encode(b"c" * 32).decode("ascii")
}
AUTH_CONTACT_ENCRYPTION_CURRENT_KEY_ID = "contact-encryption-v1"
AUTH_CONTACT_LOOKUP_KEYS = {
    "contact-lookup-v1": base64.urlsafe_b64encode(b"l" * 32).decode("ascii")
}
AUTH_CONTACT_LOOKUP_CURRENT_KEY_ID = "contact-lookup-v1"
AUTH_VERIFICATION_CODE_PEPPER_KEYS = {
    "verification-code-v1": base64.urlsafe_b64encode(b"p" * 32).decode("ascii")
}
AUTH_VERIFICATION_CODE_PEPPER_CURRENT_KEY_ID = "verification-code-v1"
AUTH_DELIVERY_PAYLOAD_ENCRYPTION_KEYS = {
    "delivery-payload-v1": base64.urlsafe_b64encode(b"d" * 32).decode("ascii")
}
AUTH_DELIVERY_PAYLOAD_ENCRYPTION_CURRENT_KEY_ID = "delivery-payload-v1"
DEFAULT_FROM_EMAIL = "no-reply@test.invalid"
